import requests
import json
import sys
import argparse
from pathlib import Path

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))
from helpers.config import Config

def main(config_file=None, payload_file=None):
    try:
        config = Config(config_file=config_file).src
    except Exception as e:
        print(f"⚠️ Failed to load configuration: {e}")
        sys.exit(1)

    headers = config.get('headers', {})
    kf_url = config.get('kf_url')
    asset_uid = config.get('asset_uid')  # Ensure 'asset_uid' is in the config

    if not headers:
        print("❌ 'headers' not found in configuration.")
        sys.exit(1)

    if not kf_url:
        print("❌ 'kf_url' not found in configuration.")
        sys.exit(1)

    if not asset_uid:
        print("❌ 'asset_uid' not found in configuration.")
        sys.exit(1)

    # Prepare the payload
    if payload_file:
        # If payload_file is provided, read from JSON file
        try:
            with open(payload_file, 'r', encoding='utf-8') as f:
                payload_content = json.load(f)
        except Exception as e:
            print(f"❌ Failed to read payload file: {e}")
            sys.exit(1)
    else:
        # Define payload directly in the code
        payload_content = {
            "payload": {
                "submission_ids": [5697, 5698, 5699],  # Replace with actual numerical IDs
                "data": {
                    "individual_questions/individual_details/full_name_i_c": "JOSPHANT OCHIENG GENGA",
                    "individual_questions/individual_details/gender_i_c": "female"
                }
            }
        }

    # Validate payload structure
    if not isinstance(payload_content, dict):
        print("❌ Payload should be a JSON object.")
        sys.exit(1)

    if "payload" not in payload_content:
        print("❌ Payload must contain 'payload' key.")
        sys.exit(1)

    bulk_payload = payload_content["payload"]

    if "submission_ids" not in bulk_payload or "data" not in bulk_payload:
        print("❌ Payload must contain 'submission_ids' and 'data' keys within 'payload'.")
        sys.exit(1)

    submission_ids = bulk_payload["submission_ids"]
    data_to_update = bulk_payload["data"]

    if not isinstance(submission_ids, list) or not all(isinstance(uid, (int, str)) for uid in submission_ids):
        print("❌ 'submission_ids' must be a list of numerical IDs.")
        sys.exit(1)

    if not isinstance(data_to_update, dict):
        print("❌ 'data' must be a dictionary of fields to update.")
        sys.exit(1)

    # Construct the bulk PATCH endpoint
    bulk_patch_url = f"{kf_url}/api/v2/assets/{asset_uid}/data/bulk/"

    # Make the PATCH request
    try:
        response = requests.patch(
            url=bulk_patch_url,
            json=payload_content,  # Use json= to automatically set Content-Type
            headers=headers
        )

        if response.status_code == 200:
            print("✅ Submissions edited successfully.")
        elif response.status_code == 403:
            print("❌ Permission denied. Check your token and permissions.")
        elif response.status_code == 404:
            print("❌ Submission(s) or asset not found.")
        else:
            print(f"⚠️ Unexpected error: {response.status_code} - {response.text}")

    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='A CLI tool to update submissions in KoBoToolbox.'
    )
    parser.add_argument(
        "--config-file",
        "-c",
        type=str,
        default="config.json",
        help="Path to the configuration file (default: config.json)"
    )
    parser.add_argument(
        "--payload-file",
        "-p",
        type=str,
        default=None,
        help="Path to the payload JSON file (optional). If not provided, payload is defined in the script."
    )
    args = parser.parse_args()

    try:
        main(
            config_file=args.config_file,
            payload_file=args.payload_file
        )
    except KeyboardInterrupt:
        print('🛑 Stopping run')
        sys.exit()