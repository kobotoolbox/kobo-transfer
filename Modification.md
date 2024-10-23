# kobo-transfer modification
Change Validation Statuses based on JSON file.

## Setup

1. Clone a copy of this repo somewhere on your local machine:

```bash
git clone https://github.com/yutsukioka/kobo-transfer
```

2. Install packages from `requirements.txt`.

3. Prepare config.json file for the option of --config-file. This JSON file is also used for helper script.

**Note:** 
Recomend to transfer all submissions to new asset before applying any changes.
Leave the `dest.asset_uid` field empty in the config file:

```
{
  ...
  "dest": {
    ...
    "asset_uid": ""
  }
}
```

Run commandline to transfer. e.g., 
```bash
python3 run.py \
  [--asset] [--config-file/c <file path>]
```
Read original REDAME.md for use transfering validation status and download media in the attachments directory.
```bash
python 3 run.py \
  [--validation-status] [--keep-media]
```

## Usage

```bash
python3 run.py \
  [--config-file/-c <file path>] [--sync/-s] [--change-validation-statuses/-cvs <file path>]
```
**The change validation statuses only works if it's used with --sync as well as the same assets of 'src' and 'dest' designated in the config.json file.**

## Helper script 1
Download all submissions of the asset written in config JSON file in the 'attachments' folder.

**Usage**
helpers/download_submissions.py
```bash
python3 helpers/download_submissions.py \
  [--config-file/-c <file path>] [--format <xlsx, json, xml, geojson>]
```

Example of use.
```bash
python helpers/download_submissions.py --config-file config-xxxxx.json --format xlsx # Excel file download.
```

🕵️ Validating config file  
📥 Downloading XLSX file from: https://{kf_url}/api/v1/data/{form_id}.xlsx  
✅ XLSX file saved successfully to: attachments/{asset_uid}.xlsx  
📥 Downloading JSON data from: https://{kf_url}/api/v2/assets/{asset_uid}/data.json  
✅ JSON file saved successfully to: attachments/{asset_uid}.json  
✅ Generated validation status Excel: attachments/{asset_uid}_val_stat.xlsx  

Script will create three files.
```bash
─── {submission_uid}
    ├── {asset_uid}.xlsx
    ├── {asset_uid}.json
    └── {asset_uid}_val_stat.xlsx

```
{asset_uid}.xlsx contains all submissions but not including validation_status_uid.  
{asset_uid}.json contains all submissions including validation_status_uid.  
{asset_uid}_val_stat.xlsx contains only _uuid, validation_status_uid, and _id.  

## Change / enter desired validation statuses in the {asset_uid}_val_stat.xlsx.
Change value of each line of 'validation_status_uid' to one of four status.
    - 'validation_status_approved'  
    - 'validation_status_not_approved'  
    - 'validation_status_on_hold'  
    - ''  

## Helper script 2
Convert Excel file to JSON file.

helpers/gen_json.py
```bash
python3 helpers/gen_json.py
   [<attachments/file path to Excel file>] [<attachments/file path to JSON file>]
```

Example of use.
```bash
python helpers/gen_json.py attachments/{asset_uid}_val_stat.xlsx attachments/{asset_uid}_val_stat.json
```

✅ JSON file has been saved to attachments/{asset_uid}_val_stat.json  

## Final step to change validation statuses.
Example of use.
```bash
python run.py --config-file config-xxxxx.json --sync --change-validation-statuses attachments/{asset_uid}_val_stat.json
🕵️ Validating config file  
🪪 Getting _uuid values from src and dest projects  
🔄 Changing validation statuses using {change_validation_statuses_file}  
-----------  
validation_status_on_hold: xxx  
validation_status_not_approved: xxx  
validation_status_approved: xxx  
-----------  
```

Another example of use.
```bash
python run.py --config-file config-xxxxxx.json --asset --keep-media --change-validation-statuses attachments/{asset_uid}_val_stat.json
🕵️ Validating config file  
📋 Transferring asset, versions and form media  
✨ New asset UID at `dest`: {new_asset_uid}  
💼 Transferring all form media files  
✅ locations.csv  
✅ nat_id.csv  
✅ enumerators.csv  
✅ programme_no.csv  
📨 Transferring and deploying all versions  
✅ {new_asset_uid}  
✨ All 1 versions deployed  
📸 Getting all submission media .....................................................................
📨 Transferring submission data  
✅ {_uuid_1}  
✅ {_uuid_2}  
✅ {_uuid_3}  
✨ Done  
🧮 xxx  ✅ xxx  ⚠️ 0     ❌ 0  
🔄 Changing validation statuses using attachments/{asset_uid}_val_stat.json  
-----------  
validation_status_on_hold: xx  
validation_status_not_approved: xx  
validation_status_approved: xxx  
-----------  
```

