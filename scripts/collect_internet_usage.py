#!/usr/bin/python3
# coding: utf-8
# combine_filelist_by_type.py

import os
import sys
import csv
import glob

path_root =  r"N:\duncan\C\user\docs\PC\internet\download-logs\internode_dl"
print('path root = ' + str(path_root) )
sys.path.append(str(path_root))

src_file_pattern = '*Internode-RESIDENTIAL_NBN-data-usage.csv'
op_file = r"N:\duncan\C\user\docs\PC\internet\download-logs\internode_dl\ALL_internet_usage.csv"
print('output file = ' + str(op_file) )

def get_rows_from_file(f, yr):
    rows = ''
    with open(f, 'r') as fip:
        csv_reader = csv.reader(fip)
        next(csv_reader)  # Skip header row
        for line in csv_reader:
            if len(line) >= 2:
                #print(line[0])
                date = yr + '-' + line[0][3:5] + '-' + line[0][0:2]
                download_gb = line[1].replace('GB','').strip()
                rows += f'"{date}","{download_gb}"\n'

    return rows

def get_year_from_filename(fname):
    base = os.path.basename(fname)
    return base[0:4]



def main():
    print('combining all usage files from folder - ' + path_root + '\ninto file ' + op_file)
    all_files = glob.glob(os.path.join(path_root,src_file_pattern))

    with open(op_file, 'w') as fop:
        fop.write('"Date","Download (GB)"\n')
        for f in all_files:
            rows = get_rows_from_file(f, get_year_from_filename(f))
            if len(rows) > 0:
                fop.write(rows)

    print('done')

main()