import pandas as pd
import json
import argparse

def serialize_timestamp(obj):
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def generate_json(input_xlsx, output_json):
    try:
        excel_data = pd.read_excel(input_xlsx, sheet_name=None)
        main_sheet_name = list(excel_data.keys())[0]
        main_df = excel_data[main_sheet_name].fillna("")
        main_records = main_df.to_dict(orient='records')
        linked_data = {}
        for sheet_name, df in excel_data.items():
            if sheet_name != main_sheet_name:
                df = df.fillna("")
                for _, row in df.iterrows():
                    key = (row.get("_submission__id"), row.get("_submission__uuid"))
                    if key not in linked_data:
                        linked_data[key] = {}
                    if sheet_name not in linked_data[key]:
                        linked_data[key][sheet_name] = []
                    linked_data[key][sheet_name].append(row.to_dict())

        main_data = []
        for record in main_records:
            key = (record.get("_id"), record.get("_uuid"))
            related_entries = linked_data.get(key, {})

            for sheet_name, entries in related_entries.items():
                record[f"{sheet_name}_count"] = len(entries)
                record[sheet_name] = entries

            main_data.append(record)

        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, indent=2, ensure_ascii=False, default=serialize_timestamp)

        print(f"✅ JSON file has been saved to {output_json}")


    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate changes.json from edited CSV file.')
    parser.add_argument('input_xlsx', help='Path to the Excel file.')
    parser.add_argument('output_json', help='Path to the output JSON file.')
    args = parser.parse_args()
    generate_json(args.input_xlsx, args.output_json)

