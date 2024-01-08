import glob
import string
import io
import os
import requests

from datetime import datetime
from xml.etree import ElementTree as ET
from dateutil.parser import ParserError
import re
from utils.text import get_valid_filename

import openpyxl
import xml.etree.ElementTree as ET
from .media import rename_media_folder
import pandas as pd
from datetime import datetime, timedelta

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


def match_kobo_xls(questions, submission_data):
    config_src = Config().src
    url = config_src['xml_url']
    url = url.replace("/data.xml", ".xml")
    
    res = requests.get(url)
    if not res.status_code == 200:
        raise Exception('Something went wrong')
    
    instance_kobo_form = ET.fromstring(res.text)
    uid = submission_data["asset_uid"]
    start = instance_kobo_form.find(".//{uid}}")
    end = instance_kobo_form.find(".//meta")

    num_kobo_questions = instance_kobo_form[instance_kobo_form.index(start) + 1:instance_kobo_form.index(end)].count('*')
    num_xls_questions = len(questions)

    #all kobo forms have <start> and <end>
    num_kobo_questions = num_kobo_questions - 2

    #Timestamp in google forms is equivalent to start in kobo, and is recorded
    # for each submission 
    if "start" in questions or "Timestamp" in questions:
        num_kobo_questions += 1
    
    if "end"  in questions: 
        num_kobo_questions += 1
    
    #TODO 
    #WHAT ABOUT GROUPS HERE? 
    # CHECK IF THAT AFFECTS ANYTHING ^^^
    if num_kobo_questions != num_xls_questions: 
        print("Warning: Number of questions in Kobo Form, and imported data may not match.")
    

    #s.lower().strip(string.punctuation).strip()
    
    #kobo questions = numkobo
    #subtract two from this because theres obviously going to be a start and end

    #num questions = question
    #if there is a start (add + num1 to numkobo)
    #if there is an end (add + num1 to numkobo)
    
    #check if there is a timestamp 
    #since this is equivalent to start
    #add num1 to kobo

    #lowercase everything
    #strip all punctuation except white spaces


def group_element(_uid, group, cell_value):
    group_name = group.split("/")
    element = _uid.find('.//' + group_name[0])
    if (element == None):
        element = ET.SubElement(_uid, group_name[0])
    if (group_name[0] != group_name[1]):
        group_element = ET.SubElement(element, group_name[1])
        group_element.text = str(cell_value)
    return _uid


def repeat_groups(submission_xml, uuid, file_path): 
        uuid = uuid[len("uuid:"):]
        workbook = openpyxl.load_workbook(file_path)

        sheet_names = workbook.sheetnames
        sheet_names = sheet_names[1:]
        for sheet_name in sheet_names:
            sheet = workbook[sheet_name]
            headers = [cell.value for cell in sheet[1]]

            submission_uid_header = headers.index("_submission__uuid")
   
            for row in sheet.iter_rows(min_row=2, values_only=True):
                #get the submission id for that row
                submission_uid = str(row[submission_uid_header])

                if (submission_uid == uuid):
                     element = ET.SubElement(submission_xml, sheet_name)

                for col_num, cell_value in enumerate(row, start=1):
                    col_name = headers[col_num-1]
                    group_arr = col_name.split('/')

                    if len(group_arr) == 2 and sheet_name in col_name:
                        if (submission_uid == uuid): 
                            group_element = ET.SubElement(element, group_arr[1])
                            group_element.text = cell_value
        
            return submission_xml 

