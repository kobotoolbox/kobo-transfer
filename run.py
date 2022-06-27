#!/usr/bin/env python3

import argparse

from transfer.transfer import main

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

    main(limit=args.limit, keep_media=args.keep_media, quiet=args.quiet)
