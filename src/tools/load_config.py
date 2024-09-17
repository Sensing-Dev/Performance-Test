import json

Mono8 = 0x01080001
Mono10 = 0x01100003
Mono12 = 0x01100005
RGB8 = 0x02180014
BGR8 = 0x02180015
BayerBG8 = 0x0108000B
BayerBG10 = 0x0110000F
BayerBG12 = 0x01100013

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