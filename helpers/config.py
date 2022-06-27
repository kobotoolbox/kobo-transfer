import json
import os
import pathlib

from .singleton import Singleton


class Config(metaclass=Singleton):
    CONFIG_FILE = 'config.json'
    BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
    TEMP_DIR = '/tmp'
    REWRITE_DOWNLOAD_URL = True

    def __init__(self):
        self.old, self.new = self.get_config()

    def get_config(self):
        data = self._read_config()
        old = self._append_additional_config_data(data['old'])
        new = self._append_additional_config_data(data['new'])
        return old, new

    def _read_config(self):
        with open(os.path.join(self.BASE_DIR, self.CONFIG_FILE), 'r') as f:
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
