import string
from datetime import datetime
from xml.etree import ElementTree as ET
import openpyxl
import xml.etree.ElementTree as ET
from .media import rename_media_folder
import pandas as pd
from datetime import datetime
from dateutil import parser
from .xml import generate_new_instance_id
from helpers.config import Config


def format_timestamp(google_timestamp):
    dt = parser.parse(google_timestamp)
    kobo_format = "%Y-%m-%dT%H:%M:%S.%f"
    #[-3] since kobo stores to miliseconds .000
    return dt.strftime(kobo_format)[:-3]

def format_date(google_date):
    date = None
    try: 
        date = datetime.strptime(google_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return google_date
    
    if (date != None):
        return date.strftime("%Y-%m-%d")
    else: 
        return google_date

def format_time(google_time):
    is_time = None
    try: 
        is_time = datetime.strptime(google_time, '%H:%M:%S')
    except ValueError:
        return google_time
    
    if (is_time!= None):
        return is_time.strftime("%H:%M:%S.%f")[:-3]
    else: 
        return google_time

def group_element(_uid, group, cell_value):
    """creates logical groups in xml for kobo"""
    group_name = group.split("/")

    element = _uid.find('.//' + group_name[0])
    if (element == None):
        element = ET.SubElement(_uid, group_name[0])

    if (group_name[0] != group_name[1]):
        group_element = ET.SubElement(element, group_name[1])
        group_element.text = str(cell_value)
        
    return _uid


def repeat_groups(submission_xml, uuid, workbook): 
    """method is called whne there are multiple sheets in xlsx, because it is assumed to be repeat groups"""
    uuid = uuid[len("uuid:"):]
    sheet_names = workbook.sheetnames
    sheet_names = sheet_names[1:]
    for sheet_name in sheet_names:
        sheet = workbook[sheet_name]
        headers = [cell.value for cell in sheet[1]]
        try:
            submission_uid_header = headers.index("_submission__uuid")
        except Exception:
            print("Error: if xlsx file has multiple tabs, data in extra sheets must be in expected repeating group format")
            raise
        for row in sheet.iter_rows(min_row=2, values_only=True):
            submission_uid = str(row[submission_uid_header])
            if (submission_uid == uuid):
                    element = ET.SubElement(submission_xml, sheet_name)
            for col_num, cell_value in enumerate(row, start=1):
                col_name = str(headers[col_num-1])
                group_arr = col_name.split('/')
            
                if cell_value is None or cell_value == "none" or cell_value == "None":  
                    cell_value = ""
                
                if len(group_arr) == 2 and sheet_name in col_name:
                    if (submission_uid == uuid): 
                        group_element = ET.SubElement(element, group_arr[1])
                        group_element.text = str(cell_value)
        
        return submission_xml 



def initial_repeat(_uid, col_arr, cell_value):
    """When xlsx data doesn't have a uuid (initial transfer to kobo), repeating group responses created with this method.
    All questions in repeat group should have an equal number of responses, even if a response is blank. If question 1 in repeating group responses are {a, b, c},
    question 2 responses need to have same number so indices match {1,,3}
    expected label to indicate repeat group: repeat/{group_name}/{question}
    """
    #repeat/group_name/question
    group_name = col_arr[1]
    responses = cell_value.split(',')
    elements = _uid.findall('.//' + group_name)
    if not elements: 
        #when initial group doesn't exist, create element with group name, and subelement with question label and response
        for response in responses:
            element = ET.SubElement(_uid, group_name)
            subelement = ET.SubElement(element, col_arr[2])
            subelement.text = response
    else: 
        if (len(elements) != len(responses)): 
            raise Exception("Repeat group transfer failed. They should be saved in order with commas seperating each repeat response. No response should have a comma within it.")
        for group_el, response in zip(elements, responses):
            subelement = ET.SubElement(group_el, col_arr[2])
            subelement.text = response

    return _uid


def open_xlsx(excel_file_path): 
    """opens xlsx, and formats all data into xml format compatible with kobo"""
    try: 
        workbook = openpyxl.load_workbook(excel_file_path, read_only=True)
    except FileNotFoundError as e:
        print(f"⚠️ Error: Excel file not found at path '{excel_file_path}'.")
        raise(e)
    except openpyxl.utils.exceptions.InvalidFileException:
            print(f"⚠️ Error: Invalid file format for '{excel_file_path}'")
            raise(e)
    except TypeError as e: 
        if "NoneType" in str(e):
            print(f"⚠️ Error: File path is None. Specify xls file path with flag -ef")
            raise(e)
    except Exception as e:
        print(f"⚠️ Something went wrong when reading xlsx file: {e}")
        raise(e)
    return workbook

def formhub_element(uid, NSMAP, formhubuuid):
        # create formhub element with nested uuid
        _uid = ET.Element(uid, NSMAP)
        fhub_el = ET.SubElement(_uid, "formhub") 
        uuid_el = ET.SubElement(fhub_el, "uuid") 
        uuid_el.text = formhubuuid
        return _uid

def format_xml_from_google(cell_value):
    #multiple select question responses from google forms are sepearated by ',' 
    #to show up in kobo, responses must be lowercase, spaces must be replaced with '_' and seperated by ' '
    if ',' in cell_value:
        options_selected = cell_value.split(',')
        for i in range(len(options_selected)):
            options_selected[i] = options_selected[i].strip().lower()
            options_selected[i] = options_selected[i].replace(' ', '_')
        cell_value = ' '.join(options_selected)
        
    #formatting date and time to be compatible with kobo are specific to how google forms saves data
    cell_value = format_time(str(cell_value))
    cell_value = format_date(cell_value)
    return cell_value

def meta_element(_uid, formatted_uuid):
    """meta tag 
          <meta>
                <instanceID>uuid:a0ea37ef-ac71-434b-93b6-1713ef4c367f</instanceID>
                <deprecatedID>
            </meta>
    }"""
    meta = ET.Element("meta")
    if (formatted_uuid == "uuid:"):
        formatted_uuid = generate_new_instance_id()[1]
    instanceId = ET.SubElement(meta, "instanceID") 
    deprecatedId = ET.SubElement(meta, "deprecatedID")
    instanceId.text = formatted_uuid
    deprecatedId.text = formatted_uuid

    _uid.append(meta)
    return formatted_uuid


def single_submission_xml( gtransfer, _uid, col_name, cell_value, all_empty, formatted_uuid):
    if (gtransfer):
        cell_value = format_xml_from_google(str(cell_value))
     
    if cell_value is None or cell_value == "none" or cell_value == "None":  
        cell_value = ""
    else:
        all_empty = False
        
    #if xlsx data is downloaded from kobo, it will contain this column
    if (col_name == "_uuid"):
        if cell_value == "": #if there is no uuid specified, new one will be generated
            formatted_uuid = formatted_uuid + generate_new_instance_id()[1]
        else:
            formatted_uuid = formatted_uuid + str(cell_value)
                
    #column headers that include / indicate {group_name}/{question}
    group_arr = col_name.split('/')
    if len(group_arr) == 2:
        _uid = group_element(_uid, str(col_name), str(cell_value))
        return all_empty, formatted_uuid

    #repeat groups, for initial data transfer to kobo (without uuid) are saved like this: repeat/testname/group_question_1_text
    #therefore, column header for a repeat group will have three elements when split()
    if len(group_arr) == 3 and group_arr[0] == "repeat":
        _uid = initial_repeat(_uid, group_arr, str(cell_value))
        return all_empty, formatted_uuid
                

    if not (col_name.startswith("_")):  #column automatically generated with kobo (this is after data has been downloaded from kobo)
        cell_element = ET.SubElement(_uid, col_name)
        if (col_name == "end" or col_name == "start"):
            if (gtransfer):
                cell_value = format_timestamp(str(cell_value))
            elif (cell_value != ""):
                cell_value = cell_value.isoformat()                
        cell_element.text = str(cell_value)
            
    return all_empty, formatted_uuid

def general_xls_to_xml(excel_file_path, submission_data, gtransfer = False):
    workbook = open_xlsx(excel_file_path)
    #first sheet should have all data, if xlsx contains other sheets, they must be for repeat groups
    sheet = workbook.worksheets[0]

    uid = submission_data["asset_uid"]
    formhubuuid = submission_data["formhub_uuid"]
    v = submission_data["version"]
    __version__ = submission_data["__version__"]

    root = ET.Element("root") 
    results = ET.Element("results")
    headers = [cell.value for cell in sheet[1]]
    
    #data collected in google forms automatically records timestamp
    if (gtransfer):
        for i in range(len(headers)): 
            if (headers[i] == "Timestamp"): 
                headers[i] = "end"
            headers[i] =  headers[i].rstrip(string.punctuation)
            headers[i] = headers[i].replace(" ", "_")

    num_results = 0
    NSMAP = {"xmlns:jr" :  'http://openrosa.org/javarosa',
         "xmlns:orx" : 'http://openrosa.org/xforms', 
         "id" : str(uid),
         "version" : str(v)}
    for row_num, row in enumerate(sheet.iter_rows(min_row=2, values_only=True,), start=2):
        _uid = formhub_element(uid, NSMAP, formhubuuid)
        if (gtransfer):
            #google form data does not collect start time data
            start_element = ET.Element("start")
            _uid.append(start_element)

        all_empty = True
        formatted_uuid = "uuid:"

        # Iterate through cells in the row and create corresponding XML elements
        for col_num, cell_value in enumerate(row, start=1):
                col_name = headers[col_num-1]
                all_empty, formatted_uuid = single_submission_xml(gtransfer, _uid, col_name, cell_value, all_empty, formatted_uuid)
        
        if (all_empty):
            print("Warning: Data may include one or more blank responses where no questions were answered.")
        #iterate through other sheets to create repeat groups, and append to xml
        repeat_elements =  repeat_groups(_uid, formatted_uuid, workbook)
        if (repeat_elements != None):
            _uid = repeat_elements
        
        version = ET.Element("__version__")
        version.text = (__version__)
        _uid.append(version)

        formatted_uuid = meta_element(_uid, formatted_uuid)

        #for initial transfer (without uuids), attachments are saved with row numbers
        #row number folder is renamed to uuid to complete transfer to kobo and associate attachment to specific response
        rename_media_folder(submission_data, formatted_uuid[len("uuid:"):], row_num)
        results.append(_uid)
        num_results += 1
    
    count =  ET.SubElement(root, 'count')
    count.text = (str(num_results))
    next = ET.SubElement(root, 'next')
    next.text = None 
    previous = ET.SubElement(root, 'previous')
    previous.text = None 
    root.append(results)
    #tree = ET.ElementTree(root)

    workbook.close()
    return root

