# kobo-transfer

Transfer submissions from XLSX Form to Kobo Project 

Demo: https://drive.google.com/file/d/1yMcsEKqOH3L09O00urFko3iB77PABuFh/view?usp=sharing 

## Usage

For XLSX: 
```bash
python3 run2.py -xt -ef [excel_file_path]
```

For data downloaded from Google Form:
```bash
python3 run2.py -gt -ef [excel_file_path]
```

## Requirements

Make sure you have the following Python packages installed:

```bash
pip install openpyxl pandas requests xmltodict python-dateutil
```

## Setup

1. Destination project must be deployed and have the same content as xlsx form. All questions should be in same order. 

2. Clone a copy of this repo somewhere on your local machine

3. Copy `sample-config.json` to `config.json` and add your configuration details
   for the source (`src`) and destination (`dest`) projects. If transfering from xls to kobo, duplicate src and destination url and token.

### Notes for Google Form Data Transfer

To ensure that destination project has the same content as Google Form. The corresponding question types for a Google Form, and Kobo is listed below:

|Google Question Type | Kobo Question Type |
| -------- | -------- |
| Multiple Choice | Select one |
| Short Answer, Paragraph |Text|
| Checkboxes | Select Many|
| Linear Scale | Range |
| Dropdown | Select One|
| Date | Date |
| Time | Time |

To download google form responses as xlsx:
   Open Google Form data (Responses tab) in Google Sheets, and download as xlsx from there (file → download as → microsoft excel (xlsx))

- As long as google question labels match kobo question labels, they don't need to be edited in the downloaded xlsx form before running transfer. Timestamp is automatically saved in Google Form responses, and the time format nor the column label need to be edited. Transfer tool will record this as the 'end' time when saving to Kobo project. 
- Each of the selected items for multiple select responses in Google Forms, are saved in a single cell and separated by commas when downloaded. If only one option is selected, need to add ',' at the end of the response.
- Time and Date question type responses also don't need to be edited. Running the transfer will convert them to the correct format for Kobo.

### Notes for General XLSX Data Transfer
- for initial transfer from xlsx to kobo, when there is no uuid, the column header for repeat groups must be repeat/{group name}/{xml header for question in repeating group}. Each question in repeat group must have its own column in xlsx.
- to associate media with a specific response/submission for initial transfer, when there is no _uuid column, row number of submission can be used. Media for the submission can be saved in file path ./attachments/{asset_uid}/{row_number}.
- for logical groups, column header can be {group name}/{xml header for question in repeating group}. The group name in the header must match Data Column Name in Kobo project.
- for ranking data, headers must be in this format: {xml header for question}/_1st_choice, {xml header for question}/_2nd_choice, {xml header for question}/_3rd_choice, and so on.

- if data downloaded from kobo as xlsx with XML values and headers, repeat groups span across multiple tabs. Script supports this, and data for these repeat group responses can be edited in the respective tabs and reuploaded.
- to minimise errors with formatting when data needs to be cleaned, it's best to do initial transfer from xlsx, then download the kobo data from xlsx with XML values and headers. The downloaded xlsx from Kobo is best to work from since all headers will be in the format the script expects. 

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
- If transferring from google form xlsx data (running -gt), submissions will be duplicated each time the script is run. Even when google form xlsx data is uploaded, edited, and then reuploaded, it will show up as a new submission instead of editing the one in kobo. To avoid this, after transferring from google form xlsx into kobo once, download the kobo data in xlsx form and edit/reupload that one with the flag -xt.
- Similarly, if running -xt for initial xlsx data without uuid, submissions will be duplicated each time script is run. To avoid, after initial transfer, download data from kobo as xlsx and edit/work with that. 

- if running -gt, responses and text submissions can not contain ',' or '/' since data will be transferred to Kobo incorrectly.
- assumes that kobo project and xlsx form question types and labels match (does not throw error but transferred submissions will be recorded incorrectly)
- any data transferred will be accepted by kobo. For example, if question type is number in kobo, but submission transferred is text/string, it will be saved as such. For questions types such as dropdown/select one, responses in xlsx can be any string and kobo will save (regardless of whether or not it is an option in the kobo project). 
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
Google form attachments are saved in a folder in Google Drive and folders are categorised by questions. If the google drive folder path is specified, it's possible to have all the images transferred to Kobo and have them show up in Gallery View. 
For the filter view of these images, where a question is selected in Kobo, and images submitted for that question appears, user would need to manually specify which google drive folder path corresponds to each question. It's also not possible to link an image to a specific submission. 

Right now, I've ony figured out how to transfer images, and I'm not sure if other types are possible to transfer. Given all these limitations because of the access rules in google drive, is it worth implementing? The Google drive image transfer to Kobo gallery works but is not included in the main branch since there are a few bugs and I'm not sure it makes sense to have if each drive link needs to be listed with each question? 
