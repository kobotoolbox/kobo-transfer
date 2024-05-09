#!/usr/bin/env python3

import argparse
import json
import sys
import requests

from helpers.config import Config
from transfer.media import get_media, del_media
from transfer.xml import (
    get_src_submissions_xml,
    get_submission_edit_data,
    print_stats,
    transfer_submissions,
)


def get_uuids(config_loc, params):
    def get_uuids_rec(uuids=[], url=None, params=None, headers=None):
        if 'fields' not in url:
            res = requests.get(
                url=url,
                params=params,
                headers=headers
        )
        else:
            res = requests.get(url=url, headers=headers)
        data = res.json()
        uuids += [i['_uuid'] for i in data['results']]
        next_ = data['next']
        if next_ is not None:
            get_uuids_rec(uuids, next_, headers=headers)

    uuids = []
    get_uuids_rec(uuids=uuids, url=config_loc['data_url'], params=params, headers=config_loc['headers'])
    return uuids


def chunker(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def get_params(uuids=[], limit=10000, fields=[]):
    query = json.dumps({"_uuid": {"$in": uuids}})
    res = {
        'format': 'json',
        'limit': limit,
        'fields': json.dumps(fields),
    }
    if uuids:
        res['query'] = query
    return res


def get_diff_uuids(config):
    # TODO: make limit dynamic
    params = get_params(fields=['_uuid'], limit=1000)
    src_uuids = get_uuids(config_loc=config.src, params=params)
    dest_uuids = get_uuids(config_loc=config.dest, params=params)

    return list(set(src_uuids).difference(set(dest_uuids)))


def main(
    limit,
    last_failed=False,
    keep_media=False,
    regenerate=False,
    quiet=False,
    validate=True,
    sync=False,
    chunk_size=100,
    config_file=None,
    skip_media=False,
):
    config = Config(config_file=config_file, validate=validate)
    config_src = config.src
    all_results = []
    submission_edit_data = get_submission_edit_data()

    def transfer(all_results, url=None):
        parsed_xml = get_src_submissions_xml(xml_url=url)
        submissions = parsed_xml.findall(f'results/')
        next_ = parsed_xml.find('next').text
        results = transfer_submissions(
            submissions,
            submission_edit_data,
            quiet=quiet,
            regenerate=regenerate,
        )
        all_results += results

        if next_ != 'None' and next_ is not None:
            transfer(all_results, next_)

    xml_url_src = config_src['xml_url'] + f'?limit={limit}'

    if last_failed and config.last_failed_uuids:
        xml_url_src += f'&query={json.dumps(config.data_query)}'

    if sync:
        print('🪪 Getting _uuid values from src and dest projects')
        diff_uuids = get_diff_uuids(config)

        if not diff_uuids:
            print('👌 Projects are in-sync')
            sys.exit()

        # run through chunks of uuids
        first_run = True
        for chunked_uuids in chunker(diff_uuids, chunk_size):
            query = json.dumps({"_uuid": {"$in": chunked_uuids}})
            xml_url_src = config_src['xml_url'] + f'?limit={limit}&query={query}'

            if not skip_media:
                if first_run:
                    print('📸 Getting all submission media', end=' ', flush=True)
                get_media(query=query)

            if first_run:
                print('📨 Transferring submission data')
                first_run = False
            transfer(all_results, xml_url_src)


    if not sync:
        if not skip_media:
            print('📸 Getting all submission media', end=' ', flush=True)
            get_media()

        print('📨 Transferring submission data')
        transfer(all_results, xml_url_src)

    if not keep_media and not skip_media:
        del_media()

    print('✨ Done')
    print_stats(all_results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='A CLI tool to transfer submissions between projects with identical XLSForms.'
    )
    parser.add_argument(
        '--limit',
        '-l',
        default=5000,
        type=int,
        help='Number of submissions included in each batch for download and upload.',
    )
    parser.add_argument(
        '--last-failed',
        '-lf',
        default=False,
        action='store_true',
        help='Run transfer again with only last failed submissions.',
    )
    parser.add_argument(
        '--config-file',
        '-c',
        default='config.json',
        type=str,
        help='Location of config file.',
    )
    parser.add_argument(
        '--regenerate-uuids',
        '-R',
        default=False,
        action='store_true',
        help='Regenerate submission UUIDs.',
    )
    parser.add_argument(
        '--no-validate',
        '-N',
        default=False,
        action='store_true',
        help='Skip validation of config file.',
    )
    parser.add_argument(
        '--keep-media',
        '-k',
        default=False,
        action='store_true',
        help='Keep submission attachments rather than cleaning up after transfer.',
    )
    parser.add_argument(
        '--sync',
        '-s',
        default=False,
        action='store_true',
        help='Sync src and dest project data',
    )
    parser.add_argument(
        '--chunk-size',
        '-cs',
        default=20,
        type=int,
        help='Number of submissions included in each batch for sync query filters.',
    )
    parser.add_argument(
        '--skip-media',
        '-sm',
        default=False,
        action='store_true',
        help='Skip media downloads',
    )
    parser.add_argument(
        '--quiet',
        '-q',
        default=False,
        action='store_true',
        help='Suppress stdout',
    )
    args = parser.parse_args()

    try:
        main(
            limit=args.limit,
            last_failed=args.last_failed,
            regenerate=args.regenerate_uuids,
            keep_media=args.keep_media,
            quiet=args.quiet,
            validate=not args.no_validate,
            sync=args.sync,
            chunk_size=args.chunk_size,
            config_file=args.config_file,
            skip_media=args.skip_media,
        )
    except KeyboardInterrupt:
        print('🛑 Stopping run')
        # Do something here so we can pick up again where this leaves off
        sys.exit()
