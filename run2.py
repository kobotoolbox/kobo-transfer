#!/usr/bin/env python3

import argparse
import json
import sys

from helpers.config import Config
from transfer.media import get_media, del_media, download_google_media
from transfer.xml import (
    get_src_submissions_xml,
    get_submission_edit_data,
    print_stats,
    transfer_submissions,
    xls_to_xml,
)

def main(
    gtransfer,
    excel_file,
    limit,
    last_failed=False,
    keep_media=False,
    regenerate=False,
    quiet=False,
    validate=True,
    config_file=None,
):
    config = Config(config_file=config_file, validate=validate)
    config_src = config.src
   
    print('📸 Getting all submission media', end=' ', flush=True)
    #get_media() #TODO: josh saves all media in the attachments folder here
    #download_google_media("https://drive.google.com/drive/u/1/folders/149lRc_R6YBqqUCQEMuN_vmz36wqp5r1BiZolmcxGqDO4J5the7h_g_8xZ8Jvuz_50ugrnhcR") #TODO hardcoded folder to all media from google survey
    xml_url_src = config_src['xml_url'] + f'?limit={limit}'

    if last_failed and config.last_failed_uuids:
        xml_url_src += f'&query={json.dumps(config.data_query)}'

    all_results = []
    submission_edit_data = get_submission_edit_data() 

    xml_file_path = './output.xml' #TODO: (for testing purposes)

    def transfer(all_results, url=None):
        if (gtransfer):
            parsed_xml = xls_to_xml(excel_file, xml_file_path, submission_edit_data)
        else: 
            parsed_xml = get_src_submissions_xml(xml_url=url)
        
        submissions = parsed_xml.findall(f'results/{config_src["asset_uid"]}')
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
        
    transfer(all_results, xml_url_src)

    if not keep_media:
        del_media()

    print('✨ Done')
    print_stats(all_results)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='A CLI tool to transfer submissions between projects with identical XLSForms.'
    )
    parser.add_argument( 
        '--google-transfer',
        '-g',
        default = False,
        action = 'store_true', 
        help='Complete transfer from Google Form data to Kobo project.', #TODO
    )
    parser.add_argument( 
        '--excel-file',
        '-ef', 
        default = "./KoboTest(Responses_New(nofile).xlsx",
        help='Google form excel-file path', #TODO
    )
    parser.add_argument(
        '--limit',
        '-l',
        default=30000,
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
        '--quiet',
        '-q',
        default=False,
        action='store_true',
        help='Suppress stdout',
    )
    args = parser.parse_args()

    try:
        main(
            gtransfer=args.google_transfer,
            excel_file=args.excel_file,
            limit=args.limit,
            last_failed=args.last_failed,
            regenerate=args.regenerate_uuids,
            keep_media=args.keep_media,
            quiet=args.quiet,
            validate=not args.no_validate,
            config_file=args.config_file,
        )
    except KeyboardInterrupt:
        print('🛑 Stopping run')
        # Do something here so we can pick up again where this leaves off
        sys.exit()
