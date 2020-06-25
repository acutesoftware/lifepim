#!/usr/bin/python3
# coding: utf-8
# filelister.py

import os
import time 
import config as mod_cfg
import web_data as web

output_folder = mod_cfg.user_folder
op_full_list = os.path.join(output_folder, 'full_filelist.csv')
fldr_list = web.get_folder_list(mod_cfg.folder_list_file)


def collect_all():
    """
    runs filelist for all folders and updates 
    metadata.
    """
    collect_raw_filelists()
    collect_metadata()

def collect_metadata():
    # we have a single list of folders, so scan them and get counts
    print('todo')
 

def collect_raw_filelists():    
    all_files = []
    lg('START', 'filelist')
    for fldr in fldr_list:
        print('scanning folder ' + fldr)
        files, folders = web.get_file_list([fldr], ['*.*'], shortNameOnly='N')
        print('found ' + str(len(files)) + ' files')
        lg('FOLDER', fldr + ' has ' + str(len(files)) + ' files in ' + str(len(folders)) + ' folders')
        op_fname = os.path.join(output_folder, 'index', 'raw_filelist_' + fldr.replace('\\', '_').replace(':','_') + '.csv')
        save_list(files, op_fname, fldr)
 
        op_folder_name = os.path.join(output_folder, 'index', 'raw_folderlist_' + fldr.replace('\\', '_').replace(':','_') + '.csv')
        save_list(folders, op_folder_name, fldr)
    lg('FINISH', 'filelist')

def save_list(lst, fname, fldr):

    with open(fname,'w', encoding='utf-8', errors='replace') as fout:
        fout.write('# ' + fldr + '\n')
        for line in lst:
            # we remove the first path so it is not repeated

            fout.write(line[len(fldr):])
            fout.write('\n')

def lg(tpe, txt):
    with open(os.path.join(output_folder, 'filelist.log'), 'a') as f:
        f.write(dte() + ',' + tpe + ',' + txt + '\n')

def dte():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

if __name__ == '__main__':
    collect_all()

