# kobo-transfer

Transfer submissions from XLSX Form to Kobo Project

## Requirements

Make sure you have the following Python packages installed:

```bash
pip install openpyxl pandas requests xmltodict python-dateutil
```

## Setup

1. Destination project must be deployed and have the same content as Google Form. All questions should be in same order. 


|Google Question Type | Kobo Question Type |
| -------- | -------- |
| Multiple Choice | Select one |
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

For Google Form:
```bash
python3 run2.py -gt -ef [excel_file_path]
```
For XLSX: 
```bash
python3 run2.py -xt -ef [excel_file_path]
```

To run transfer from downloaded google -g flag must be passed.
If -ef not passed (python3 run2.py -g), default xls file used will be KoboTest(Responses_New).xlsx
If -ef passed, file path form downloaded from google sheets can be passed in as a string. 

## Edge Cases
- order of questions in google form, and kobo form can be different
- no effect if some questions in kobo form are not present in google form (the response cells for that column will just be empty)
- responses that are left blank in google form results show up correctly (also blank) in kobo
- if the question strings in kobo form and google form are not exact match, transfer will add columns in kobo data for the "extra" questions in google form 
  
### Plan to account for more edge Cases (TODO)
- print a warning if question strings seem similar (differences in capitalisation, spacing, and punctuation)
- print warning if number of questions in kobo form and google form do not match
- check if differences in spacing for question labels has unintended effects
- check differences in how data is saved when google form collects email addresses of responses
  
## Limitations
- If transferring from google form xlsx data, submissions will be duplicated each time the script is run. Even when google form xlsx data is uploaded, edited, and then reuploaded, it will show up as a new submission instead of editing the one in kobo. To avoid this, after transferring from google form xlsx into kobo once, download the kobo data in xlsx form and edit/reupload that one with the flag -xt.

- assumes that kobo project and google form question types and labels match (does not throw error but transferred submissions will be recorded incorrectly)
- _submitted_by in Kobo will show username of account running the transfer, for all submissions.
- Google sheets does not have a ‘start’ and ‘end’ like kobo does; it only records submission time. Submission time data will show up in ‘end’ column in kobo project.
- submission_time in Kobo will show the time transfer was completed. 'end' shows time of response submission.
- For time question types in kobo, time zone is recorded. Time question types in google sheets does not have the same feature. Time will not show UTC + ___. 
- Text submissions will be changed: all commas will show up as a space character, all text will be lowercase

- data could be recorded in Kobo as 'invalid' but code will not throw error in this case. For example, if date or time format is incorrect when uploading to a Kobo Date or Time question, it will save as "Invalid". 
- If ‘None’ is a response in Google submission, it will show up as blank after being transferred to kobo
  
- Although submissions will not be duplicated across multiple runs of the
  script, if the submissions contain attachment files, the files are duplicated
  on the server.

- Does not support Google question types multiple choice grid, tick box grid, and file attachments.

 ## Notes regarding media uploaded as a response in google forms
 


