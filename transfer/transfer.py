import glob
import os
import io
import json
import requests
import uuid
from datetime import datetime
from xml.etree import ElementTree as ET

from .download_media import get_media


def get_config():
    with open('transfer/config.json', 'r') as f:
        data = json.loads(f.read())
    append_additional_config_data(data)
    return flatten_config(data)


def flatten_config(config_data):
    data = {}
    for k, v in config_data.items():
        for kk, vv in v.items():
            data[f'{kk}_{k}'] = vv
    return data


def append_additional_config_data(data):
    for k, v in data.items():
        asset_url = f"{v['kf_url']}/api/v2/assets/{v['asset_uid']}"
        v.update(
            {
                'assets_url': asset_url,
                'submission_url': f"{v['kc_url']}/api/v1/submissions",
                'forms_url': f"{v['kc_url']}/api/v1/forms",
                'headers': {'Authorization': f"Token {v['token']}"},
                'params': {'format': 'json'},
                'deployment_url': f'{asset_url}/deployment/',
                'xml_url': f'{asset_url}/data.xml',
                'data_url': f'{asset_url}/data',
            }
        )


def get_submission_edit_data(asset_uid_new, *args, **kwargs):
    _v_, v = get_info_from_deployed_versions(*args, **kwargs)
    data = {
        'asset_uid': asset_uid_new,
        'version': v,
        '__version__': _v_,
        'formhub_uuid': get_formhub_uuid(asset_uid_new, *args, **kwargs),
    }
    return data


def get_old_submissions_xml(
    xml_url_old, asset_uid_old, headers_old, params_old, *args, **kwargs
):
    res = requests.get(url=xml_url_old, headers=headers_old, params=params_old)
    if not res.status_code == 200:
        raise Exception('Something went wrong')
    return ET.fromstring(res.text)


def submit_data(
    xml_sub, _uuid, asset_uid_old, submission_url_new, headers_new, *args, **kwargs
):
    """
    Send the XML to kobo!
    """
    file_tuple = (_uuid, io.BytesIO(xml_sub))
    files = {'xml_submission_file': file_tuple}

    # see if there is media to upload with it
    TMP_DIR = '/tmp'
    submission_attachments_path = os.path.join(TMP_DIR, asset_uid_old, _uuid.replace('uuid:',''), '*')
    for file_path in glob.glob(submission_attachments_path):
        filename = os.path.basename(file_path)
        files[filename] = (filename, open(file_path, 'rb'))

    res = requests.Request(
        method='POST', url=submission_url_new, files=files, headers=headers_new
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


def transfer_submissions(
    all_submissions_xml, asset_data, quiet, *args, **kwargs
):
    results = []
    for submission_xml in all_submissions_xml:
        # Use the same UUID so that duplicates are rejected
        _uuid = submission_xml.find('meta/instanceID').text

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

        result = submit_data(
            ET.tostring(submission_xml), _uuid, *args, **kwargs
        )
        if not quiet:
            if result == 201:
                print(f'{_uuid}:\tSuccess')
            elif result == 202:
                print(f'{_uuid}:\tSkip, UUID exists')
            else:
                print(f'{_uuid}:\tFail')
        results.append(result)
    return results


def get_formhub_uuid(
    asset_uid_new, headers_new, params_new, forms_url_new, *args, **kwargs
):
    res = requests.get(
        url=forms_url_new, headers=headers_new, params=params_new
    )
    if not res.status_code == 200:
        raise Exception('Something went wrong')
    all_forms = res.json()
    latest_form = [f for f in all_forms if f['id_string'] == asset_uid_new][0]
    return latest_form['uuid']


def get_deployed_versions(
    assets_url_new, headers_new, params_new, *args, **kwargs
):
    res = requests.get(
        url=assets_url_new, headers=headers_new, params=params_new
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


def get_info_from_deployed_versions(*args, **kwargs):
    """
    Get the version formats
    """
    deployed_versions = get_deployed_versions(*args, **kwargs)
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
    print(
        f'Total attempts: {total}\tTransferred: {success}\tSkipped: {skip}\tFailed: {fail}'
    )


def main(limit, quiet=False):
    config = get_config()
    config.update(
        {
            'quiet': quiet,
        }
    )

    print('Getting all submission media if it exists')
    get_media()

    xml_url_old = config.pop('xml_url_old') + f'?limit={limit}'
    all_results = []
    submission_edit_data = get_submission_edit_data(**config)

    print('Transferring submission data')
    def do_the_stuff(all_results, url=None):
        parsed_xml = get_old_submissions_xml(xml_url_old=url, **config)
        submissions = parsed_xml.findall(f'results/{config["asset_uid_old"]}')
        next_ = parsed_xml.find('next').text
        results = transfer_submissions(
            submissions, submission_edit_data, **config
        )
        all_results += results
        if next_ != 'None':
            do_the_stuff(all_results, next_)

    do_the_stuff(all_results, xml_url_old)

    print_stats(all_results)
