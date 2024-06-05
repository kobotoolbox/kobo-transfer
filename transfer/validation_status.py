import requests
import json
from collections import defaultdict

from utils.joins import left_join
from utils.iterators import chunker


def get_params(loc, limit):
    fields = ['_uuid']
    if loc == 'src':
        fields.append('_validation_status')

    params = {
        'format': 'json',
        'fields': json.dumps(fields),
        'limit': limit,
    }

    if loc == 'src':
        params['query'] = json.dumps(
            {'_validation_status.uid': {'$exists': 'true'}}
        )

    return params


def get_results(url, params, headers):
    def get_uuids_rec(results=[], url=None):
        if 'fields' not in url:
            res = requests.get(url=url, params=params, headers=headers)
        else:
            res = requests.get(url=url, headers=headers)

        data = res.json()
        results += data['results']
        next_ = data['next']

        if next_ is not None:
            get_uuids_rec(results, next_)

    results = []
    get_uuids_rec(results=results, url=url)
    return results


def get_payload(ids, validation_status):
    return {
        'payload': {
            'submission_ids': ids,
            'validation_status.uid': validation_status,
        }
    }


def get_clean_stats():
    return {
        'validation_status_on_hold': 0,
        'validation_status_not_approved': 0,
        'validation_status_approved': 0,
    }


def update_dest_validation_status(validation_data, config, stats, chunk_size):
    for key, group in validation_data.items():
        submission_ids = [str(i['_id']) for i in group if '_id' in i]
        for chunked_ids in chunker(submission_ids, chunk_size):
            res = requests.patch(
                url=config.dest['validation_statuses_url'],
                headers=config.dest['headers'],
                json=get_payload(chunked_ids, key),
            )
            res.raise_for_status()
            stats[key] += int(res.json()['detail'].split()[0])
    return stats


def print_stats(stats):
    '''
    Very simple stats formatting -- to be improved.
    '''
    print('-----------')
    for k, v in stats.items():
        print(f'{k}: {v}')
    print('-----------')


def sync_validation_statuses(config, chunk_size, limit):
    stats = get_clean_stats()

    src_results = get_results(
        url=config.src['data_url'],
        params=get_params(loc='src', limit=limit),
        headers=config.src['headers'],
    )

    src_data = []
    for item in src_results:
        src_data.append(
            {
                '_uuid': item['_uuid'],
                'validation_status_uid': item['_validation_status']['uid'],
            }
        )

    dest_data = get_results(
        url=config.dest['data_url'],
        params=get_params(loc='dest', limit=limit),
        headers=config.dest['headers'],
    )

    joined = left_join(src_data, dest_data, '_uuid')

    grouped = defaultdict(list)
    for item in joined:
        grouped[item['validation_status_uid']].append(item)
    validation_data = dict(grouped)

    res_stats = update_dest_validation_status(
        validation_data, config, stats, chunk_size
    )
    print_stats(res_stats)
