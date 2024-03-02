from ionpy import Node, Builder, Buffer, PortMap, Port, Param, Type, TypeCode
import numpy as np
from  gendc_python.gendc_separator import descriptor as gendc

import datetime
import argparse
import sys
from pathlib import Path

import os
os.add_dll_directory(os.path.join(os.environ["SENSING_DEV_ROOT"], "bin"))

import gi
gi.require_version("Aravis", "0.8")
from gi.repository import Aravis

import struct

import re
import json

log_display = True
saving_directory_prefix = "U3V-performance-test-"

def set_commandline_options():
    parser = argparse.ArgumentParser(description="Performance test for your U3V Camera")
    parser.add_argument('-d', '--directory', default='.', type=str, \
                        help='Directory to save log')
    parser.add_argument('-nd', '--number-of-device', default=1, type=int, \
                        help='The number of devices')
    parser.add_argument('-nf', '--number-of-frames', default=100, type=int, \
                        help='The number of frames to obtain per test')
    parser.add_argument('-nt', '--number-of-tests', default=2, type=int, \
                        help='The number of tests to perform in this script')
    parser.add_argument('-rt', '--realtime-display-mode', choices=["true", "false"], default='false', type=str, \
                        help='Switch image capture mode')

    return parser

def log_write(logtype, msg):
    if log_display:
        print("[LOG {0}][{1}] {2}".format(Path(__file__).name, logtype, msg))

def log_info_write(msg):
    log_write("INFO", msg)

def log_warning_write(msg):
    log_write("WARNING", msg)

def is_realtime_display(userinput):
    if not userinput:
        return False
    
    if userinput.lower() == 'on':
        return True
    else:
        False

