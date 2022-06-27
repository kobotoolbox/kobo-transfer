#!/usr/bin/env python3

import argparse
import json
import os
import pathlib
import re
import requests
import time

KOBO_CONF = 'config.json'
REWRITE_DOWNLOAD_URL = True
TMP_DIR = '/tmp'


def download_all_media(data_url, stats, *args, **kwargs):

    data_res = requests.get(
        data_url, headers=kwargs['headers'], params=kwargs['params']
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
        media_filenames = [
            sub.get(name) for name in kwargs.get('question_names', '').split(',')
        ]
        media_filenames = [
            get_valid_filename(name)
            for name in media_filenames
            if name is not None
        ]

        if not attachments:
            continue

        sub_dir = os.path.join(TMP_DIR, kwargs['asset_uid'], sub['_uuid'])
        if not os.path.isdir(sub_dir):
            os.makedirs(sub_dir)

        for attachment in attachments:
            download_url = attachment['filename']
            if REWRITE_DOWNLOAD_URL:
                download_url = rewrite_download_url(
                    download_url, kwargs['kc_url']
                )
            filename = get_filename(attachment['filename'])

            if kwargs.get('question_names', '') and filename not in media_filenames:
                continue

            file_path = os.path.join(sub_dir, filename)
            if os.path.exists(file_path):
                if kwargs['verbosity'] == 3:
                    print(f'File already exists, skipping: {file_path}')
                stats['skipped'] += 1
                continue
            download_media_file(
                url=download_url, path=file_path, stats=stats, *args, **kwargs
            )

    if next_url is not None:
        download_all_media(data_url=next_url, stats=stats, *args, **kwargs)

    return stats


def download_media_file(url, path, stats, headers, chunk_size, *args, **kwargs):
    stream_res = requests.get(url, stream=True, headers=headers)
    if stream_res.status_code != 200:
        if kwargs['verbosity'] == 3:
            print(f'Fail: {path}')
        stats['failed'] += 1
        return stats

    with open(path, 'wb') as f:
        for chunk in stream_res.iter_content(chunk_size):
            f.write(chunk)

    if kwargs['verbosity'] == 3:
        print(f'Success: {path}')
    stats['successful'] += 1

    time.sleep(kwargs['throttle'])

    return stats


def get_clean_stats():
    return {'successful': 0, 'failed': 0, 'skipped': 0}


def get_config():
    conf_path = os.path.join(pathlib.Path(__file__).resolve().parent, KOBO_CONF)
    with open(conf_path, 'r') as f:
        settings = json.loads(f.read())
    return settings['old']


def get_data_url(asset_uid, kf_url):
    return f'{kf_url}/api/v2/assets/{asset_uid}/data'


def get_filename(path):
    return path.split('/')[-1]


def get_params(limit=100, query='', *args, **kwargs):
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


def get_media(verbosity=0, *args, **kwargs):
    settings = get_config()
    options = {
        'params': get_params(*args, **kwargs),
        'headers': {'Authorization': f'Token {settings["token"]}'},
        'verbosity': verbosity,
        'chunk_size': 1024,
        'throttle': 0.1,
    }
    data_url = get_data_url(settings['asset_uid'], settings['kf_url'])
    stats = download_all_media(
        data_url,
        stats=get_clean_stats(),
        **options,
        **settings,
    )
    #if verbosity > 1:
    #    print(json.dumps(stats, indent=2))
