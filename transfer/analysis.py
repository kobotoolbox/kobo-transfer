import re
import requests


ACTION_NAME_MAP = {
    'automatic_google_transcription': 'manual_transcription',
    'automatic_google_translation': 'manual_translation',
    'automatic_bedrock_qual': 'manual_qual',
}

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
)


def _is_uuid(key):
    return bool(_UUID_RE.match(key))


def _get_versions_data(versions):
    """
    Return _data for all versions in chronological order (oldest first).
    Strips `status` since manual actions don't accept it.
    """
    sorted_v = sorted(versions, key=lambda v: v.get('_dateCreated', ''))
    return [
        {k: val for k, val in v.get('_data', {}).items() if k != 'status'}
        for v in sorted_v
        if v.get('_data')
    ]


def clean_sup_details(data):
    """
    Transform GET /supplement/ response into an ordered list of PATCH payloads.

    Each version becomes its own payload to preserve full history.
    Ordering: transcription first (translation depends on it), then
    translation, then qual (no dependencies).
    Automatic action names are mapped to their manual equivalents.
    """
    version = data.get('_version')
    transcription_payloads = []
    translation_payloads = []
    qual_payloads = []

    for question_xpath, actions in data.items():
        if question_xpath.startswith('_') or not isinstance(actions, dict):
            continue

        for action_key, action_value in actions.items():
            if action_key.startswith('_') or not isinstance(action_value, dict):
                continue

            mapped_action = ACTION_NAME_MAP.get(action_key, action_key)

            if '_versions' in action_value:
                # Direct action (e.g. transcription)
                for v_data in _get_versions_data(action_value['_versions']):
                    transcription_payloads.append({
                        '_version': version,
                        question_xpath: {mapped_action: v_data},
                    })
            else:
                # Sub-keyed action: language codes (translation) or UUIDs (qual)
                for sub_key, sub_value in action_value.items():
                    if sub_key.startswith('_') or not isinstance(sub_value, dict):
                        continue
                    if '_versions' not in sub_value:
                        continue

                    for v_data in _get_versions_data(sub_value['_versions']):
                        payload = {
                            '_version': version,
                            question_xpath: {mapped_action: v_data},
                        }
                        if _is_uuid(sub_key):
                            qual_payloads.append(payload)
                        else:
                            translation_payloads.append(payload)

    return transcription_payloads + translation_payloads + qual_payloads


def sync_advanced_features(config_src, config_dest):
    """
    Configure dest advanced features from src.
    Maps automatic actions to manual equivalents and merges params when
    multiple src features map to the same dest action.
    """
    src_res = requests.get(
        url=config_src['asset_url'] + 'advanced-features/',
        headers=config_src['headers'],
    )
    src_res.raise_for_status()

    dest_res = requests.get(
        url=config_dest['asset_url'] + 'advanced-features/',
        headers=config_dest['headers'],
    )
    dest_res.raise_for_status()
    existing_on_dest = {
        (f['question_xpath'], f['action']) for f in dest_res.json()
    }

    dest_features = {
        (f['question_xpath'], f['action']): f for f in dest_res.json()
    }

    to_create = {}
    to_update = {}  # key → (dest_uid, merged_params)

    for f in src_res.json():
        action = f.get('action', '')
        mapped_action = ACTION_NAME_MAP.get(action, action)
        key = (f['question_xpath'], mapped_action)

        target = to_create if key not in dest_features else None

        if target is None:
            # Feature exists on dest — check for missing params
            dest_feature = dest_features[key]
            dest_ids = {
                p.get('language') or p.get('uuid')
                for p in dest_feature.get('params', [])
            }
            missing = [
                p for p in f.get('params', [])
                if (p.get('language') or p.get('uuid')) not in dest_ids
            ]
            if missing:
                if key not in to_update:
                    to_update[key] = (
                        dest_feature['uid'],
                        list(dest_feature.get('params', [])),
                    )
                existing_ids = {
                    p.get('language') or p.get('uuid')
                    for p in to_update[key][1]
                }
                for p in missing:
                    pid = p.get('language') or p.get('uuid')
                    if pid not in existing_ids:
                        to_update[key][1].append(p)
                        existing_ids.add(pid)
        else:
            if key not in target:
                target[key] = {
                    'question_xpath': f['question_xpath'],
                    'action': mapped_action,
                    'params': list(f.get('params', [])),
                }
            else:
                existing_ids = {
                    p.get('language') or p.get('uuid')
                    for p in target[key]['params']
                }
                for p in f.get('params', []):
                    pid = p.get('language') or p.get('uuid')
                    if pid not in existing_ids:
                        target[key]['params'].append(p)
                        existing_ids.add(pid)

    for feature in to_create.values():
        res = requests.post(
            url=config_dest['asset_url'] + 'advanced-features/',
            headers=config_dest['headers'],
            json=feature,
        )
        res.raise_for_status()
        print(f"✅ {feature['action']} ({feature['question_xpath']})")

    for (question_xpath, action), (dest_uid, merged_params) in to_update.items():
        res = requests.patch(
            url=config_dest['asset_url'] + f'advanced-features/{dest_uid}/',
            headers=config_dest['headers'],
            json={'params': merged_params},
        )
        res.raise_for_status()
        print(f"✅ updated {action} ({question_xpath})")


def sync_analysis_data(config, limit=10000):
    config_src = config.src
    config_dest = config.dest

    print('📋 Configuring analysis features in dest project')
    sync_advanced_features(config_src, config_dest)

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

            sup_res = requests.get(
                url=f"{config_src['data_url']}{uuid}/supplement/",
                headers=config_src['headers'],
            )
            if not sup_res.ok:
                continue

            payloads = clean_sup_details(sup_res.json())
            if not payloads:
                continue

            failed = False
            for payload in payloads:
                sd_post_res = requests.patch(
                    url=f"{config_dest['data_url']}{uuid}/supplement/",
                    headers=config_dest['headers'],
                    json=payload,
                )
                if not sd_post_res.ok:
                    print(f'❌ {uuid} ({sd_post_res.status_code}): {sd_post_res.text}')
                    failed = True
                    break
            if not failed:
                print(f'✅ {uuid} (Analysis data)')

        if next_:
            sync_rec(next_)

    print('📨 Transferring analyis data')
    sync_rec(config_src['data_url'])
