# without saving
import numpy as np
import ctypes

# saving
import struct

# common
from ionpy import Node, Builder, Buffer, PortMap, Port, Param, Type, TypeCode
from  gendc_python.gendc_separator import descriptor as gendc

import datetime, time
import argparse
from pathlib import Path

import os
if os.name == 'nt':
    os.add_dll_directory(os.path.join(os.environ["SENSING_DEV_ROOT"], "bin"))

import gi
gi.require_version("Aravis", "0.8")
from gi.repository import Aravis

import re
import json

log_display = True


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
    
    parser.add_argument('-rt', '--realtime-display-mode', \
                        action='store_true', help='Image capture in Realtime-display mode.')
    parser.add_argument('-re', '--realtime-evaluation-mode', \
                        action='store_true', help='Run performance test in Realtime-evaluation.')
    parser.add_argument('-db', '--delete-bins', \
                        action='store_true', help='Delete bin files in --realtime-ecaluation-mode.')
    return parser

def log_write(logtype, msg):
    if log_display:
        print("[LOG {0}][{1}] {2}".format(Path(__file__).name, logtype, msg))

def log_info_write(msg):
    log_write("INFO", msg)

def log_warning_write(msg):
    log_write("WARNING", msg)

def log_status_write(msg):
    log_write("STATUS", msg)

def get_prefix(ith_device):
    return 'camera-' + str(ith_device) + '-'