def general_xls_to_xml(excel_file_path, xml_file_path, submission_data, gtransfer = False):
    try: 
        workbook = openpyxl.load_workbook(excel_file_path)
    except FileNotFoundError:
        print(f"⚠️ Error: Excel file not found at path '{excel_file_path}'.")
    except openpyxl.utils.exceptions.InvalidFileException:
        print(f"⚠️ Error: Invalid file format for '{excel_file_path}'")
    except TypeError as e: 
        if "NoneType" in str(e):
            print(f"⚠️ Error: File path is None. Specify xls file path with flag -ef")
    except Exception as e:
        print(f"⚠️ Something went wrong when reading xlsx file: {e}")

    sheet = workbook.active

    uid = submission_data["asset_uid"]
    formhubuuid = submission_data["formhub_uuid"]
    v = submission_data["version"]
    __version__ = submission_data["__version__"]

    root = ET.Element("root") 
    results = ET.Element("results")
   
    headers = [cell.value for cell in sheet[1]]
    
    if (gtransfer):
        for i in range(len(headers)): 
            if (headers[i] == "Timestamp"): 
                headers[i] = "end"
            headers[i] =  headers[i].rstrip(string.punctuation)
            headers[i] = headers[i].replace(" ", "_")
    
   # match_kobo_xls(headers, submission_data)

    num_results = 0

    NSMAP = {"xmlns:jr" :  'http://openrosa.org/javarosa',
         "xmlns:orx" : 'http://openrosa.org/xforms', 
         "id" : str(uid),
         "version" : str(v)}


    for row_num, row in enumerate(sheet.iter_rows(min_row=2, values_only=True,), start=2):
        # create formhub element with nested uuid
        _uid = ET.Element(uid, NSMAP)
        fhub_el = ET.SubElement(_uid, "formhub") 
        uuid_el = ET.SubElement(fhub_el, "uuid") 
        uuid_el.text = formhubuuid

        formatted_uuid = "uuid:"

        if (gtransfer):
            #start element empty
            start_element = ET.Element("start")
            _uid.append(start_element)

        all_empty = True
        # Iterate through cells in the row and create corresponding XML elements
        for col_num, cell_value in enumerate(row, start=1):
                col_name = headers[col_num-1]

                #if (gtransfer and col_name == "end"): 
                 #       cell_element.text = format_timestamp(str(cell_value))
                
                if (gtransfer):
                    #multiple select question responses from google forms will only show up in kobo
                    #when selected choices are seperated by a space, and all lower case. 
                    cell_value = str(cell_value).lower()   
                    cell_value = str(cell_value).replace(",", " ")

                    cell_value = format_time(str(cell_value))
                    cell_value = format_date(cell_value)

                if cell_value is None or cell_value == "none":  
                    cell_value = ""
                else:
                    all_empty = False
        
                if (col_name == "_uuid"):
                    if cell_value == "":
                        formatted_uuid = formatted_uuid + generate_new_instance_id()[1]
                    else:
                        formatted_uuid = formatted_uuid + str(cell_value)
                
                group_arr = col_name.split('/')
                if len(group_arr) == 2:
                    #create new element for ranking question type
                    _uid = group_element(_uid, str(col_name), str(cell_value))
                    continue

                if not (col_name.startswith("_")): 
                    cell_element = ET.SubElement(_uid, col_name)

                    if (col_name == "end" or col_name == "start"):
                        if (gtransfer):
                            cell_value = format_timestamp(str(cell_value))
                        elif (cell_value != ""):
                            cell_value = cell_value.isoformat()
                        
                
                    cell_element.text = str(cell_value)
                    
        if (all_empty): #TODO
            print("Warning: Data may include one or more blank responses where no questions were answered.")
        
        repeat_groups(_uid, formatted_uuid, excel_file_path)

        version = ET.Element("__version__")
        version.text = (__version__)
        _uid.append(version)

        """meta tag before this ends
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
    
        rename_media_folder(submission_data, formatted_uuid[len("uuid:"):], row_num)
        
        _uid.append(meta)

        results.append(_uid)
        
        num_results += 1
    

    count =  ET.SubElement(root, 'count')
    count.text = (str(num_results))

    next = ET.SubElement(root, 'next')
    next.text = None #TODO

    previous = ET.SubElement(root, 'previous')
    previous.text = None #TODO

    root.append(results)

    tree = ET.ElementTree(root)

    #tree.write(xml_file_path) #for testing purposes

    workbook.close()

    return root

