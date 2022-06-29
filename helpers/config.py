import json
import os
import pathlib

from .singleton import Singleton


class Config(metaclass=Singleton):
    BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
    LOG_DIR = '.log'
    LOG_LOCATION = os.path.join(BASE_DIR, LOG_DIR)
    FAILURES_FILE = 'failures.txt'
    FAILURES_LOCATION = os.path.join(LOG_DIR, FAILURES_FILE)
    DEFAULT_CONFIG_FILE = 'config.json'
    ATTACHMENTS_DIR = 'attachments'
    REWRITE_DOWNLOAD_URL = True

    def __init__(self, config_file=None):
        self.config_file = config_file or self.DEFAULT_CONFIG_FILE
        self.last_failed_uuids = []
        self._create_log_location()
        self._read_failed_transfer_uuids()
        self.src, self.dest = self.get_config()

    def get_config(self):
        data = self._read_config()
        src = self._append_additional_config_data(data['src'])
        dest = self._append_additional_config_data(data['dest'])
        return src, dest

    @property
    def data_query(self):
        return {"_uuid": {"$in": self.last_failed_uuids}}

    def _create_log_location(self):
        if not os.path.isdir(self.LOG_LOCATION):
            os.makedirs(self.LOG_LOCATION)

    def _read_failed_transfer_uuids(self):
        if os.path.exists(self.FAILURES_LOCATION):
            with open(self.FAILURES_LOCATION, 'r') as f:
                self.last_failed_uuids = f.read().split('\n')[:-1]
            # burn after reading
            os.remove(self.FAILURES_LOCATION)

    def _read_config(self):
        with open(os.path.join(self.BASE_DIR, self.config_file), 'r') as f:
            config = json.loads(f.read())
        return config

    @staticmethod
    def _append_additional_config_data(data):
        asset_url = f"{data['kf_url']}/api/v2/assets/{data['asset_uid']}"
        return {
            **data,
            'assets_url': asset_url,
            'submission_url': f"{data['kc_url']}/api/v1/submissions",
            'forms_url': f"{data['kc_url']}/api/v1/forms",
            'headers': {'Authorization': f"Token {data['token']}"},
            'params': {'format': 'json'},
            'deployment_url': f'{asset_url}/deployment/',
            'xml_url': f'{asset_url}/data.xml',
            'data_url': f'{asset_url}/data',
        }