def get_device_info(parser):
    dev_info ={}
    test_info = {}

    # get user input
    args = parser.parse_args()

    test_info["Output Directory"] = args.directory
    test_info["Number of Frames"] = args.number_of_frames
    test_info["Number of Tests"] = args.number_of_tests
    test_info["Realtime-display mode"] = args.realtime_display_mode
    test_info["Delete Bin files"] = args.delete_bins
    test_info["Realtime-evaluation mode"] = args.realtime_evaluation_mode

    dev_info["Number of Devices"] = args.number_of_device

    saving_directory_prefix = "U3V-performance-test-"
    if test_info["Realtime-evaluation mode"]:
        # if this is true, ion-kit pipeline does not save bin files
        saving_directory_prefix = saving_directory_prefix + 'without-saving-'

    if not os.path.isdir(test_info["Output Directory"]):
        os.mkdir(test_info["Output Directory"])
    # Create U3V-performance-test-YYYY-MM-DD-HH-mm-SS
    test_info["Output Directory"] = os.path.join(test_info["Output Directory"], 
                                                saving_directory_prefix + datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
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

def get_bb_for_obtain_image(save_as_bin, gendc, pixelformat):
    if save_as_bin and gendc:
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
    
def get_bytedepth(int_pf):
    if int_pf == Mono8 or int_pf == RGB8 or int_pf == BGR8 or int_pf == BayerBG8:
        return 1
    elif int_pf == Mono10 or int_pf == Mono12 or int_pf == BayerBG10 or int_pf == BayerBG12:
        return 2
    else:
        raise Exception(int_pf + " is not supported as default in this tool.\nPlease update getPixelFormatInInt() ")

def open_and_check(output_directory, ith_sensor):
    f = open(os.path.join(output_directory, get_prefix(ith_sensor) + "config.json"))
    config = json.loads(f.read())
    f.close()
    return config

def open_bin_file(bin_file):
    ifs = open(bin_file, mode='rb')
    filecontent = ifs.read()
    ifs.close()
    return filecontent

def get_frame_size(ith_sensor_config):   
    w = ith_sensor_config["width"]
    h = ith_sensor_config["height"]
    d = 2 if ith_sensor_config["pfnc_pixelformat"] == Mono10 or ith_sensor_config["pfnc_pixelformat"] == Mono12 \
        else 1
    c = 3 if ith_sensor_config["pfnc_pixelformat"] == RGB8 or ith_sensor_config["pfnc_pixelformat"] == BGR8 \
        else 1
    return w * h * d * c

def load_and_get_framecount(output_directory, num_devices):

    log_status_write("Post recording Process... Framecount data is generated.")

    framecount_record = {}

    for ith_sensor in range(num_devices):
        config = open_and_check(output_directory, ith_sensor)
        framecount_record[ith_sensor] = []

        bin_files = [f for f in os.listdir(output_directory) if f.startswith(get_prefix(ith_sensor)) and f.endswith(".bin")]
        bin_files = sorted(bin_files, key=lambda s: int(re.search(r'\d+', s).group()))

        framesize = get_frame_size(config)

        for bf in bin_files:
            bin_file = os.path.join(output_directory, bf)

            with open(bin_file, mode='rb') as ifs:
                filecontent = ifs.read()   
                cursor = 0

                while cursor < len(filecontent):
                    try:
                        # TODO return NULL for non-gendc format
                        gendc_container = gendc.Container(filecontent[cursor:])
                        image_component_idx = gendc_container.get_1st_component_idx_by_typeid(GDC_INTENSITY)
                        image_component = gendc_container.get_component_by_index(image_component_idx)
                        part = image_component.get_part_by_index(0)
                        typespecific3 = part.get_typespecific_by_index(2)
                        frame_count = int.from_bytes(typespecific3.to_bytes(8, 'little')[0:4], "little")
                        framecount_record[ith_sensor].append(frame_count)
                        cursor = cursor + gendc_container.get_container_size()

                    except:
                        framecount_record[ith_sensor].append(struct.unpack('I', filecontent[cursor:cursor+4])[0])
                        cursor = cursor + 4 + framesize

    return framecount_record


def process_and_save(dev_info, test_info, output_directory_path, eval_while_recording):

    # sys.exit(1)

    builder = Builder()
    builder.set_target('host')
    builder.with_bb_module('ion-bb')

    # input port for the second BB #############################################
    # if gendc
    payloadsize_p = Port('payloadsize', Type(TypeCode.Int, 32, 1), 0)
    # else
    wp = Port('width', Type(TypeCode.Int, 32, 1), 0)
    hp = Port('height', Type(TypeCode.Int, 32, 1), 0)

    # Params
    num_devices = Param('num_devices', str(dev_info["Number of Devices"]))
    frame_sync = Param('frame_sync', 'true')
    realtime_display_mode = Param('realtime_display_mode', test_info["Realtime-display mode"])

    output_directory = Param("output_directory", output_directory_path)

    # the first BB: Obtain GenDC/images
    node = builder.add(get_bb_for_obtain_image(not eval_while_recording, dev_info["GenDCStreamingMode"], dev_info["PixelFormat"]))\
        .set_param([num_devices, frame_sync, realtime_display_mode, ])
    
    # the second BB: optional
    if eval_while_recording:
        output_p = node.get_port('output')
        frame_count_p = node.get_port('frame_count')
        # output values
        data_type = np.uint8 if get_bytedepth(eval(dev_info["PixelFormat"])) == 1 else np.uint16
        
        outputs = []
        output_datas = []
        output_size = (dev_info["Height"], dev_info["Width"], )
        if dev_info["PixelFormat"] == "RGB8" or dev_info["PixelFormat"] == "BGR8":
            output_size += (3,)
        fcdatas = []
        frame_counts = []
        for i in range(dev_info["Number of Devices"]):
            output_datas.append(np.full(output_size, fill_value=0, dtype=data_type))
            outputs.append(Buffer(array= output_datas[i]))
            fcdatas.append(np.zeros(1, dtype=np.uint32))
            frame_counts.append(Buffer(array=fcdatas[i]))

        output_p.bind(outputs)
        frame_count_p.bind(frame_counts)

        framecount_record = {}
        for i in range(dev_info["Number of Devices"]):
            framecount_record[i] = []

        log_status_write("Recording and evaluating Process... Framecount is stored during the record.")

        for x in range(test_info["Number of Frames"]):
            builder.run()

            for nd in range(dev_info["Number of Devices"]):
                framecount_record[nd].append(fcdatas[i][0])
        return framecount_record
    else:
        prefix_params = [Param('prefix', get_prefix(0)), Param('prefix', get_prefix(1))]
        terminators = [Buffer(Type(TypeCode.Int, 32, 1), ()), Buffer(Type(TypeCode.Int, 32, 1), ())]
        out_nodes = []

        if dev_info["GenDCStreamingMode"]:
            for ith_device in range(dev_info["Number of Devices"]):
                out_nodes.append(builder.add(get_bb_for_save_image(dev_info["GenDCStreamingMode"], dev_info["PixelFormat"]))\
                    .set_iport([node.get_port('gendc')[ith_device], node.get_port('device_info')[ith_device], payloadsize_p, ])\
                    .set_param([prefix_params[ith_device], output_directory]))
            
        else:
            for ith_device in range(dev_info["Number of Devices"]):
                out_nodes.append(builder.add(get_bb_for_save_image(dev_info["GenDCStreamingMode"], dev_info["PixelFormat"]))\
                    .set_iport([
                        node.get_port('output')[ith_device], 
                        node.get_port('device_info')[ith_device], 
                        node.get_port('frame_count')[ith_device], 
                        wp, hp, ])\
                    .set_param([prefix_params[ith_device], output_directory]))
   
        if dev_info["GenDCStreamingMode"]:
            payloadsize_p.bind(dev_info["PayloadSize"])
        else:
            wp.bind(dev_info["Width"])
            hp.bind(dev_info["Height"])

        # output values 
        for ith_device in range(dev_info["Number of Devices"]):
            out_nodes[ith_device].get_port('output').bind(terminators[ith_device])

        log_status_write("Recording Process... Bin files are generated.")

        for x in range(test_info["Number of Frames"]):
            builder.run()

        return load_and_get_framecount(output_directory_path, dev_info["Number of Devices"])

def write_log(output_directory, dev_info, framecount_record, last_run):

    log_status_write("Post Recording Process... A log for frameskip will be generated.")

    print('log written in ')
    logfile = []
    ofs = []
    for ith_device in range(dev_info["Number of Devices"]):
        logfile.append(os.path.join(output_directory, get_prefix(ith_device)+'frame_log.txt'))
        ofs.append(open(logfile[ith_device], mode='w'))
        ofs[ith_device].write(str(dev_info["Width"])+'x'+str(dev_info["Height"])+'\n')
        print('\t{0}'.format(logfile[ith_device]))

        num_dropped_frames = 0

        current_frame = 0
        offset_frame_count = 0
        

        for i, fc in enumerate(framecount_record[ith_device]):
            if i == 0:
                if ctypes.c_long(fc & 0xFFFFFFFF).value  == -1:
                    raise Exception("This U3V Camera does not support Frame count.")
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

def delete_bin_files(output_directory, ith_sensor):
    log_status_write("Post Recording Process... Deleting bin files.")
    bin_files = [f for f in os.listdir(output_directory) if f.startswith(get_prefix(ith_sensor)) and f.endswith(".bin")]
    for i, bf in enumerate(bin_files):
        bin_file = os.path.join(output_directory, bf)
        os.remove(bin_file)
            
if __name__ == "__main__":

    parser = set_commandline_options()
    dev_info, test_info = get_device_info(parser)

    for i in range(test_info["Number of Tests"]):
        start = time.time()

        ith_test_output_directory = os.path.join(test_info["Output Directory"], str(i))
        os.mkdir(ith_test_output_directory)

        ret = process_and_save(dev_info, test_info, ith_test_output_directory, test_info["Realtime-evaluation mode"])

        if test_info["Delete Bin files"]:
            for nd in range(dev_info["Number of Devices"]):
                delete_bin_files(ith_test_output_directory, nd)
        ret = write_log(ith_test_output_directory, dev_info, ret, i == test_info["Number of Tests"] - 1)

        end = time.time()
        print(f"test-{i} time in total(s) for {test_info['Number of Frames']} frames:", end - start)


    