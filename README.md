# kobo-transfer

Transfer submissions between two identical projects.

## Setup

1. Ensure the destination project is deployed and has the same content as the
   source project.

1. Clone a copy of this repo somewhere on your local machine:

```bash
git clone https://github.com/kobotoolbox/kobo-transfer
```

1. Copy `sample-config.json` to `config.json` and add your configuration details
   for the source (`src`) and destination (`dest`) projects. If both projects
   are located on the same Kobo instance, then just duplicate the URL and token
   values.

## Usage

```bash
python3 run.py \
  [--config-file/-c] [--limit/-l] [--last-failed/-lf] \
  [--keep-media/-k] [--no-validate/-N] [--quiet/-q]
```

The original UUID for each submission is maintained across the transfer,
allowing for duplicate submissions to be rejected at the destination project if
the script is run multiple times.

If submissions contain media attachments, all media will be downloaded to a
local `attachments/` directory before the transfer between projects begin.
Attachment files will be cleaned up after completion of the transfer unless the
`--keep-media` flag is passed.

The `--limit` option can be set to restrict the number of submissions processed
in a batch. For large projects, either in number of submissions or number of
questions or both, it may be necessary to reduce the limit below the default of
30000 to mitigate time-outs from the server.

Sometimes transfers will fail for whatever reason. A list of failed UUIDs is
stored in `.log/failures.txt` after each run. You can run the transfer again
with only these failed submissions by passing the flag `--last-failed`.

If you would like to have a configuration file other than `config.json`, such as
when different configurations are kept in the directory, then specify the file
path with `--config-file`:

```bash
python3 run.py --config-file config-2.json
```

By default, the configuration file will be validated before the transfer is
attempted. Pass the `--no-validate` flag to skip this step.

## Media attachments

Media attachments are written to the local `attachments/` directory and follow
the tree structure of:

```bash
{asset_uid}
├── {submission_uid}
│   ├── {filename}
│   └── {filename}
├── {submission_uid}
│   └── {filename}
├── {submission_uid}
│   └── {filename}
├── {submission_uid}
│   └── {filename}
└── {submission_uid}
    ├── {filename}
    └── {filename}
```

## Limitations

- Although submissions will not be duplicated across multiple runs of the
  script, if the submissions contain attachment files, the files are duplicated
  on the server.
- The script does not check if the source and destination projects are identical
  and will transfer submission data regardless.
