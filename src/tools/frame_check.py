import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.load_config import *
import struct
from gendc_python.gendc_separator import descriptor as gendc
from PIL import Image  
import numpy as np
GDC_INTENSITY   = 0x0000000000000001

# to check the framecount
import ctypes

CONFIG_SUFFIX = 'config.json'



def write_log(w, h, prefix, framecount, output_directory):
    logfile_path = os.path.join(output_directory, prefix + 'frame_log.txt')
    print('log written in {}'.format(logfile_path))
    with open(logfile_path, mode='w') as ofs:
        ofs.write('{}x{}\n'.format(w, h))
        offset_frame_count = 0
        expected_frame_count = 0
        frame_drip = False

        for i, fc in enumerate(framecount):
            if i == 0:
                if ctypes.c_long(fc & 0xFFFFFFFF).value  == -1:
                    raise Exception("This U3V Camera does not support Frame count.")
                offset_frame_count = fc
                expected_frame_count = offset_frame_count
                ofs.write('offset_frame_count: {}\n'.format(expected_frame_count))

            frame_drop = fc != expected_frame_count

            if frame_drop:
                while expected_frame_count < fc:
                    ofs.write('{} : x\n'.format(expected_frame_count))
                    expected_frame_count += 1
            frame_drop = False
            ofs.write('{} : {}\n'.format(expected_frame_count, fc))
            expected_frame_count += 1

class FrameCheck:

    def __init__(self, dir_path, items, display_result=True):
        self.dir_path_ = dir_path
        self.items_ = items
        self.display_result_ = display_result

    def frame_check_non_bin(self, ext, blackpixel=False):
        if self.display_result_:
            print('{}({})'.format(self.dir_path_, ext))
        ext_items = sorted(self.items_)
        # print(categorized_items[ext])
        expected_idx = ext_items[0]
        num_dropped_frame = 0
        num_catch = 0
        num_dark = {'25':0, '50':0, '75':0, '100':0}
        for saved_idx in ext_items:
            while expected_idx != saved_idx:
                # print('expected: {}, actual: {}'.format(expected_idx, saved_idx))
                expected_idx += 1
                num_dropped_frame += 1
            expected_idx += 1
            num_catch += 1

            img_file_name = os.path.join(self.dir_path_, str(saved_idx) + '.' + ext)
            if not os.path.isfile(img_file_name):
                raise Exception('Image {} does not exist'.format(img_file_name))
            if blackpixel:
                numpydata = np.array(Image.open(img_file_name)  )  
                img_size = numpydata.size
                num_black = np.sum(numpydata == 0)
                black_ratio =  num_black * 100.00 / img_size
                if black_ratio >= 25.0:
                    num_dark['25'] += 1
                if black_ratio >= 50.0:
                    num_dark['50'] += 1
                if black_ratio >= 75.0:
                    num_dark['75'] += 1
                if black_ratio > 99.9:
                    num_dark['100'] += 1

        if self.display_result_:
            self.print_stats(ext_items[0], expected_idx-1, num_catch, num_dropped_frame, num_dark, blackpixel)
        return ext_items

    def frame_check_bin_prefix(self, config_file_path, blackpixel=False):
        if self.display_result_:
            print('{}/{}({})'.format(self.dir_path_, get_prefix(config_file_path), 'bin'))
        w, h, d, c = get_config_info(config_file_path)
        framesize = w * h * d * c
        expected_idx = 0
        offset_idx = 0
        num_dropped_frame = 0
        num_catch = 0

        ret = []

        for bin_idx, bf in enumerate(self.items_):
            bin_file = os.path.join(self.dir_path_, bf)

            with open(bin_file, mode='rb') as ifs:
                filecontent = ifs.read()   
                cursor = 0
                first_frame = True

                while cursor < len(filecontent):
                    try:
                        # TODO return NULL for non-gendc format
                        gendc_container = gendc.Container(filecontent[cursor:])
                        image_component_idx = gendc_container.get_1st_component_idx_by_typeid(GDC_INTENSITY)
                        image_component = gendc_container.get_component_by_index(image_component_idx)
                        part = image_component.get_part_by_index(0)
                        typespecific3 = part.get_typespecific_by_index(2)
                        saved_idx = int.from_bytes(typespecific3.to_bytes(8, 'little')[0:4], "little")
                        cursor = cursor + gendc_container.get_container_size()
                        ret.append(saved_idx)

                    except:
                        saved_idx = struct.unpack('I', filecontent[cursor:cursor+4])[0]
                        cursor = cursor + 4 + framesize
                        ret.append(saved_idx)

                    if first_frame and bin_idx == 0:
                        expected_idx = saved_idx
                        offset_idx = saved_idx
                        first_frame = False

                    while expected_idx != saved_idx:
                        expected_idx += 1
                        num_dropped_frame += 1

                    expected_idx += 1
                    num_catch += 1

        if self.display_result_:
            self.print_stats(offset_idx, expected_idx-1, num_catch, num_dropped_frame, None, blackpixel)
        return ret

    def print_stats(self, min_idx, max_idx, num_catch, num_dropped_frame, num_dark, blackpixel):
        num_total = max_idx - min_idx + 1
        stats = (num_total - num_dropped_frame) * 100.0 / num_total
        print('  frame catch rate     : {}%'.format(stats))
        print('  frame catch          : {} frames'.format(num_catch))
        print('  num frames           : {}'.format(num_total))
        print('  frames               : {} - {}'.format(min_idx, max_idx))
        if blackpixel and num_dark:
            print('  black pixels > 25%   : {}'.format(num_dark['25']))
            print('  black pixels > 50%   : {}'.format(num_dark['50']))
            print('  black pixels > 75%   : {}'.format(num_dark['75']))
            print('  black pixels > 99.9% : {}'.format(num_dark['100']))
            
   
                    
