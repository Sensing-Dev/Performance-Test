from ionpy import Node, Builder, Buffer, PortMap, Port, Param, Type, TypeCode
import numpy as np
import gendc_separator.descriptor as gendc

import datetime
import argparse
import sys
from pathlib import Path

import cv2

import os
os.add_dll_directory(os.path.join(os.environ["SENSING_DEV_ROOT"], "bin"))

import gi
gi.require_version("Aravis", "0.8")
from gi.repository import Aravis

import struct

import re
import json

log_display = True
saving_directory_prefix = "U3V-performance-test-with-display-"

def set_commandline_options():
    parser = argparse.ArgumentParser(description="Performance test for your U3V Camera")
    parser.add_argument('-d', '--directory', default='.', type=str, \
                        help='Directory to save log')
    parser.add_argument('-g', '--gain-key-name', default='Gain',type=str, \
                         help='Name of Gain key defined for GenICam feature')
    parser.add_argument('-e', '--exposuretime-key-name', default='ExposureTime', type=str, \
                        help='Name of ExposureTime key defined for GenICam feature')
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

    dev_info["Gain Key"] = args.gain_key_name
    dev_info["ExposureTime Key"] = args.exposuretime_key_name
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

    for k in ["Gain Key", "ExposureTime Key"]:
        if not device.is_feature_available(dev_info[k]):
            parser.print_help(sys.stderr)
            raise Exception("{0} is an invalid feature key to access {1}".format(dev_info[k], k))
        
    del device
    Aravis.shutdown()

    for key in dev_info:
        log_info_write("{0:>20s} : {1}".format(key, dev_info[key]))
    
    for key in test_info:
        log_info_write("{0:>20s} : {1}".format(key, test_info[key]))

    return dev_info, test_info

def get_bb_for_obtain_image(pixelformat):
    if pixelformat == "Mono8":
        return "image_io_u3v_cameraN_u8x2"
    elif pixelformat == "Mono10" or pixelformat == "Mono12":
        return "image_io_u3v_cameraN_u16x2"
    else:
        raise Exception("Currently not supported")

gain = 40
exposure = 400

if os.name == 'nt':
    module_name = 'ion-bb.dll'
elif os.name == 'posix':
    module_name = 'libion-bb.so'

