import json
import os
from . import CONF_PATH


class ConfigLoader(object):
    def __init__(self):
        production_config = os.path.join(CONF_PATH, 'prod.json')
        default_config = os.path.join(CONF_PATH, 'default.json')
        config_file = default_config
        if os.path.exists(production_config):
            config_file = production_config

        with open(config_file) as json_file:
            json_data = json.load(json_file)
            self.config = json_data

    def __getitem__(self, key):
        return self.config.get(key)

    def __setitem__(self, key, value):
        self.config[key] = value
