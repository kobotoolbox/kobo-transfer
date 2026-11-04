#!/usr/bin/env python3

import argparse
import json
import os
import sys
import time
import requests

from helpers.config import Config
from transfer.analysis import sync_analysis_data
from transfer.asset import transfer_asset, get_src_asset_details, create_asset
from transfer.media import get_media, del_media
from transfer.xml import (
    get_src_submissions_xml,
    get_stats,
    get_submission_edit_data,
    print_stats,
    transfer_submissions,
)
from transfer.validation_status import sync_validation_statuses
from utils.urls import rebase
from urllib.parse import urlsplit


def chunker(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


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


def get_roots(config_loc):
    """
    {UUID: root UUID} of every submission: the root is the first version's UUID, which
    an edited submission keeps while its `_uuid` changes.
    """
    roots, url = {}, config_loc['data_url']
    params = get_params(fields=['_uuid', 'meta/rootUuid'], limit=1000)
    while url:
        res = requests.get(url, params=params, headers=config_loc['headers'])
        res.raise_for_status()
        data = res.json()
        for sub in data['results']:
            roots[sub['_uuid']] = (sub.get('meta/rootUuid') or sub['_uuid']).replace('uuid:', '')
        url, params = rebase(data['next'], config_loc['kf_url']), None
    return roots


def sent_path(config):
    # Next to failures.txt: what this machine last sent for each root UUID
    return os.path.join(
        Config.LOG_DIR, f"sent-{config.src['asset_uid']}-{config.dest['asset_uid']}.json"
    )


def load_sent(config):
    try:
        with open(sent_path(config)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_sent(config, sent):
    os.makedirs(Config.LOG_DIR, exist_ok=True)
    tmp = sent_path(config) + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(sent, f)
    os.replace(tmp, sent_path(config))


# What the run did, for --summary-file: filled in as it goes, so a run that stops on an
# error still says how far it got
SUMMARY = {}


def describe(e):
    if isinstance(e, requests.HTTPError) and e.response is not None:
        u = urlsplit(e.response.url)
        return f'{e.response.status_code} from {u.netloc} {u.path}'
    if isinstance(e, requests.RequestException):
        return f'{type(e).__name__}: no answer from {urlsplit(e.request.url).netloc if e.request else "the server"}'
    return f'{type(e).__name__}: {e}'


def write_summary(path, summary):
    if not path:
        return
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(summary, f, indent=2)
    os.replace(tmp, path)


def main(
    limit,
    asset=False,
    src_asset_uid=None,
    last_failed=False,
    keep_media=False,
    regenerate=False,
    quiet=False,
    validate=True,
    sync=False,
    validation_statuses=False,
    analysis_data=False,
    chunk_size=100,
    config_file=None,
    skip_media=False,
    summary_file=None,
):
    if src_asset_uid:
        validate = False
    
    config = Config(config_file=config_file, validate=validate, asset=asset)

    if src_asset_uid:
        config.update_config(loc='src', new_data={'asset_uid': src_asset_uid})

    if asset:
        print('📋 Transferring asset, versions and form media')
        asset_setup_content, *_ = get_src_asset_details(config_src=config.src)
        asset_uid = create_asset(config.dest, asset_setup_content)
        print(f'✨ New asset UID at `dest`: {asset_uid}')
        config.update_config(loc='dest', new_data={'asset_uid': asset_uid})
        transfer_asset(config)

    summary = SUMMARY
    summary.update({
        'src': config.src['asset_uid'],
        'dest': config.dest['asset_uid'],
        'started': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    })

    def finish(failed):
        summary['finished'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        summary['ok'] = not failed
        write_summary(summary_file, summary)
        sys.exit(1 if failed else 0)

    if validation_statuses and not sync:
        print('✏️ Syncing validation statuses')
        summary['validation_statuses'] = sync_validation_statuses(config, chunk_size, limit)
        finish(False)

    if analysis_data and not sync:
        print('📶 Syncing analysis data')
        summary['analysis'] = sync_analysis_data(config, limit)
        finish(summary['analysis']['failed'])

    config_src = config.src
    all_results = []
    analysis_failures = 0
    dest_roots = src_roots = sent = None
    submission_edit_data = get_submission_edit_data()

    def transfer(all_results, url=None):
        parsed_xml = get_src_submissions_xml(xml_url=url)
        submissions = parsed_xml.findall(f'results/')
        next_ = parsed_xml.find('next').text
        if next_ not in (None, 'None'):
            next_ = rebase(next_, config_src['kf_url'])
        results = transfer_submissions(
            submissions,
            submission_edit_data,
            quiet=quiet,
            regenerate=regenerate,
            dest_roots=dest_roots,
            src_roots=src_roots,
            sent=sent,
        )
        all_results += results

        if next_ != 'None' and next_ is not None:
            transfer(all_results, next_)

    xml_url_src = config_src['xml_url'] + f'?limit={limit}'

    if last_failed and config.last_failed_uuids:
        xml_url_src += f'&query={json.dumps(config.data_query)}'

    if sync:
        print('🪪 Getting _uuid values from src and dest projects')
        src_roots = get_roots(config.src)
        dest_roots = {root: uuid_ for uuid_, root in get_roots(config.dest).items()}
        sent = load_sent(config)
        diff_uuids = list(set(src_roots).difference(dest_roots.values()))

        if not diff_uuids:
            print('👌 Projects are in-sync')
            if not (validation_statuses or analysis_data):
                summary['submissions'] = get_stats([])
                finish(False)

        # run through chunks of uuids
        first_run = True
        for chunked_uuids in chunker(diff_uuids, chunk_size):
            query = json.dumps({"_uuid": {"$in": chunked_uuids}})
            xml_url_src = (
                config_src['xml_url'] + f'?limit={limit}&query={query}'
            )

            if not skip_media:
                if first_run:
                    print('📸 Getting all submission media', end=' ', flush=True)
                get_media(query=query)

            if first_run:
                print('📨 Transferring submission data')
                first_run = False
            transfer(all_results, xml_url_src)
        save_sent(config, sent)
        summary['submissions'] = get_stats(all_results)

        if validation_statuses:
            print('✏️ Syncing validation statuses')
            summary['validation_statuses'] = sync_validation_statuses(
                config, chunk_size, limit
            )

        if analysis_data:
            print('📶 Syncing analysis data')
            summary['analysis'] = sync_analysis_data(config, limit)
            analysis_failures = summary['analysis']['failed']

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
    summary['submissions'] = get_stats(all_results)
    # Edited on both sides isn't a failure: it waits for a person, and is counted
    finish(analysis_failures or summary['submissions']['failed'])


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
        '--asset',
        '-a',
        default=False,
        action='store_true',
        help='Transfer asset, versions and form media.',
    )
    parser.add_argument(
        '--src-asset-uid',
        '-sau',
        default=None,
        type=str,
        help='Override asset_uid value in config file.',
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
        '--validation-statuses',
        '-vs',
        default=False,
        action='store_true',
        help='Sync src and dest validation statuses',
    )
    parser.add_argument(
        '--analysis-data',
        '-ad',
        default=False,
        action='store_true',
        help='Sync src and dest analysis data (transcript, translations, analysis questions)',
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
        '--summary-file',
        default=None,
        type=str,
        help='Write what was done (counts, failures) to this file as JSON.',
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
            asset=args.asset,
            src_asset_uid=args.src_asset_uid,
            last_failed=args.last_failed,
            regenerate=args.regenerate_uuids,
            keep_media=args.keep_media,
            quiet=args.quiet,
            validate=not args.no_validate,
            sync=args.sync,
            validation_statuses=args.validation_statuses,
            analysis_data=args.analysis_data,
            chunk_size=args.chunk_size,
            config_file=args.config_file,
            skip_media=args.skip_media,
            summary_file=args.summary_file,
        )
    except requests.RequestException as e:
        print(f'❌ Stopped: {describe(e)}')
        if args.summary_file:
            write_summary(args.summary_file, {
                **SUMMARY, 'ok': False, 'error': describe(e),
                'finished': time.strftime('%Y-%m-%dT%H:%M:%S%z')})
        sys.exit(1)
    except KeyboardInterrupt:
        print('🛑 Stopping run')
        # Do something here so we can pick up again where this leaves off
        sys.exit()
