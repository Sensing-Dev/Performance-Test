import json

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.util import *

CONFIG_SUFFIX = 'config.json'

def get_prefix(config_path):
    config_file_name = os.path.basename(config_path)
    return config_file_name.split(CONFIG_SUFFIX)[0]

def get_config_info(config_file_path):
    with open(config_file_path, mode='r') as f:
        config = json.loads(f.read())
        w = config["width"]
        h = config["height"]
        d = 2 if config["pfnc_pixelformat"] == Mono10 or config["pfnc_pixelformat"] == Mono12 \
            else 1
        c = 3 if config["pfnc_pixelformat"] == RGB8 or config["pfnc_pixelformat"] == BGR8 \
            else 1
    return w, h, d, c