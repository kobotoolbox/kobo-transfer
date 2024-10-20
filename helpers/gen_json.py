import csv
import json
import argparse

def generate_changes_json(input_csv, output_json):
    changes_list = []
    with open(input_csv, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            uuid = row.get('_uuid') or row.get('uuid')
            if not uuid:
                continue
            changes = {k: v for k, v in row.items() if k != '_uuid' and v != ''}
            if changes:
                entry = {
                    'uuid': uuid,
                    'changes': changes
                }
                changes_list.append(entry)
    with open(output_json, 'w', encoding='utf-8') as jsonfile:
        json.dump(changes_list, jsonfile, indent=2)
    print(f"✅ Changes JSON file has been written to {output_json}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate changes.json from edited CSV file.')
    parser.add_argument('input_csv', help='Path to the edited CSV file.')
    parser.add_argument('output_json', help='Path to the output JSON file.')
    args = parser.parse_args()
    generate_changes_json(args.input_csv, args.output_json)
