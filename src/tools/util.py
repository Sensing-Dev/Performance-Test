GDC_INTENSITY   = 0x0000000000000001
Mono8 = 0x01080001
Mono10 = 0x01100003
Mono12 = 0x01100005
RGB8 = 0x02180014
BGR8 = 0x02180015
BayerBG8 = 0x0108000B
BayerBG10 = 0x0110000F
BayerBG12 = 0x01100013
gain = 40
exposure = 400

def get_pixelformat_in_int(str_pf):
    if str_pf == "Mono8":
        return Mono8
    elif str_pf == "Mono10":
        return Mono10
    elif str_pf == "Mono12":
        return Mono12
    elif str_pf == "RGB8":
        return RGB8
    elif str_pf == "BGR8":
        return BGR8
    elif str_pf == "BayerBG8":
        return BayerBG8
    elif str_pf == "BayerBG10":
        return BayerBG10
    elif str_pf == "BayerBG12":
        return BayerBG12
    else:
        raise Exception(str_pf + " is not supported as default in this tool.\nPlease update getPixelFormatInInt() ")