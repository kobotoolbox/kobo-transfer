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
  [--asset]
```
Read original REDAME.md for use transfering validation status and media in the attachments directory.
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
helpers/download_xlsx.py
```bash
python3 helpers/download_xlsx.py \
  [--config-file/-c <file path>]
```
Script will create two files.
```bash
─── {submission_uid}
    ├── {asset_uid}.xlsx
    └── {asset_uid}_val_stat.xlsx

```
{asset_uid}.xlsx contains all submissions.
{asset_uid}_val_stat.xlsx contains only _uuid and validation_status_uid

## Change / enter desired validation statuses in the Excel file to the generated xlsx file.
Change value of each line of 'validation_status_uid' to four status.
    'validation_status_approved'
    'validation_status_not_approved'
    'validation_status_on_hold'
    ''

## Helper script 2
Convert Excel file to JSON file.

helpers/gen_json.py
```bash
python3 helpers/gen_json.py
   [<attachments/file path to Excel file>] [<attachments/file path to JSON file>]
```

## To do list
- [ ] Selected submission transfer to a new asset.
- [ ] Change submission data when it transfer to a new asset.

## Very useful api usages article
https://community.kobotoolbox.org/t/how-to-make-an-api-request-for-editing-a-submitted-instance/13050

KoBoToolbox API Usage Summary (for my memo)

| **Action**                    | **Endpoint**                                                         | **Method** |
|-------------------------------|----------------------------------------------------------------------|------------|
| **Submit New Data (V1)**      | `/api/v1/submissions`                                                | `POST`     |
| **Retrieve Submissions (V2)** | `/api/v2/assets/{asset_uid}/data/`                                   | `GET`      |
| **Delete Submission (V1)**    | `/api/v1/data/{form_id}/{submission_id}/`                            | `DELETE`   |
| **Change Validation Status**  | `/api/v2/assets/{asset_uid}/data/{submission_id}/validation_status/` | `PATCH`    |
| **Edit via Enketo**           | `/api/v2/assets/{asset_uid}/data/{submission_id}/enketo/edit/`       | `GET`      |


| **Action**                    | **curl client command**                                                                     |
|-------------------------------|---------------------------------------------------------------------------------------------|
| **Submit New Data (V1)**      | ```bash                                                                                     |
|                               | curl -X POST \                                                                              |
|                               |   <kc_url>/api/v1/submissions \                                                             |
|                               |   -F "xml_submission_file=@submission.xml" \                                                |
|                               |   -H "Authorization: Token <your_token>"                                                    |
|                               | ```                                                                                         |
| **Retrieve Submissions (V2)** | ```bash                                                                                     |
|                               | curl -X GET \                                                                               |
|                               |   "<kf_url>/api/v2/assets/{asset_uid}/data/?format=json" \                                  |
|                               |   -H "Authorization: Token <your_token>"                                                    |
|                               | ```                                                                                         |
| **Delete Submission (V1)**    | ```bash                                                                                     |
|                               | curl -X DELETE \                                                                            |
|                               |   "<kc_url>/api/v1/data/{form_id}/{submission_id}/" \                                       |
|                               |   -H "Authorization: Token <your_token>"                                                    |
|                               | ```                                                                                         |
| **Change Validation Status**  | ```bash                                                                                     |
|                               | curl -X PATCH \                                                                             |
|                               |   "<kf_url>/api/v2/assets/{asset_uid}/data/{submission_id}/validation_status/" \            |
|                               |   --data '{"validation_status.uid": "validation_status_approved"}' \                        |
|                               |   -H "Authorization: Token <your_token>"                                                    |
|                               | ```                                                                                         |
| **Edit via Enketo**           | ```bash                                                                                     |
|                               | curl -X GET \                                                                               |
|                               |   "<kf_url>/api/v2/assets/{asset_uid}/data/{submission_id}/enketo/edit/?return_url=false" \ |
|                               |   -H "Authorization: Token <your_token>"                                                    |
|                               | ```                                                                                         |

