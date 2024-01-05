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


def google_xls_to_xml(excel_file_path, xml_file_path, submission_data):
    # Load the Excel workbook
    workbook = openpyxl.load_workbook(excel_file_path)

    # Select the default sheet (usually named 'Sheet1')
    sheet = workbook.active

    uid = submission_data["asset_uid"]
    formhubuuid = submission_data["formhub_uuid"]
    v = submission_data["version"]
    __version__ = submission_data["__version__"]

    root = ET.Element("root") # Create the root element for the XML tree
    results = ET.Element("results")
   
    headers = [cell.value for cell in sheet[1]]
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

    # Iterate through rows and columns to populate XML
    for row in sheet.iter_rows(min_row=2, values_only=True):
         # create formhub element with nested uuid
        _uid = ET.Element(uid, NSMAP)
        fhub_el = ET.SubElement(_uid, "formhub") 
        uuid_el = ET.SubElement(fhub_el, "uuid") 
        uuid_el.text = formhubuuid

        #start element empty
        start_element = ET.Element("start")
        _uid.append(start_element)

        # Iterate through cells in the row and create corresponding XML elements
        for col_num, cell_value in enumerate(row, start=1):
                col_name = headers[col_num-1]
                cell_element = ET.SubElement(_uid, col_name)

                if (col_name == "end"): 
                    cell_element.text = format_timestamp(str(cell_value))
                else: 
                    if str(cell_value) == 'None': 
                        cell_value = ""
        
                    cell_value = str(cell_value).lower()
                   
                    #multiple select question respones seperated by , in google
                    cell_value = cell_value.replace(",", " ")
                    cell_value = format_time(str(cell_value))
                    cell_value = format_date(cell_value)
                    cell_element.text = cell_value

        version = ET.Element("__version__")
        version.text = (__version__)
        _uid.append(version)

        """meta tag before this ends
          <meta>
                <instanceID>uuid:a0ea37ef-ac71-434b-93b6-1713ef4c367f</instanceID>
            </meta>
        }"""
        meta = ET.Element("meta")
        instanceId = ET.SubElement(meta, "instanceID") 
        _uuid, formatted_uuid = generate_new_instance_id()
        instanceId.text = formatted_uuid
        
        _uid.append(meta)

        results.append(_uid)
        
        num_results += 1

    meta = ET.Element("meta")
    instanceId = ET.SubElement(meta, "instanceID") 
    _uuid, formatted_uuid = generate_new_instance_id()
    instanceId.text = formatted_uuid
        
    _uid.append(meta)

    results.append(_uid)

    count =  ET.SubElement(root, 'count')
    count.text = (str(num_results))

    next = ET.SubElement(root, 'next')
    next.text = ("None") #TODO

    previous = ET.SubElement(root, 'previous')
    previous.text = ("None") #TODO

    root.append(results)

    tree = ET.ElementTree(root)

 #   tree.write(xml_file_path) for testing purposes

    workbook.close()
    return root


def group_element(_uid, group, cell_value):
    #print("group" + group)
    group_name = group.split("/")
    #print("Group name: " + group_name[0] + group_name[1])
    element = _uid.find('.//' + group_name[0])
    #print(element)
    if (element == None):
        element = ET.SubElement(_uid, group_name[0])
    group_element = ET.SubElement(element, group_name[1])
    
    group_element.text = cell_value
    return _uid

#TODO: ideally would combine the two methods
def general_xls_to_xml(excel_file_path, xml_file_path, submission_data):
    workbook = openpyxl.load_workbook(excel_file_path)

    #select default sheet
    sheet = workbook.active

    uid = submission_data["asset_uid"]
    formhubuuid = submission_data["formhub_uuid"]
    v = submission_data["version"]
    __version__ = submission_data["__version__"]

    root = ET.Element("root") # Create the root element for the XML tree
    results = ET.Element("results")
   
    headers = [cell.value for cell in sheet[1]]

    num_results = 0

    NSMAP = {"xmlns:jr" :  'http://openrosa.org/javarosa',
         "xmlns:orx" : 'http://openrosa.org/xforms', 
         "id" : str(uid),
         "version" : str(v)}

    # Iterate through rows and columns to populate XML
    for row in sheet.iter_rows(min_row=2, values_only=True):
        # create formhub element with nested uuid
        _uid = ET.Element(uid, NSMAP)
        fhub_el = ET.SubElement(_uid, "formhub") 
        uuid_el = ET.SubElement(fhub_el, "uuid") 
        uuid_el.text = formhubuuid

        formatted_uuid = "uuid:"

        # Iterate through cells in the row and create corresponding XML elements
        for col_num, cell_value in enumerate(row, start=1):
                col_name = headers[col_num-1]
        
                if (col_name == "_uuid"):
                    if cell_value == None:
                       formatted_uuid = formatted_uuid + generate_new_instance_id()[1]
                    else:
                        formatted_uuid = formatted_uuid + str(cell_value)
            
                #TODO HOW TO FIX SUBMITTED_BY
                
                group_arr = col_name.split('/')
                if (len(group_arr) == 2) and group_arr[0] == group_arr[1]:
                    #create new element for ranking question
                    _uid = group_element(_uid, str(col_name), str(cell_value))
                    continue

                #create new element for group question, or add to group
                #add to ranking question with choice element
                if (col_name.startswith("group_") or col_name.endswith("_choice")):
                    _uid = group_element(_uid, str(col_name), str(cell_value))
                    continue

                if not (col_name.startswith("_")): 
                    cell_element = ET.SubElement(_uid, col_name)

                    if (col_name == "end" or col_name == "start"):
                        if (cell_value != None):
                            cell_value = cell_value.isoformat()
                
                    cell_element.text = str(cell_value)
                    

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
        instanceId = ET.SubElement(meta, "instanceID") 
        deprecatedId = ET.SubElement(meta, "deprecatedID")

        instanceId.text = formatted_uuid
        deprecatedId.text = formatted_uuid
        
        _uid.append(meta)

        results.append(_uid)
        
        num_results += 1
    

    count =  ET.SubElement(root, 'count')
    count.text = (str(num_results))

    next = ET.SubElement(root, 'next')

    #next.text = submission_data["next"] #TODO

    previous = ET.SubElement(root, 'previous')
    #previous.text = submission_data["previous"] #TODO

    root.append(results)

    tree = ET.ElementTree(root)

    tree.write(xml_file_path) #for testing purposes

    workbook.close()
    return root

