# kobo-transfer

Transfer submissions from Google Form to Kobo Project

## Requirements

Make sure you have the following Python packages installed:

```bash
pip install openpyxl pandas requests xmltodict python-dateutil
```

## Setup

1. Destination project must be deployed and have the same content as Google Form. All questions should be in same order. 


|Google Question Type | Kobo Question Type |
| -------- | -------- |
| Select one | Multiple Choice |
| Short Answer, Paragraph |Text|
| Checkboxes | Select Many|
| Linear Scale | Range |
| Dropdown | Select One|
| Date | Date |
| Time | Time |


2. Clone a copy of this repo somewhere on your local machine

3. Copy `sample-config.json` to `config.json` and add your configuration details
   for the source (`src`) and destination (`dest`) projects. If transfering from google forms to kobo, duplicate src and destination url and token.

4. Open Google Form data (Responses tab) in Google Sheets, and download as xlsx from there (file → download as → microsoft excel (xlsx))


## Usage

```bash
python3 run2.py -g -ef [excel_file_path]
```
To run transfer from downloaded google -g flag must be passed. When -g flag is passed, -ef flag is mandatory. File path of the xlsx form downloaded from google sheets can be passed in here. 

## Limitations
- assumes that kobo project and google form question types, and order match (does not throw error but transferred submissios will be recorded incorrectly)
- _submitted_by in Kobo will show username of account running the transfer, for all submissions.
- submission_time in Kobo will show the time transfer was completed. 'end' shows time of response submission.
- If transfer is run multiple times, repetitions will appear in kobo project
- For time question types in kobo, time zone is recorded. Time question types in google sheets does not have the same feature. Time will not show UTC + ___. 
- Text submissions will be changed: all commas will show up as a space character, all text will be lowercase

- data could be recorded in Kobo as 'invalid' but code will not throw error in this case

- Google sheets does not have a ‘start’ and ‘end’ like kobo does; it only records submission time. Submission time data will show up in ‘end’ column in kobo project. 
- Does not account for empty submissions. Empty submission in xlsx will be transferred to kobo 
- If ‘None’ is a response in Google submission, it will show up as blank after being transferred to kobo 

- Although submissions will not be duplicated across multiple runs of the
  script, if the submissions contain attachment files, the files are duplicated
  on the server.
- The script does not check if the source and destination projects are identical
  and will transfer submission data regardless.


- Does not support Google question types multiple choice grid, tick box grid, and file attachments. 


