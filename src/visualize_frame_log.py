import os
import sys
from matplotlib import pyplot as plt
import numpy as np
import argparse
import json

def check_frame_catch(logfile):
    num_frames = 0
    num_skipped = 0
    skipped_frames = []
    with open(logfile) as f:
        lines = f.readlines()
        for line in lines:
            if 'offset' in line:
                offset = int(line.split(':')[-1])
            if ':' in line:
                num_frames += 1
                if 'x' in line:
                    num_skipped += 1
                    skipped_index = int(line.split(':')[0])
                    skipped_frames.append(skipped_index - offset)

    return (offset, num_frames-num_skipped, num_frames, skipped_frames)
                
def get_bin_directory_prefix():
    with open('kizashi_config.h') as f:
        lines = f.readlines()
        for line in lines:
            if 'SAVE_BIN_PATH_PRIFIX' in line:
                path_prefix = os.path.normpath(line.split("\"")[1])
                return os.path.split(path_prefix)
            
def list_all_directories():
    (parent_dir, prefix) = get_bin_directory_prefix()
    print('list all directories:')
    list_of_files = os.listdir(parent_dir)
    for i, file in enumerate(list_of_files):
        if prefix in file:
            print('\t'+str(i)+': '+file)
    idx = input("\nselect directories (type index):")
    return os.path.join(parent_dir, list_of_files[int(idx)])    

def get_stats(target_dir, ith_device, display_plot=False):
    percent = []
    skipped_frames_for_all_run = []

    num_runs = 0
    for d in os.listdir(target_dir):
        if os.path.isdir(os.path.join(target_dir, d)) and 'camera-0-frame_log.txt' in os.listdir(os.path.join(target_dir, d)):
            num_runs += 1

    plot_height = 2 * num_runs
    fig, axes = plt.subplots(num_runs, 1, figsize=(20,plot_height))
    fig.suptitle('skipped frames in all ' + str(num_runs) + ' runs')
    fig.tight_layout(rect=[0,0,1,0.96])

    for i in range(num_runs):
        log_file = os.path.join(target_dir, str(i), 'camera-'+str(ith_device)+'-frame_log.txt')
        (offset, caught_frames, all_frames, skipped_frames) = check_frame_catch(log_file)
        percent.append(caught_frames * 100.0 / all_frames)
        skipped_frames_for_all_run.append(skipped_frames)
        if display_plot:
            x = np.arange(all_frames)
            y = np.zeros(all_frames)
            for skipped_idx in skipped_frames_for_all_run[i]:
                y[skipped_idx] = 1
            axes[i].scatter(x, y)
            axes[i].set_ylim(0.5, 1.5)
            axes[i].set_yticks([])
    plt.savefig(os.path.join(target_dir, 'stat'+str(ith_device)+'.png'))
    print("image is saved under", os.path.join(target_dir, 'stat'+str(ith_device)+'.png'))
    return num_runs, percent

def main():

    parser = argparse.ArgumentParser(description="Performance test for your U3V Camera")
    parser.add_argument('-d', '--directory', type=str, \
                        help='Directory to save log', required=True)
    parser.add_argument('-nd', '--number-of-device', default=1, type=int, \
                        help='The number of devices')
    args = parser.parse_args()

    num_devices = args.number_of_device

    for n in range(num_devices):
        num_runs, percent = get_stats(args.directory, n, True)
        print('total run: ' + str(num_runs))
        print(percent)
        
    
if __name__ == "__main__":
    main()