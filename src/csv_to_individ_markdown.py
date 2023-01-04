#!/usr/bin/python3
# coding: utf-8
# csv_to_individ_markdown.py
# takes a CSV file and generates individual markdown files for each row
# used for free form datasets in PIMs like Obsidian or general notes.

import os 
import sys
import time
import config as mod_cfg

op_fldr = os.path.join(mod_cfg.export_data_folder_base)


def process_markdown(tbl_name, tbl_desc, tbl_ip):
    with open(tbl_ip, 'r') as fip:
        raw = fip.readlines()

    hdr = []
    for row_num, line in enumerate(raw):
        cols = line.split(',')
        if row_num == 0:
            hdr = make_clean_header(line)
        else:

            ndx_id = make_index_col(row_num, cols[0])
            fname = ndx_id + '.md'
            op_file = os.path.join(op_fldr, tbl_name, fname)
            txt = make_markdown(tbl_desc, row_num, cols, hdr)
            #print(txt)
            #print(' generating ' + op_file)
            with open(op_file, 'w') as fop:
                fop.write(txt)
    
    print('Processed ' + str(row_num) + ' ' + tbl_desc + ' to "_data\\' + tbl_name + '" via ' + tbl_ip )

def make_clean_header(raw_list):
    op = []
    h_cols = raw_list.split(',')
    #print('h_cols = ' + str(h_cols))
    for h_col in h_cols:
        new_name = ''
        for ch in h_col.strip('\n'):
            if ch in '1234567890qwertyuiopasdfghjklzxcvbnm_ABCDEFGHIJKLMNOPQURSTUVWXYZ':
                new_name += ch
            #else:
            #    new_name += '_'
        op.append(new_name)
    print('hdr = ' + str(op))
    return op



def make_markdown(tbl_desc, num, cols, hdr):
    # location_code,location_desc,GPS_LAT,GPS_LONG
    txt = '---\n'
    txt += 'file_type : database\n'
    txt += 'database_name : ' + tbl_desc + '\n'
    for hdr_num, hdr_col in enumerate(hdr):
        txt += hdr_col.strip('\n') + ' : ' + cols[hdr_num].strip('\n') + '\n'
    txt += '---\n'
    txt += '### ' + tbl_desc + ' Notes for ' + cols[1] + '\n\n'

    return txt



def make_index_col(num, txt):
    op = str(num+0)  # first row is header anyway
    return op.zfill(4) + '_' + txt.replace(' ', '_')

# Main routine here - define CSV conversions
process_markdown('tbl_locations', 'Location', r'N:\duncan\LifePIM_Data\DATA\notes\_data\old_csv_lifepim\my_locations.csv')