from tools.load_bin import *

def main():

    parser = argparse.ArgumentParser(description="Check frame catch rate")
    parser.add_argument('-d', '--directory', type=str, \
                        help='Directory that has saved files', required=True)
    parser.add_argument('-b', '--blackpixel', action='store_true', \
                        help='Check if image is mostly black')
    parser.add_argument('-p', '--prefix', type=str, default=None, \
                        help='Prefix of config file e.g. <prefix>-config.json')
    parser.add_argument('-f', '--format', type=str, default=None, \
                        help='File format')

    directory_name = parser.parse_args().directory
    blackpixel = parser.parse_args().blackpixel
    prefix = parser.parse_args().prefix
    fileformat = parser.parse_args().format

    dir_list = get_bin_directories(directory_name, [], prefix, fileformat)

    if len(dir_list) == 0:
        print('The directory containing bin files that matches the following conditions was not found.')
        print('prefix: {}'.format(prefix))
        print('format: {}'.format(fileformat))
    
    for camera_dir in dir_list:

        pti = PerformanceTestItems(camera_dir, prefix)
        extensions = image_ext if not fileformat else [fileformat]

        for ext in extensions:
            filtered_items_list, configs = pti.check_frame_catch_rate_of_ext(ext)

            for i, filtered_items in enumerate(filtered_items_list):

                fc = FrameCheck(camera_dir, filtered_items)
                if ext == 'bin':
                    w, h, d, c = get_config_info(os.path.join(camera_dir, configs[i]))
                    
                    framecount = fc.frame_check_bin_prefix(os.path.join(camera_dir, configs[i]), blackpixel)
                    w, h, d, c = get_config_info(os.path.join(camera_dir, configs[i]))
                    write_log(w, h, get_prefix(configs[i]), framecount, camera_dir)
                else:
                    _ = fc.frame_check_non_bin(ext, blackpixel)

if __name__ == "__main__":
    main()