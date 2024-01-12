import argparse
import json
import os
import pathlib
import re
import requests
import shutil
import sys
import time

from helpers.config import Config


import os
import shutil



def rename_media_folder(submission_data, uuid, rowNum):
    current_attachments_path = os.path.join(
        Config.ATTACHMENTS_DIR, submission_data['asset_uid'], str(rowNum)
    )
    if (os.path.exists(current_attachments_path)):   
        new_attachments_path = os.path.join(
            Config.ATTACHMENTS_DIR, submission_data['asset_uid'], str(uuid)
        )
        print(current_attachments_path)
        
        try:
            # Move the folder to the new path
            shutil.move(current_attachments_path, new_attachments_path)

        except Exception as e: #TODO
            print(f"Error: {e}")

def del_media():
    config = Config().src
    media_path = os.path.join(Config.ATTACHMENTS_DIR, config['asset_uid'])
    if os.path.exists(media_path):
        print('🧹 Cleaning up media (pass `--keep-media` to prevent cleanup).')
        shutil.rmtree(media_path)

def get_media(verbosity=0, chunk_size=1024, throttle=0.1, limit=1000, query=''):
    config = Config().src
    config.update(
        {
            'params': get_params(limit=limit, query=query),
            'verbosity': verbosity,
            'chunk_size': chunk_size,
            'throttle': throttle,
        }
    )
   
    stats = download_all_media(
       data_url=config['data_url'],
       stats=get_clean_stats(),
    )


def download_all_media(data_url, stats):

    config = Config().src

    data_url = data_url or config['data_url']
    data_res = requests.get(
        data_url, headers=config['headers'], params=config['params']
    )
    if data_res.status_code != 200:
        return stats

    data = data_res.json()
    next_url = data['next']
    results = data['results']

    if not results:
        return stats

    for sub in results:
        attachments = sub.get('_attachments', [])

        if not attachments:
            continue

        sub_dir = os.path.join(
            Config.ATTACHMENTS_DIR, config['asset_uid'], sub['_uuid']
        )
        if not os.path.isdir(sub_dir):
            os.makedirs(sub_dir)

        for attachment in attachments:
            download_url = attachment['filename']
            if Config.REWRITE_DOWNLOAD_URL:
                download_url = rewrite_download_url(
                    download_url, config['kc_url']
                )
            filename = get_filename(attachment['filename'])

            file_path = os.path.join(sub_dir, filename)
            if os.path.exists(file_path):
                if config['verbosity'] == 3:
                    print(f'File already exists, skipping: {file_path}')
                stats['skipped'] += 1
                continue
            download_media_file(url=download_url, path=file_path, stats=stats)
            print('.', end='', flush=True)

    if next_url is not None:
        download_all_media(data_url=next_url, stats=stats)

    print()

    return stats


def download_media_file(url, path, stats):
    config = Config().src
    stream_res = requests.get(url, stream=True, headers=config['headers'])
    if stream_res.status_code != 200:
        if config['verbosity'] == 3:
            print(f'Fail: {path}')
        stats['failed'] += 1
        return stats

    with open(path, 'wb') as f:
        for chunk in stream_res.iter_content(config['chunk_size']):
            f.write(chunk)

    if config['verbosity'] == 3:
        print(f'Success: {path}')
    stats['successful'] += 1

    time.sleep(config['throttle'])

    return stats


def get_clean_stats():
    return {'successful': 0, 'failed': 0, 'skipped': 0}


def get_data_url(asset_uid, kf_url):
    return f'{kf_url}/api/v2/assets/{asset_uid}/data'


def get_filename(path):
    return path.split('/')[-1]


def get_params(limit, query):
    params = {'format': 'json', 'limit': limit}
    if query:
        params['query'] = query
    return params


def get_valid_filename(name):
    s = str(name).strip().replace(' ', '_')
    s = re.sub(r'(?u)[^-\w.]', '', s)
    return s


def rewrite_download_url(filename, kc_url):
    return f'{kc_url}/media/original?media_file={filename}'
