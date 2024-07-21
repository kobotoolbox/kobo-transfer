import base64
import json
import requests


def get_src_asset_details(config_src):
    '''
    Get the details needed from the `src` project to setup the `dest`:
      - Settings
      - Deployed version history
      - Form media
    '''
    res = requests.get(
        url=config_src['asset_url_json'], headers=config_src['headers']
    )
    res.raise_for_status()
    asset_data = res.json()

    deployed_versions = asset_data['deployed_versions']['results']
    files = [
        {'url': f['content'], 'metadata': f['metadata']}
        for f in asset_data['files']
    ]

    asset_setup_content = {}
    for item in ['name', 'settings', 'asset_type']:
        asset_setup_content[item] = asset_data[item]

    return asset_setup_content, deployed_versions, files


def create_asset(config_dest, asset_setup_content):
    '''
    Create the `dest` asset, initially without content.
    '''
    res = requests.post(
        url=config_dest['assets_url'] + '/',
        headers=config_dest['headers'],
        params=config_dest['params'],
        json=asset_setup_content,
    )
    res.raise_for_status()
    return res.json()['uid']


def deploy_all_versions(config_src, config_dest, deployed_versions):
    '''
    Iterate through all deployed `src` versions and deploy them from
    oldest to newest on the `dest` side.
    '''
    # `reversed()` is needed to go from oldest to newest version
    for i, dp in enumerate(reversed(deployed_versions)):
        # Get the version content from `src`
        res = requests.get(
            url=dp['url'],
            headers=config_src['headers'],
        )
        res.raise_for_status()
        asset_content = res.json()['content']

        # Patch this content to the `dest asset`
        res = requests.patch(
            url=config_dest['asset_url'] + '/',
            headers=config_dest['headers'],
            params=config_dest['params'],
            json={"content": json.dumps(asset_content)},
        )
        res.raise_for_status()
        version_id = res.json()['version_id']

        # Deploy `dest` asset version. If it's the first time
        # being deployed, use `POST`, otherwise `PATCH`.
        method = 'POST' if i == 0 else 'PATCH'
        res = requests.request(
            method=method,
            url=config_dest['deployment_url'],
            headers=config_dest['headers'],
            json={'active': True, 'version_id': version_id},
        )
        res.raise_for_status()
        print(f'✅ {version_id}')


def transfer_asset_media(config_src, config_dest, files):
    '''
    Transfer all form media from `src` to `dest`
    '''
    if not files:
        return
    
    dest_headers = {
        **config_dest['headers'],
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    for file in files:
        # Download file from `src`
        res = requests.get(
            file['url'], stream=True, headers=config_src['headers']
        )
        res.raise_for_status()

        # Encode file content to base64
        file_content = res.content
        encoded_file = base64.b64encode(file_content).decode('utf-8')
        data = {
            'description': 'default',
            'file_type': 'form_media',
            'metadata': json.dumps(file['metadata']),
            'base64Encoded': f"data:{file['metadata']['mimetype']};base64,"
            + encoded_file,
        }
        # `POST` file content and metadata to `dest`
        res = requests.post(
            url=config_dest['files_url'], headers=dest_headers, data=data
        )
        res.raise_for_status()
        print(f"✅ {file['metadata']['filename']}")


def transfer_asset(config):
    config_src = config.src
    config_dest = config.dest

    _, deployed_versions, files = get_src_asset_details(config_src=config_src)
    print('💼 Transferring all form media files')
    transfer_asset_media(config_src, config_dest, files)
    print('📨 Transferring and deploying all versions')
    deploy_all_versions(config_src, config_dest, deployed_versions)
    print(f'✨ All {len(deployed_versions)} versions deployed')
