import glob
import string
import io
import os
import requests

from datetime import datetime
from xml.etree import ElementTree as ET
from dateutil.parser import ParserError
import re
import gdown
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


def xls_to_xml(excel_file_path, xml_file_path, submission_data):
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
    
    #create an extra submission which is blank but only needed to upload ALL attachments
    #how are you going to get the folder tho, i think you need to specify in the config file tbh
    # create formhub element with nested uuid
    _uid = ET.Element(uid, NSMAP)
    fhub_el = ET.SubElement(_uid, "formhub") 
    uuid_el = ET.SubElement(fhub_el, "uuid") 
    uuid_el.text = formhubuuid

    #start element empty
    start_element = ET.Element("start")
    _uid.append(start_element)

    #each response to question should be blank
    for col_num, cell_value in enumerate(row, start=1):
            col_name = headers[col_num-1]
            cell_element = ET.SubElement(_uid, col_name)
            cell_element.text = ("")
            
    version = ET.Element("__version__")
    version.text = (__version__)
    _uid.append(version)


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