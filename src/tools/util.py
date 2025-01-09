from gendc_python.genicam import tool as genicam

GDC_INTENSITY = 0x0000000000000001
Mono8 = genicam.pfnc_convert_pixelformat("Mono8")
Mono10 = genicam.pfnc_convert_pixelformat("Mono10")
Mono12 = genicam.pfnc_convert_pixelformat("Mono12")
RGB8 = genicam.pfnc_convert_pixelformat("RGB8")
BGR8 = genicam.pfnc_convert_pixelformat("BGR8")
BayerBG8 = genicam.pfnc_convert_pixelformat("BayerBG8")
BayerBG10 = genicam.pfnc_convert_pixelformat("BayerBG10")
BayerBG12 = genicam.pfnc_convert_pixelformat("BayerBG12")
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