## To do list
- [ ] Selected submission transfer to a new asset.
- [ ] Change submission data when it transfer to a new asset.
- [ ] Bulk edit for the first repeated questions and other non-nested questions. # See bulk_edit_test.py


## Very useful api usages article
https://community.kobotoolbox.org/t/how-to-make-an-api-request-for-editing-a-submitted-instance/13050
https://community.kobotoolbox.org/t/updating-records-via-the-api/4291/4

KoBoToolbox API Usage Summary (for my memo)

| **Action**                    | **Endpoint**                                                         | **Method** |
|-------------------------------|----------------------------------------------------------------------|------------|
| **Submit New Data (V1)**      | `/api/v1/submissions`                                                | `POST`     |
| **Retrieve Submissions (V2)** | `/api/v2/assets/{asset_uid}/data/`                                   | `GET`      |
| **Delete Submission (V1)**    | `/api/v1/data/{form_id}/{submission_id}/`                            | `DELETE`   |
| **Change Validation Status**  | `/api/v2/assets/{asset_uid}/data/{submission_id}/validation_status/` | `PATCH`    |
| **Edit via Enketo**           | `/api/v2/assets/{asset_uid}/data/{submission_id}/enketo/edit/`       | `GET`      |
| **Bulk Edit Submission (V2)** | `/api/v2/assets/{asset_uid}/data/bulk/`                              | `PATCH`    |


| **Action**                    | **curl client command**                                                                       |
|-------------------------------|-----------------------------------------------------------------------------------------------|
| **Submit New Data (V1)**      | ```bash                                                                                       |
|                               | curl -X POST \                                                                                |
|                               |   <kc_url>/api/v1/submissions \                                                               |
|                               |   -F "xml_submission_file=@submission.xml" \                                                  |
|                               |   -H "Authorization: Token <your_token>"                                                      |
|                               | ```                                                                                           |
| **Retrieve Submissions (V2)** | ```bash                                                                                       |
|                               | curl -X GET \                                                                                 |
|                               |   "<kf_url>/api/v2/assets/{asset_uid}/data/?format=json" \                                    |
|                               |   -H "Authorization: Token <your_token>"                                                      |
|                               | ```                                                                                           |
| **Delete Submission (V1)**    | ```bash                                                                                       |
|                               | curl -X DELETE \                                                                              |
|                               |   "<kc_url>/api/v1/data/{form_id}/{submission_id}/" \                                         |
|                               |   -H "Authorization: Token <your_token>"                                                      |
|                               | ```                                                                                           |
| **Change Validation Status**  | ```bash                                                                                       |
|                               | curl -X PATCH \                                                                               |
|                               |   "<kf_url>/api/v2/assets/{asset_uid}/data/{submission_id}/validation_status/" \              |
|                               |   --data '{"validation_status.uid": "validation_status_approved"}' \                          |
|                               |   -H "Authorization: Token <your_token>"                                                      |
|                               | ```                                                                                           |
| **Edit via Enketo**           | ```bash                                                                                       |
|                               | curl -X GET \                                                                                 |
|                               |   "<kf_url>/api/v2/assets/{asset_uid}/data/{submission_id}/enketo/edit/?return_url=false" \   |
|                               |   -H "Authorization: Token <your_token>"                                                      |
|                               | ```                                                                                           |
| **Bulk Edit Submission (V2)** | ```bash                                                                                       |
|                               | curl -X PATCH \                                                                               |
|                               |   "<kf_url>/api/v2/assets/{asset_uid}/data/bulk/” \                                           |
|                               |   –data ‘{“payload”: {“submission_ids”: [“1234”, “5678”], “data”: {“field_name”: “value”}}}’ \|
|                               |  -H “Authorization: Token <your_token>”                                                       |
|                               | ```                                                                                           |
