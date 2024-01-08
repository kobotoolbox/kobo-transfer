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
from utils.text import get_valid_filename


import openpyxl
import xml.etree.ElementTree as ET

import pandas as pd
from datetime import datetime, timedelta
import pytz
from dateutil import parser

from .media import get_media, del_media
from helpers.config import Config

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

#next 3 methods from #15
def get_all_values_from_xml(elem):
    '''
    Return a list of all the values in the submission's XML
    '''
    values = []
    for child in elem:
        values.extend(get_all_values_from_xml(child))
    if elem.text:
        values.append(elem.text.strip())
    return [v for v in values if v]


def get_xml_value_media_mapping(values):
    '''
    Return a mapping of the filename as it's stored and the submission value
    as it's sent. We need this to link the two together again for when filenames
    are stripped of special characters.
    '''
    return {get_valid_filename(v):v for v in values}


def submit_data(xml_sub, _uuid, original_uuid, xml_value_media_map):
    config = Config().dest

    file_tuple = (_uuid, io.BytesIO(xml_sub))
    files = {'xml_submission_file': file_tuple}

    # see if there is media to upload with it
    submission_attachments_path = os.path.join(
        Config.ATTACHMENTS_DIR, Config().src['asset_uid'], original_uuid, '*'
    )
    for file_path in glob.glob(submission_attachments_path):
        filename = os.path.basename(file_path)
        filename_value = xml_value_media_map.get(filename)
        files[filename_value] = (filename_value, open(file_path, 'rb'))

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

        submission_values = get_all_values_from_xml(submission_xml)
        xml_value_media_map = get_xml_value_media_mapping(submission_values)

        result = submit_data(
                ET.tostring(submission_xml),
                _uuid,
                original_uuid,
                xml_value_media_map,
            )
        
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
