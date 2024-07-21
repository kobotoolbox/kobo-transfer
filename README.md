# kobo-transfer

Transfer assets and submissions between two projects.

## Setup

1. Clone a copy of this repo somewhere on your local machine:

```bash
git clone https://github.com/kobotoolbox/kobo-transfer
```

2. Install `pip` packages from `requirements.txt`. See detailed steps
   [here](#python-requirements).

3. Copy `sample-config.json` to `config.json` and add your configuration details
   for the source (`src`) and destination (`dest`) projects. If both projects
   are located on the same server, then just duplicate the URLs and token
   values.

4. If only syncing submissions, ensure the destination project is deployed and
   has the same content as the source project.

5. If transferring assets _and_ submissions for the first time, leave the
   `dest.asset_uid` field empty in the config file:

```
{
  ...
  "dest": {
    ...
    "asset_uid": ""
  }
}
```

**Note:** Kobo offers two public servers, the Global and EU servers. For each of
these, the config URLs are the following:

- EU:
  - `kc_url`: https://kc-eu.kobotoolbox.org
  - `kf_url`: https://eu.kobotoolbox.org
- Global:
  - `kc_url`: https://kc.kobotoolbox.org
  - `kf_url`: https://kf.kobotoolbox.org

## Usage

```bash
python3 run.py \
  [--config-file/-c <file path>] [--asset/-a] [--sync/-s] [--no-validate/-N] \
  [--validation-status/-vs] [--analysis-data/-ad] [--keep-media/-k] \
  [--src-asset-uid/-sau <uid>] [--limit/-l <limit>] [--chunk-size/-cs <size>] \
  [--regenerate-uuids/-R] [--last-failed/-lf] [--quiet/-q]
```

To transfer the asset, its form media and versions from the `src` to `dest`
servers, use the `--asset` flag, in addition to any other flags described below.
Once the asset has finished transferring, the submissions will be transferred
next. Note that each time this flag is used, a _new_ asset is created on the
`dest` side.

```bash
python3 run.py --asset
```

The original UUID for each submission is maintained across the transfer,
allowing for duplicate submissions to be rejected at the destination project if
the script is run multiple times. If this behaviour is not desired, pass the
`--regenerate-uuids` flag to create new UUIDs for each submission. This may be
necessary when transferring submissions to a project located on the same server.

Use the `--sync` option to keep the two projects in sync after an initial
transfer. This is useful if you are phasing from one server to the other and
there is still data being collected at the `src`. Without using `--sync` in this
case, if the submissions contain media attachments, they will be duplicated at
the `dest` project and therefore consume unnecessary storage in your account.

Use the `--validation-status` option to sync the validation statuses from `src`
submissions to the `dest`. If used in combination with the `--sync` option, it
will first transfer missing submissions and then sync the statuses. If used
alone, it will only sync the status and then end script operation -- no
submissions will be transferred. Since the validation statuses are metadata to
the submissions, this requires an additional step to the standard process.

```bash
python3 run.py --sync --validation-status
# or
python3 run.py --validation-status
```

Use the `--analysis-data` to transfer analysis data, which may include
transcripts, translations, analysis questions. As with the `--validation-status`
option, this is an additional step needed once the submissions have already been
transferred. It can be run with the `--sync` option (and other compatible
options) or on its own.

```bash
python3 run.py --sync --analysis-data
# or
python3 run.py --analysis-data
```

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

Example usage with syncing submissions, validation statuses and analysis data in
one go, noting that this will be three different phases of the transfer that
will run sequentially:

```bash
python3 run.py --config-file config-project-abc.json --sync \
  --validation-status --analysis-data \
  --keep-media --no-validate

# additionally let's transfer the asset itself with the `--asset` flag
python3 run.py --config-file config-project-abc.json --sync \
  --asset --validation-status --analysis-data \
  --keep-media --no-validate
```

Use the `--src-asset-uid` to pass an asset UID through the args rather than in
the config file. This allows for iterating through a list of assets UIDs and
transfer them in bulk. Example usage of transferring all assets and submission
data from one user account to another (note that a config file is still required
for configuring URLs and tokens):

```bash
TOKEN=<your src token>
# note this requires `jq` to be installed
curl -s 'https://kf.kobotoolbox.org/api/v2/assets.json' \
  -H "Authorization: Token $TOKEN" | \
  jq '.results[] | select(.asset_type == "survey" and .has_deployment == true) | .uid' | \
  xargs -I {} python3 run.py --src-asset-uid "{}" --asset --sync -c <config file>
```

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

- Although submissions will generally not be duplicated across multiple runs of
  the script, if the submissions contain attachment files, they are duplicated
  on the server unless the `--sync` option is used.
- The script does not check if the source and destination projects are identical
  and will transfer submission data regardless.
- The script does not account for multiple versions that the form may have had.
  Rather use the `--asset` flag to fully transfer the `src` project to the
  `dest` side to account for this. It naively uses the latest version of the
  `dest` form for the submissions' `__version__` attribute. This will be updated
  at some point to match the version history at the `dest` project.
- Currently it's not possible to sync the asset versions from `src` to `dest`.
  Once a project has been transferred with all its versions, it's best not to
  continue updating the form and submitting data to the `src` project to avoid
  complications.
- If the `dest` form is updated and redeployed, it will have a new version UID.
  If the script is run again, this will result in duplicates at the `dest`
  because the submissions contain the new `__version__` value, therefore are no
  longer unique, and therefore won't be rejected from the `dest` project. This
  will be addressed once transferred submissions have their `__version__` value
  matching the new version UIDs at the `dest` project.
- Due to a known KoboToolbox issue, projects may contain submissions with
  duplicate submission UUIDs. Some of these submissions may be full duplicates
  of themselves, while others are unique submissions but contain a duplicate
  UUID value. If an initial sync between `src` and `dest` has been done, only
  unique submissions will be transferred (or accepted by the `dest` project). If
  more submissions are collected at the `src` after this point and they contain
  duplicate UUIDs from the previous sync (the UUID already exists at the
  `dest`), those submissions will not be transferred.

## Python requirements

To ensure that the necessary Python packages are installed correctly, follow the
steps below to set up a virtual environment and install the packages listed in
the `requirements.txt` file. These instructions cover both Windows and
macOS/Linux systems.

### Windows

1. **Install Python and pip**

Make sure you have Python and pip installed. You can download Python from the
[official website](https://www.python.org/downloads/), which includes pip by
default.

2. **Create a virtual environment**

Open the Command Prompt and navigate to the directory where your script is
located. Then, run the following command to create a virtual environment:

```sh
python -m venv venv
```

3. **Activate the virtual environment**

Activate the virtual environment with the following command:

```sh
.\venv\Scripts\activate
```

4. **Install the required packages**

With the virtual environment activated, install the required packages by
running:

```sh
pip install -r requirements.txt
```

### macOS/Linux

1. **Install Python and pip**

Ensure you have Python and pip installed. Most macOS/Linux systems come with
Python pre-installed. If not, you can install Python via a package manager
(e.g., `brew` for macOS or `apt` for Ubuntu).

2. **Create a virtual environment**

Open a terminal and navigate to the directory where your script is located.
Then, run the following command to create a virtual environment:

```sh
python3 -m venv venv
```

3. **Activate the virtual environment**

Activate the virtual environment with the following command:

```sh
source venv/bin/activate
```

4. **Install the required packages**

With the virtual environment activated, install the required packages by
running:

```sh
pip3 install -r requirements.txt
```
