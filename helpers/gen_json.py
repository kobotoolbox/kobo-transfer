import pandas as pd
import json
import argparse

def generate_changes_json(input_xlsx, output_json):
    try:
        df = pd.read_excel(input_xlsx)
        if '_uuid' not in df.columns:
            raise ValueError('❌ _uuid column not found in the Excel file.')
        
        changes_list = []    
    
        for _, row in df.iterrows():
            uuid = row.get('_uuid') or row.get('uuid')
            validation_status = row.get('validation_status_uid', "")
            entry = {
                "_uuid": uuid,
                "validation_status_uid": validation_status
            }
            changes_list.append(entry)
        with open(output_json, 'w', encoding='utf-8') as jsonfile:
            json.dump(changes_list, jsonfile, indent=2)
        print(f"✅ Changes JSON file has been written to {output_json}")
    
    except Exception as e:
        print(f"❌ Error generating changes JSON file: {e}")
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate changes.json from edited CSV file.')
    parser.add_argument('input_xlsx', help='Path to the Excel file.')
    parser.add_argument('output_json', help='Path to the output JSON file.')
    args = parser.parse_args()
    generate_changes_json(args.input_xlsx, args.output_json)
