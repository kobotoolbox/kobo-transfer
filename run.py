#!/usr/bin/env python3

import argparse

from helpers.config import Config
from transfer.media import get_media, del_media
from transfer.xml import (
    get_old_submissions_xml,
    get_submission_edit_data,
    print_stats,
    transfer_submissions,
)


def main(limit, keep_media=False, quiet=False, config_file=None):
    config = Config(config_file=config_file).old

    print('📸 Getting all submission media', end=' ', flush=True)
    get_media()

    xml_url_old = config['xml_url'] + f'?limit={limit}'
    all_results = []
    submission_edit_data = get_submission_edit_data()

    print('📨 Transferring submission data')

    def transfer(all_results, url=None):
        parsed_xml = get_old_submissions_xml(xml_url=url)
        submissions = parsed_xml.findall(f'results/{config["asset_uid"]}')
        next_ = parsed_xml.find('next').text
        results = transfer_submissions(
            submissions, submission_edit_data, quiet=quiet
        )
        all_results += results
        if next_ != 'None':
            transfer(all_results, next_)

    transfer(all_results, xml_url_old)

    if not keep_media:
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
        default=30000,
        type=int,
        help='Number of submissions included in each batch for download and upload.',
    )
    parser.add_argument(
        '--config-file',
        '-c',
        default='config.json',
        type=str,
        help='Location of config file.',
    )
    parser.add_argument(
        '--keep-media',
        '-k',
        default=False,
        action='store_true',
        help='Keep submission attachments rather than cleaning up after transfer.',
    )
    parser.add_argument(
        '--quiet',
        '-q',
        default=False,
        action='store_true',
        help='Suppress stdout',
    )
    args = parser.parse_args()

    main(
        limit=args.limit,
        keep_media=args.keep_media,
        quiet=args.quiet,
        config_file=args.config_file,
    )
