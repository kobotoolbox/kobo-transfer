import json

import requests

from utils.urls import rebase

# Supplement schema version of KPI's advanced features API
# (/api/v2/assets/<uid>/advanced-features/ and /data/<uuid>/supplement/)
SUPPLEMENT_VERSION = '20250820'

# Features that others depend on go first: automatic qual answers questions defined by
# manual qual, and translations of audio need a transcript
FEATURE_ORDER = [
    'manual_qual',
    'automatic_bedrock_qual',
    'manual_transcription',
    'automatic_google_transcription',
    'manual_translation',
    'automatic_google_translation',
]
TRANSCRIPTION = {'manual_transcription', 'automatic_google_transcription'}
TRANSLATION = {'manual_translation', 'automatic_google_translation'}
QUAL = {'manual_qual', 'automatic_bedrock_qual'}


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
    """
    Copy transcripts, translations and qualitative analysis from `src` to `dest`.
    Returns the counts: submissions, versions added and updated, unreviewed results left
    at `src`, and submissions that failed.
    """
    features_url = f"{config.src['asset_url']}advanced-features/"
    res = requests.get(features_url, headers=config.src['headers'])
    if res.status_code == 404:
        # KPI from before the advanced features API
        return sync_analysis_data_legacy(config, limit)
    res.raise_for_status()
    src_features = res.json()

    importer = has_supplement_import(config.dest)
    if importer:
        print('📋 Merging analysis features into dest project')
    else:
        print(
            '📋 Merging analysis features into dest project. It has no supplement '
            'import: only reviewed results are copied, as manual entries'
        )
    merge_features(config.dest, src_features, with_manual=not importer)

    stats = {'submissions': 0, 'added': 0, 'updated': 0, 'unreviewed': 0, 'failed': 0}
    print('📨 Transferring analysis data')
    # Supplements are keyed by the submission's root UUID, which stays the same when it's
    # edited (its `_uuid` doesn't)
    for uuid in get_uuids_with_supplements(config.src, limit):
        supplement = get_supplement(config.src, uuid)
        if not any(k != '_version' for k in supplement):
            continue
        stats['submissions'] += 1
        try:
            if importer:
                result = import_supplement(config.dest, uuid, supplement)
            else:
                result = copy_reviewed(config.dest, uuid, supplement)
        except requests.HTTPError as e:
            stats['failed'] += 1
            print(f'❌ {uuid} (Analysis data): {e.response.status_code} {e.response.text[:300]}')
            continue
        for k in ('added', 'updated', 'unreviewed'):
            stats[k] += result.get(k, 0)
        print(
            f"✅ {uuid} (Analysis data: {result.get('added', 0)} added, "
            f"{result.get('updated', 0)} updated"
            + (f", {result['unreviewed']} unreviewed left at src" if result.get('unreviewed') else '')
            + ')'
        )
    print(
        f"🧮 Analysis data: {stats['submissions']} submissions, {stats['added']} versions "
        f"added, {stats['updated']} updated, {stats['unreviewed']} unreviewed left at src, "
        f"{stats['failed']} failed"
    )
    return stats


def has_supplement_import(config_loc):
    """
    Whether `dest` can store versions as they are (POST .../supplement/import/). A GET
    on that route is 405 where it exists and 404 where it doesn't.
    """
    url = f"{config_loc['asset_url']}data/00000000-0000-0000-0000-000000000000/supplement/import/"
    return requests.get(url, headers=config_loc['headers']).status_code == 405


def param_key(param):
    return param.get('uuid') or param.get('language') or json.dumps(param, sort_keys=True)


def merge_features(config_dest, src_features, with_manual=False):
    """
    Enable every `src` feature on `dest`, adding `src`'s params to any `dest` already has.
    Nothing at `dest` is removed (other sources may have added it). `with_manual` also
    enables the manual features that reviewed automatic results are copied into.
    """
    wanted = {}
    for f in src_features:
        wanted.setdefault((f['question_xpath'], f['action']), []).extend(f['params'])
        if with_manual:
            manual = {
                'automatic_google_transcription': 'manual_transcription',
                'automatic_google_translation': 'manual_translation',
            }.get(f['action'])
            if manual:
                wanted.setdefault((f['question_xpath'], manual), []).extend(f['params'])

    url = f"{config_dest['asset_url']}advanced-features/"
    res = requests.get(url, headers=config_dest['headers'])
    res.raise_for_status()
    existing = {(f['question_xpath'], f['action']): f for f in res.json()}

    order = lambda k: FEATURE_ORDER.index(k[1]) if k[1] in FEATURE_ORDER else len(FEATURE_ORDER)
    for key in sorted(wanted, key=order):
        xpath, action = key
        if key not in existing:
            res = requests.post(
                url,
                headers=config_dest['headers'],
                json={'question_xpath': xpath, 'action': action, 'params': wanted[key]},
            )
            res.raise_for_status()
            continue
        params = existing[key]['params']
        have = {param_key(p) for p in params}
        new = [p for p in wanted[key] if param_key(p) not in have]
        if new:
            # The full list: qual hides questions missing from it
            res = requests.patch(
                f"{url}{existing[key]['uid']}/",
                headers=config_dest['headers'],
                json={'params': params + new},
            )
            res.raise_for_status()


