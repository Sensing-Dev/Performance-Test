import argparse
import os

import re

CONFIG_SUFFIX = 'config.json'
image_ext = ['bin', 'png', 'jpg', 'jpeg', 'png', 'bmp', 'raw']

class PerformanceTestItems:
    def __init__(self, dir_path, prefix=None):
        self.dir_path_ = dir_path

        self.prefix_ = prefix

        self.all_items_in_dir_ = os.listdir(dir_path)

    def get_ext_items(self, ext):
        if ext == 'bin':
            return [f for f in self.all_items_in_dir_ if f.endswith(".bin")] 
        else:
            return [int(f.split('.')[0]) for f in self.all_items_in_dir_ if f.endswith(ext)]

    def get_config_list(self):
        if self.prefix_:
            return [self.prefix_ + CONFIG_SUFFIX]
        else:
            return [f for f in self.all_items_in_dir_ if f.endswith(CONFIG_SUFFIX)]

    def check_frame_catch_rate_of_ext(self, ext):

        filtered_items_by_ext = self.get_ext_items(ext)

        ret_item_list = []
        ret_configs = []

        if len(filtered_items_by_ext) > 0:
            if ext == 'bin':
                filtered_items_by_ext = sorted(filtered_items_by_ext, key=lambda s: int(re.search(r'-(\d+)\.bin', s).group(1)))
                for config_file_name in self.get_config_list():
                    ith_prefix = config_file_name.split(CONFIG_SUFFIX)[0]
                    filtered_items_by_prefix = [f for f in filtered_items_by_ext if f.startswith(ith_prefix)]
                    ret_item_list.append(filtered_items_by_prefix)
                    ret_configs.append(config_file_name)

            else:
                ret_item_list.append(filtered_items_by_ext)

        return ret_item_list, ret_configs

    




################################################################################
# 
# return the list of path of directory containing config file
# 
################################################################################
def get_bin_directories(dir, dir_list, prefix=None, fileformat=None):
    # return directory including *-config.json
    if not (os.path.exists(dir) and os.path.isdir(dir)):
        raise Exception("Directory " + dir + " does not exist")

    dir_content = [f for f in os.listdir(dir) if f.endswith(CONFIG_SUFFIX)]
    if len(dir_content) > 0:
        if fileformat:
            dir_content = [f for f in os.listdir(dir) if f.endswith(fileformat)]
            if len(dir_content) > 0:
                dir_list.append(dir)
        else:
            dir_list.append(dir)
    else:
        dir_content = [d for d in os.listdir(dir) if os.path.isdir(os.path.join(dir, d))]
        for d in dir_content:
            dir_list = get_bin_directories(os.path.join(dir, d), dir_list, prefix, fileformat)
    return dir_list


        

    
