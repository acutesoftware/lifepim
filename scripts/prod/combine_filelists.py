#!/usr/bin/python3
# coding: utf-8
# combine_filelist_by_type.py

import os
import sys
import csv
import glob

path_root =  os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + ".." ) 
print('path root = ' + str(path_root) )
sys.path.append(str(path_root))

import config as mod_cfg

src_file_pattern = 'files_*.csv'


def combine_by_extension(xtn):
    SRC_fldr = mod_cfg.filelist_op_fldr
    op_fldr = mod_cfg.filelist_merged_files
    op_file = os.path.join(op_fldr, 'ALL_files_' + xtn + '.csv')
    print('combining all filelists from folder - ' + SRC_fldr + '\ninto file ' + op_file)
    input('continue?')
    all_files = glob.glob(os.path.join(SRC_fldr,src_file_pattern))

    with open(op_file, 'w') as fop:
        fop.write('"name","album",')
        for f in all_files:
            rows, num_files = get_rows_from_file(f, xtn)
            if num_files > 0:
                fop.write(rows)
                print('Found ' + str(num_files) + ' in ' + str(f))

    print('done')

def get_rows_from_file(fname, xtn):
    rows = ''
    num_files = 0
    with open(fname, 'r') as fip:
        for line in fip:
            if xtn in line:
                num_files += 1
                rows += line

    return rows, num_files


if __name__ == '__main__':
    combine_by_extension('mp3')
    