def get_uuids_with_supplements(config_src, limit):
    params = {
        'format': 'json',
        'limit': limit,
        'fields': json.dumps(['_uuid', 'meta/rootUuid', '_supplementalDetails']),
    }
    url = config_src['data_url']
    while url:
        res = requests.get(url, headers=config_src['headers'], params=params)
        res.raise_for_status()
        data = res.json()
        for sub in data['results']:
            # No `_supplementalDetails` key at all: the server didn't say, so look
            if sub.get('_supplementalDetails', True):
                yield (sub.get('meta/rootUuid') or sub['_uuid']).replace('uuid:', '')
        url, params = rebase(data['next'], config_src['kf_url']), None


def get_supplement(config_loc, uuid):
    res = requests.get(
        f"{config_loc['data_url']}{uuid}/supplement/", headers=config_loc['headers']
    )
    res.raise_for_status()
    return res.json()


def import_supplement(config_dest, uuid, supplement):
    res = requests.post(
        f"{config_dest['data_url']}{uuid}/supplement/import/",
        headers=config_dest['headers'],
        json=supplement,
    )
    res.raise_for_status()
    return res.json()


def selected(action, node):
    """
    The value a person has reviewed in one versioned node, or None: for transcripts and
    translations the latest accepted version (unless deleted since), for qual answers
    the latest manual one or the latest verified automatic one.
    """
    versions = node.get('_versions', [])
    if action in QUAL:
        for v in versions:  # newest first
            if action == 'manual_qual' or v.get('verified'):
                return v['_data'].get('value')
        return None
    accepted = [v for v in versions if v.get('_dateAccepted')]
    if not accepted:
        return None
    latest = max(accepted, key=lambda v: v['_dateAccepted'])
    deleted_since = any(
        v['_data'].get('status') == 'deleted' and v['_dateCreated'] > latest['_dateAccepted']
        for v in versions
    )
    return None if deleted_since else latest['_data'].get('value')


def reviewed_entries(supplement):
    """
    (xpath, manual action, data) for every reviewed result, and how many unreviewed
    automatic results there are.
    """
    entries, unreviewed = [], 0
    for xpath, actions in supplement.items():
        if xpath == '_version':
            continue
        for action, data in actions.items():
            nodes = {'': data} if '_versions' in data else data
            for key, node in nodes.items():
                value = selected(action, node)
                if value is None:
                    unreviewed += action.startswith('automatic_')
                    continue
                if action in TRANSCRIPTION:
                    language = node['_versions'][0]['_data'].get('language')
                    entries.append((xpath, 'manual_transcription', {'language': language, 'value': value}))
                elif action in TRANSLATION:
                    entries.append((xpath, 'manual_translation', {'language': key, 'value': value}))
                elif action in QUAL:
                    entries.append((xpath, 'manual_qual', {'uuid': key, 'value': value}))
    order = {'manual_qual': 0, 'manual_transcription': 1, 'manual_translation': 2}
    return sorted(entries, key=lambda e: order[e[1]]), unreviewed


def copy_reviewed(config_dest, uuid, supplement):
    """
    Without an import route, write reviewed results as manual entries through the public
    API, unless `dest` already has the same reviewed value, manual or automatic (so
    re-runs add nothing).
    """
    entries, unreviewed = reviewed_entries(supplement)
    dest = get_supplement(config_dest, uuid)
    added = 0
    for xpath, action, data in entries:
        same_kind = {
            'manual_transcription': TRANSCRIPTION,
            'manual_translation': TRANSLATION,
            'manual_qual': QUAL,
        }[action]
        have = []
        for dest_action in same_kind:
            node = dest.get(xpath, {}).get(dest_action, {})
            if action == 'manual_translation':
                node = node.get(data['language'], {})
            elif action == 'manual_qual':
                node = node.get(data['uuid'], {})
            if node:
                have.append(selected(dest_action, node))
        if data['value'] in have:
            continue
        res = requests.patch(
            f"{config_dest['data_url']}{uuid}/supplement/",
            headers=config_dest['headers'],
            json={'_version': SUPPLEMENT_VERSION, xpath: {action: data}},
        )
        res.raise_for_status()
        added += 1
    return {'added': added, 'updated': 0, 'unreviewed': unreviewed}


def sync_analysis_data_legacy(config, limit=10000):
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

    failed = 0

    def sync_rec(url):
        nonlocal failed
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
            except requests.HTTPError:
                failed += 1
                print(f'❌ {uuid} (Analysis data): {sd_post_res.status_code}')

        if next_:
            sync_rec(next_)

    print('📨 Transferring analyis data')
    sync_rec(config_src['data_url'])
    return {'failed': failed}
