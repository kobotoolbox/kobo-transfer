import requests


def clean_sup_details(input_dict):
    output_dict = {}
    for key, value in input_dict.items():
        if isinstance(value, dict):
            cleaned_value = clean_sup_details(value)
            if cleaned_value:  # Only add non-empty dictionaries
                output_dict[key] = cleaned_value
        elif isinstance(value, list):
            cleaned_list = [
                clean_sup_details(item) if isinstance(item, dict) else item
                for item in value
            ]
            cleaned_list = [
                item for item in cleaned_list if item
            ]  # Remove empty dictionaries from the list
            if cleaned_list:  # Only add non-empty lists
                output_dict[key] = cleaned_list
        else:
            if key in ['uuid', 'type', 'val', 'value', 'languageCode']:
                output_dict[key] = value

    if 'type' in output_dict and 'val' in output_dict:
        if output_dict['type'] == 'qual_select_multiple':
            output_dict['val'] = [
                item['uuid'] for item in output_dict['val'] if 'uuid' in item
            ]

        if output_dict['type'] == 'qual_select_one':
            output_dict['val'] = output_dict['val']['uuid']

    return output_dict


def sync_analysis_data(config, limit=10000):
    config_src = config.src
    config_dest = config.dest

    adv_features_res = requests.get(
        url=config_src['asset_url'],
        headers=config_src['headers'],
        params=config_src['params'],
    )
    adv_features_res.raise_for_status()
    adv_features = adv_features_res.json()['advanced_features']

    adv_features_payload = {'advanced_features': adv_features}
    print('📋 Creating analysis form in dest project')
    adv_features_patch_res = requests.patch(
        url=config_dest['asset_url_json'],
        headers=config_dest['headers'],
        json=adv_features_payload,
    )
    adv_features_patch_res.raise_for_status()

    def sync_rec(url):
        sub_res = requests.get(
            url=url,
            headers=config_src['headers'],
            params={'limit': limit, **config_src['params']},
        )
        sub_res.raise_for_status()
        sub_data = sub_res.json()
        next_ = sub_data['next']
        submissions = sub_data['results']

        for submission in submissions:
            uuid = submission['_uuid']
            sup_details = submission.get('_supplementalDetails')

            if not sup_details:
                continue

            sd_payload = {'submission': uuid, **clean_sup_details(sup_details)}
            sd_post_res = requests.post(
                url=config_dest['advanced_submission_url'],
                headers=config_dest['headers'],
                json=sd_payload,
            )
            try:
                sd_post_res.raise_for_status()
                print(f'✅ {uuid} (Analysis data)')
            except:
                print(f'Something went wrong with {uuid}')

        if next_:
            sync_rec(next_)

    print('📨 Transferring analyis data')
    sync_rec(config_src['data_url'])