def process_and_save(dev_info, test_info, output_directory_path, last_run):

    framecount_record = {}
    for i in range(dev_info["Number of Devices"]):
        framecount_record[i] = []

    builder = Builder()
    builder.set_target('host')
    builder.with_bb_module(module_name)

    # input port for the first BB ##############################################
    dispose_device = Port('dispose_device', Type(TypeCode.Uint, 1, 1), 0)
    gain_p = Port('gain', Type(TypeCode.Float, 64, 1), 1)
    exposuretime_p = Port('exposuretime', Type(TypeCode.Float, 64, 1), 1)

    # input port for the second BB #############################################
    dispose_writer = Port('dispose_writer', Type(TypeCode.Uint, 1, 1), 0)
    # if gendc
    payloadsize_p = Port('payloadsize', Type(TypeCode.Int, 32, 1), 0)
    # else
    wp = Port('width', Type(TypeCode.Int, 32, 1), 0)
    hp = Port('height', Type(TypeCode.Int, 32, 1), 0)
    color_channel_p = Port('color_channel', Type(TypeCode.Int, 32, 1), 0)

    # Params
    num_devices = Param('num_devices', str(dev_info["Number of Devices"]))
    pixel_format_ptr = Param('pixel_format_ptr', dev_info["PixelFormat"])
    frame_sync = Param('frame_sync', 'true')
    realtime_diaplay_mode = Param('realtime_diaplay_mode', test_info["Realtime-display mode"])
    gain_key = Param('gain_key', dev_info["Gain Key"])
    exposure_key = Param('exposure_key', dev_info["ExposureTime Key"])

    node = builder.add(get_bb_for_obtain_image(dev_info["PixelFormat"]))\
        .set_port([dispose_device, gain_p, exposuretime_p, ])\
        .set_param([num_devices, pixel_format_ptr, frame_sync, gain_key, exposure_key, realtime_diaplay_mode, ])
        
    # portmap
    port_map = PortMap()

    # input values
    gain_data = np.array([48.0] * dev_info["Number of Devices"])
    exposure_data = np.array([100.0] * dev_info["Number of Devices"])

    gains = Buffer(Type(TypeCode.Float, 64, 1), (dev_info["Number of Devices"],))
    exposures = Buffer(Type(TypeCode.Float, 64, 1), (dev_info["Number of Devices"],))
    gains.write(gain_data.tobytes(order='C'))
    exposures.write(exposure_data.tobytes(order='C'))
    
    port_map.set_buffer(gain_p, gains)
    port_map.set_buffer(exposuretime_p, exposures)

    # output values
    outputs = []
    data_type = np.uint8 if dev_info["PixelFormat"] == "Mono8" or dev_info["PixelFormat"] == "RGB8" \
        else np.uint16 if dev_info["PixelFormat"] == "Mono10" or dev_info["PixelFormat"] == "Mono12" \
        else np.uint8
    depth_of_buffer = np.iinfo(data_type).bits
    output_size = (dev_info["Width"], dev_info["Height"], )
    if dev_info["PixelFormat"] == "RGB8":
        output_size += (3,)
    for i in range(dev_info["Number of Devices"]):
        outputs.append(Buffer(Type(TypeCode.Uint, depth_of_buffer, 1), output_size))

    framecount = Buffer(Type(TypeCode.Uint, 32, 1), (dev_info["Number of Devices"], ))

    port_map.set_buffer_array(node.get_port('output'), outputs)
    port_map.set_buffer(node.get_port('frame_count'), framecount)

    #opencv 
    buf_size_opencv = (dev_info["Height"], dev_info["Width"])

    buffersize = dev_info["Height"] * dev_info["Width"]
    if dev_info["PixelFormat"] == "Mono10" or dev_info["PixelFormat"] == "Mono12":
        buffersize *= 2


    for x in range(test_info["Number of Frames"]):
        port_map.set_u1(dispose_device, last_run and x == test_info["Number of Frames"] - 1)

        # running the builder
        builder.run(port_map)

        for nd in range(dev_info["Number of Devices"]):
            output_bytes = outputs[nd].read(buffersize) 
            output_np_HxW = np.frombuffer(output_bytes, np.uint8).reshape(buf_size_opencv) if dev_info["PixelFormat"] == "Mono8" \
                else np.frombuffer(output_bytes, np.uint16).reshape(buf_size_opencv)
            cv2.imshow("image"+str(nd), output_np_HxW)
        cv2.waitKey(1)
        size_of_framecount = 4 * dev_info["Number of Devices"]

        for nd in range(dev_info["Number of Devices"]):
            start = 0 + nd * 4
            framecount_record[nd].append(int.from_bytes(framecount.read(size_of_framecount)[start:start+4], 'little'))

    if last_run:
        port_map.set_u1(dispose_device, True)

    return framecount_record


def write_log(output_directory, dev_info, framecount_record, last_run):

    print('log written in ')
    logfile = []
    ofs = []
    for ith_device in range(dev_info["Number of Devices"]):
        logfile.append(os.path.join(output_directory, 'camera-'+str(ith_device)+'-frame_log.txt'))
        ofs.append(open(logfile[ith_device], mode='w'))
        ofs[ith_device].write(str(dev_info["Width"])+'x'+str(dev_info["Height"])+'\n')
        print('\t{0}'.format(logfile[ith_device]))

        num_dropped_frames = 0

        current_frame = 0
        offset_frame_count = 0
        

        for i, fc in enumerate(framecount_record[ith_device]):
            if i == 0:
                offset_frame_count = fc
                expected_frame_count = offset_frame_count
                ofs[ith_device].write('offset_frame_count: ' + str(expected_frame_count) +'\n')

            if last_run and i == len(framecount_record[ith_device]) - 1:
                pass
            else:
                frame_drop = fc != expected_frame_count

                if frame_drop:
                    while expected_frame_count < fc : 
                        ofs[ith_device].write(str(expected_frame_count) + ' : x\n')
                        num_dropped_frames += 1
                        expected_frame_count += 1

                frame_drop = False
                ofs[ith_device].write(str(expected_frame_count) + ' : ' + str(fc) +'\n')
                expected_frame_count += 1

            if current_frame < fc:
                current_frame = fc
        total_num_frame = current_frame - offset_frame_count  + 1
        print("\t", (total_num_frame-num_dropped_frames) * 1.0 / total_num_frame)


    return True
            
if __name__ == "__main__":

    parser = set_commandline_options()
    dev_info, test_info = get_device_info(parser)

    for i in range(test_info["Number of Tests"]):
        ith_test_output_directory = os.path.join(test_info["Output Directory"], str(i))
        os.mkdir(ith_test_output_directory)

        framecount_record = process_and_save(dev_info, test_info, ith_test_output_directory, i == test_info["Number of Tests"] - 1)
        ret = write_log(ith_test_output_directory, dev_info, framecount_record, i == test_info["Number of Tests"] - 1)
    

    