def get_device_info(parser):
    dev_info ={}
    test_info = {}

    # get user input
    args = parser.parse_args()

    test_info["Output Directory"] = args.directory
    test_info["Number of Frames"] = args.number_of_frames
    test_info["Number of Tests"] = args.number_of_tests
    test_info["Realtime-display mode"] = args.realtime_display_mode

    dev_info["Number of Devices"] = args.number_of_device

    if not os.path.isdir(test_info["Output Directory"]):
        os.mkdir(test_info["Output Directory"])
    # Create U3V-performance-test-YYYY-MM-DD-HH-mm-SS
    test_info["Output Directory"] = os.path.join(test_info["Output Directory"], saving_directory_prefix + datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
    os.mkdir(test_info["Output Directory"])

    # Access to the device
    Aravis.update_device_list()
    connected_num_device = Aravis.get_n_devices()
    if connected_num_device == 0:
        Aravis.shutdown()
        raise Exception("No device was found.")
    first_camera = Aravis.get_device_id(0)
    device = Aravis.Camera.new(first_camera).get_device()

    if device.is_feature_available("OperationMode"):
        dev_info["OperationMode"] = device.get_string_feature_value("OperationMode")
        expected_num_device = 1 if "Came1" in dev_info["OperationMode"] else 2
        if expected_num_device != dev_info["Number of Devices"]:
            log_warning_write("While {0} is set to {1}, {2} is set to {3} (Default: 1)".format("OperationMode", dev_info["OperationMode"], "Number of Devices", dev_info["Number of Devices"]))
            dev_info["Number of Devices"] = expected_num_device

    dev_info["GenDCStreamingMode"] = False
    if device.is_feature_available("GenDCDescriptor") and device.is_feature_available("GenDCStreamingMode"):
        if device.get_string_feature_value("GenDCStreamingMode"):
            dev_info["GenDCStreamingMode"] = True

    dev_info["Width"] = device.get_integer_feature_value("Width")
    dev_info["Height"] = device.get_integer_feature_value("Height")
    dev_info["PayloadSize"] = device.get_integer_feature_value("PayloadSize")
    dev_info["PixelFormat"] = device.get_string_feature_value("PixelFormat")
        
    del device
    Aravis.shutdown()

    for key in dev_info:
        log_info_write("{0:>20s} : {1}".format(key, dev_info[key]))
    
    for key in test_info:
        log_info_write("{0:>20s} : {1}".format(key, test_info[key]))

    return dev_info, test_info

def get_bb_for_obtain_image(gendc, pixelformat):
    if gendc:
        return 'image_io_u3v_gendc'

    if pixelformat == "Mono8":
        return "image_io_u3v_cameraN_u8x2"
    elif pixelformat == "Mono10" or pixelformat == "Mono12":
        return "image_io_u3v_cameraN_u16x2"
    elif pixelformat == "RGB8" or pixelformat == "BGR8":
        return "image_io_u3v_cameraN_u8x3"
    else:
        raise Exception("Currently not supported")
    
def get_bb_for_save_image(gendc, pixelformat):
    if gendc:
        return 'image_io_binary_gendc_saver'

    if pixelformat == "Mono8":
        return "image_io_binarysaver_u8x2"
    elif pixelformat == "Mono10" or pixelformat == "Mono12":
        return "image_io_binarysaver_u16x2"
    elif pixelformat == "RGB8" or pixelformat == "BGR8":
        return "image_io_binarysaver_u8x3"
    else:
        raise Exception("Currently not supported")

GDC_INTENSITY   = 0x0000000000000001
PFNC_Mono8 = 0x01080001
PFNC_Mono10 = 0x01100003
PFNC_Mono12 = 0x01100005
PFNC_RGB8 = 0x02180014
PFNC_BGR8 = 0x02180015
gain = 40
exposure = 400

if os.name == 'nt':
    module_name = 'ion-bb.dll'
elif os.name == 'posix':
    module_name = 'libion-bb.so'

def process_and_save(dev_info, test_info, output_directory_path, last_run):

    # sys.exit(1)

    builder = Builder()
    builder.set_target('host')
    builder.with_bb_module(module_name)

    # input port for the second BB #############################################
    # if gendc
    payloadsize_p = Port('payloadsize', Type(TypeCode.Int, 32, 1), 0)
    # else
    wp = Port('width', Type(TypeCode.Int, 32, 1), 0)
    hp = Port('height', Type(TypeCode.Int, 32, 1), 0)

    # Params
    num_devices = Param('num_devices', str(dev_info["Number of Devices"]))
    frame_sync = Param('frame_sync', 'true')
    realtime_diaplay_mode = Param('realtime_diaplay_mode', test_info["Realtime-display mode"])

    output_directory = Param("output_directory", output_directory_path)

    # the first BB
    node = builder.add(get_bb_for_obtain_image(dev_info["GenDCStreamingMode"], dev_info["PixelFormat"]))\
        .set_param([num_devices, frame_sync, realtime_diaplay_mode, ])
        
    # the second BB
    if dev_info["GenDCStreamingMode"]:
        node = builder.add(get_bb_for_save_image(dev_info["GenDCStreamingMode"], dev_info["PixelFormat"]))\
            .set_iport([node.get_port('gendc'), node.get_port('device_info'), payloadsize_p, ])\
            .set_param([num_devices, output_directory, 
                        Param('input_gendc.size', dev_info["Number of Devices"]),
                        Param('input_deviceinfo.size', dev_info["Number of Devices"]) ])
    else:
        node = builder.add(get_bb_for_save_image(dev_info["GenDCStreamingMode"], dev_info["PixelFormat"]))\
            .set_iport([node.get_port('output'), \
                        node.get_port('device_info'), node.get_port('frame_count'), wp, hp, ])\
            .set_param([num_devices, output_directory, \
                    Param('input_images.size', dev_info["Number of Devices"]), \
                    Param('input_deviceinfo.size', dev_info["Number of Devices"]) ])

    terminator = node.get_port('output')
   
    if dev_info["GenDCStreamingMode"]:
        payloadsize_p.bind(dev_info["PayloadSize"])
    else:
        wp.bind(dev_info["Width"])
        hp.bind(dev_info["Height"])

    # output values 
    out = Buffer(Type(TypeCode.Int, 32, 1), ())
    terminator.bind(out)

    for x in range(test_info["Number of Frames"]):
        builder.run()

def open_and_check(output_directory):
    f = open(os.path.join(output_directory, "config.json"))
    config = json.loads(f.read())
    f.close()
    return config

def get_frame_size(ith_sensor_config):   
    w = ith_sensor_config["width"]
    h = ith_sensor_config["height"]
    d = 2 if ith_sensor_config["pfnc_pixelformat"] == PFNC_Mono10 or ith_sensor_config["pfnc_pixelformat"] == PFNC_Mono12 \
        else 1
    c = 3 if ith_sensor_config["pfnc_pixelformat"] == PFNC_RGB8 or ith_sensor_config["pfnc_pixelformat"] == PFNC_BGR8 \
        else 1
    return w * h * d * c

def write_log(output_directory, WxH, delete_bin=True):

    config = open_and_check(output_directory)
    num_devices = config["num_device"]

    num_dropped_frames = [0] * num_devices
    frame_drop = [False] * num_devices
    offset_frame_count = [0] * num_devices
    ith_device_framecount = [0] * num_devices
    expected_frame_count = []

    bin_files = [f for f in os.listdir(output_directory) if f.startswith("raw-") and f.endswith(".bin")]
    bin_files = sorted(bin_files, key=lambda s: int(re.search(r'\d+', s).group()))

    print('log written in ')
    logfile = []
    ofs = []
    for ith_device in range(num_devices):
        logfile.append(os.path.join(output_directory, 'camera-'+str(ith_device)+'-frame_log.txt'))
        ofs.append(open(logfile[ith_device], mode='w'))
        ofs[ith_device].write(str(config["sensor"+str(ith_device+1)]['width'])+'x'+str(config["sensor"+str(ith_device+1)]['height'])+'\n')
        print('\t{0}'.format(logfile[ith_device]))


    framesize = []
    for ith_device in range(num_devices):
        framesize.append(get_frame_size(config["sensor"+str(ith_device+1)]))
    
    for bf in bin_files:
        bin_file = os.path.join(output_directory, bf)
        ifs = open(bin_file, mode='rb')
        filecontent = ifs.read()
        ifs.close()

        cursor = 0

        while cursor < len(filecontent):
            for ith_device in range(num_devices):
                
                try:
                    # TODO return NULL for non-gendc format
                    gendc_descriptor = gendc.Container(filecontent[cursor:])
                    gendc_descriptor = gendc.Container(filecontent[cursor:])
                    image_component = gendc_descriptor.get_first_get_datatype_of(GDC_INTENSITY)
                    typespecific3 = gendc_descriptor.get("TypeSpecific", image_component, 0)[2]
                    ith_device_framecount[ith_device] = int.from_bytes(typespecific3.to_bytes(8, 'little')[0:4], "little")
                    cursor = cursor + gendc_descriptor.get_container_size()

                except:
                    ith_device_framecount[ith_device] = struct.unpack('I', filecontent[cursor:cursor+4])[0]
                    cursor = cursor + 4 + framesize[ith_device]

                if len(expected_frame_count) <= ith_device:
                    expected_frame_count.append(ith_device_framecount[ith_device])
                    offset_frame_count[ith_device] = expected_frame_count[ith_device]
                    ofs[ith_device].write('offset_frame_count: ' + str(expected_frame_count[ith_device]) +'\n')
                    

                frame_drop[ith_device] = (ith_device_framecount[ith_device] != expected_frame_count[ith_device])
                

                if frame_drop[ith_device]:
                    while expected_frame_count[ith_device] < ith_device_framecount[ith_device] : 
                        ofs[ith_device].write(str(expected_frame_count[ith_device]) + ' : x\n')
                        num_dropped_frames[ith_device] += 1
                        expected_frame_count[ith_device] += 1

                frame_drop[ith_device] = False
                ofs[ith_device].write(str(expected_frame_count[ith_device]) + ' : ' + str(ith_device_framecount[ith_device]) +'\n')
                expected_frame_count[ith_device] += 1

    for ith_device in range(num_devices):
        total_num_frame = ith_device_framecount[ith_device] - offset_frame_count[ith_device]  + 1
        print((total_num_frame-num_dropped_frames[ith_device]) * 1.0 / total_num_frame)
        ofs[ith_device].write(str((total_num_frame-num_dropped_frames[ith_device]) * 1.0 / total_num_frame) + '\n')
        ofs[ith_device].close()

    if delete_bin:
        for i, bf in enumerate(bin_files):
            bin_file = os.path.join(output_directory, bf)
            os.remove(bin_file)
    return True
            
if __name__ == "__main__":

    parser = set_commandline_options()
    dev_info, test_info = get_device_info(parser)

    for i in range(test_info["Number of Tests"]):
        ith_test_output_directory = os.path.join(test_info["Output Directory"], str(i))
        os.mkdir(ith_test_output_directory)

        process_and_save(dev_info, test_info, ith_test_output_directory, i == test_info["Number of Tests"] - 1)
        ret = write_log(ith_test_output_directory, (dev_info["Width"], dev_info["Height"]))
    

    