import glob
import string
import io
import json
import os
import requests
import uuid
from datetime import datetime
from xml.etree import ElementTree as ET
from dateutil.parser import ParserError
import re
import gdown


import openpyxl
import xml.etree.ElementTree as ET

import pandas as pd
from datetime import datetime, timedelta
import pytz
from dateutil import parser

from .media import get_media, del_media
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

def get_submission_edit_data():
    config = Config().dest
    _v_, v = get_info_from_deployed_versions()
    data = {
        'asset_uid': config['asset_uid'],
        'version': v,
        '__version__': _v_,
        'formhub_uuid': get_formhub_uuid(),
    }
    return data


def get_src_submissions_xml(xml_url):
    config = Config().src
    res = requests.get(
        url=xml_url, headers=config['headers'], params=config['params']
    )
    if not res.status_code == 200:
        raise Exception('Something went wrong')
    return ET.fromstring(res.text)


def submit_data_test(xml_sub, _uuid, original_uuid):
     #TODO
    config = Config().dest

    file_tuple = (_uuid, io.BytesIO(xml_sub))
    files = {'xml_submission_file': file_tuple}

    # see if there is media to upload with it
    submission_attachments_path = "/Users/dyaqub/git/kobo-transfer/attachments/testmedia/*"
    for file_path in glob.glob(submission_attachments_path):
        filename = os.path.basename(file_path)
        files[filename] = (filename, open(file_path, 'rb'))

    res = requests.Request(
        method='POST',
        url=config['submission_url'],
        files=files,
        headers=config['headers'],
    )
    session = requests.Session()
    res = session.send(res.prepare())
    return res.status_code

#TODO
#bottom half is repeat of submit_data 
#jsut trying to link it to the config file
def upload_google_media(xml_sub, _uuid, original_uuid):
    file_tuple = (_uuid, io.BytesIO(xml_sub))
    files = {'xml_submission_file': file_tuple}

    config = Config().dest
    q_links = config["question_link"]

    for item in q_links:
        for question in item:
            drive_link = item[question]
            gdown.download_folder(drive_link, quiet=True, use_cookies=False)

            #submission_attachments_path = "./{question}/*"
            submission_attachments_path = "/Users/dyaqub/git/kobo-transfer/attachments/testmedia/*"
            for file_path in glob.glob(submission_attachments_path):
                 filename = os.path.basename(file_path)
                 print(filename, open(file_path, 'rb'))

    res = requests.Request(
        method='POST',
        url=config['submission_url'],
        files=files,
        headers=config['headers'],
    )

    session = requests.Session()
    res = session.send(res.prepare())
    return res.status_code


def submit_data(xml_sub, _uuid, original_uuid):
    config = Config().dest

    file_tuple = (_uuid, io.BytesIO(xml_sub))
    files = {'xml_submission_file': file_tuple}

    # see if there is media to upload with it
    submission_attachments_path = os.path.join(
        Config.ATTACHMENTS_DIR, Config().src['asset_uid'], original_uuid, '*'
    )
    for file_path in glob.glob(submission_attachments_path):
        filename = os.path.basename(file_path)
        files[filename] = (filename, open(file_path, 'rb'))

    res = requests.Request(
        method='POST',
        url=config['submission_url'],
        files=files,
        headers=config['headers'],
    )
    session = requests.Session()
    res = session.send(res.prepare())
    return res.status_code


def update_element_value(e, name, value):
    """
    Get or create a node and give it a value, even if nested within a group
    """
    el = e.find(name)
    if el is None:
        if '/' in name:
            root, node = name.split('/')
            el = ET.SubElement(e.find(root), node)
        else:
            el = ET.SubElement(e, name)
    el.text = value


def update_root_element_tag_and_attrib(e, tag, attrib):
    """
    Update the root of each submission's XML tree
    """
    e.tag = tag
    e.attrib = attrib


def generate_new_instance_id() -> (str, str):
    """
    Returns:
        - Generated uuid
        - Formatted uuid for OpenRosa xml
    """
    _uuid = str(uuid.uuid4())
    return _uuid, f'uuid:{_uuid}'


def transfer_submissions(all_submissions_xml, asset_data, quiet, regenerate):
    results = []
    for submission_xml in all_submissions_xml:

        # Use the same UUID so that duplicates are rejected
        #TODO currently this is not working for me
        # i think this makes sense because uuid is regenerated every time.. 
        #how do i make it so that its not... 

        original_uuid = submission_xml.find('meta/instanceID').text.replace(
            'uuid:', ''
        )
        if regenerate:
            _uuid, formatted_uuid = generate_new_instance_id()
            submission_xml.find('meta/instanceID').text = formatted_uuid
        else:
            _uuid = original_uuid

        new_attrib = {
            'id': asset_data['asset_uid'],
            'version': asset_data['version'],
        }
        update_root_element_tag_and_attrib(
            submission_xml, asset_data['asset_uid'], new_attrib
        )
        update_element_value(
            submission_xml, '__version__', asset_data['__version__']
        )
        update_element_value(
            submission_xml, 'formhub/uuid', asset_data['formhub_uuid']
        )

        #TODO, add a condition where this is only for google transfer
        #if final in all_submissions_xml, it is empty, and only used to upload all attachments
       # if (submission_xml == all_submissions_xml[-1]):
        #    uploaded = upload_google_media(ET.tostring(submission_xml), _uuid, original_uuid)
         #   if (uploaded != 201 and uploaded != 202):
          #      log_failure("upload all media from google drive folder failed")
      #  else: 
        result = submit_data_test(ET.tostring(submission_xml), _uuid, original_uuid)

        if result == 201:
            msg = f'✅ {_uuid}'
        elif result == 202:
            msg = f'⚠️  {_uuid}'
        else:
            msg = f'❌ {_uuid}'
            log_failure(_uuid)
        if not quiet:
            print(msg)
        results.append(result)
    
    #TODO
    #when you do submit_data_test, it's doing it for every submission in all_submissions
    #need to create extra submission and call it the submit_data_test( specifically for attachemnts) at the end

    return results


def log_failure(_uuid):
    with open(Config.FAILURES_LOCATION, 'a') as f:
        f.write(f'{_uuid}\n')


def get_formhub_uuid():
    config = Config().dest
    res = requests.get(
        url=config['forms_url'],
        headers=config['headers'],
        params=config['params'],
    )
    if not res.status_code == 200:
        raise Exception('Something went wrong')
    all_forms = res.json()
    latest_form = [
        f for f in all_forms if f['id_string'] == config['asset_uid']
    ][0]
    return latest_form['uuid']


def get_deployed_versions():
    config = Config().dest
    res = requests.get(
        url=config['asset_url'],
        headers=config['headers'],
        params=config['params'],
    )
    if not res.status_code == 200:
        raise Exception('Something went wrong')
    data = res.json()
    return data['deployed_versions']


def format_date_string(date_str):
    """
    Format goal: "1 (2021-03-29 19:40:28)"
    """
    date, time = date_str.split('T')
    return f"{date} {time.split('.')[0]}"


def get_info_from_deployed_versions():
    """
    Get the version formats
    """
    deployed_versions = get_deployed_versions()
    count = deployed_versions['count']

    latest_deployment = deployed_versions['results'][0]
    date = latest_deployment['date_deployed']
    version = latest_deployment['uid']

    return version, f'{count} ({format_date_string(date)})'


def print_stats(results):
    total = len(results)
    success = results.count(201)
    skip = results.count(202)
    fail = total - success - skip
    print(f'🧮 {total}\t✅ {success}\t⚠️ {skip}\t❌ {fail}')
