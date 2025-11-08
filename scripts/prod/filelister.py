#!/usr/bin/python3
# coding: utf-8
# filelister.py

# This script is meant to be self contained and not depend on other modules
# which is why it does not use the config module. Idea is to copy to all 
# PC's on network and run to get file lists.
# NOTE - this is probably not needed seeing you can map all folders to one PC

import os
import sys
import time 
import socket
import csv
import datetime
import win32security

hostname = socket.gethostname()
print(f"The hostname is: {hostname}")

if hostname == 'treebeard':
    fldr_list = [
                #r'N:\DATA',
                #r'N:\duncan',
                'P:'
                 #'W:',
                 #'M:',
                 #'R:', 
                 #'S:'
                 ]
else:
    fldr_list = ['D:', 'C:']

#path_root =  os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + ".." + os.sep + 'src') 
#print('path root = ' + str(path_root) )
#sys.path.append(str(path_root))
# from common import config as mod_cfg

import aikif.lib.cls_filelist as mod_fl




def get_folder_list(fname):
    """
    returns the default list of folders from a config file
    """
    res = []
    print('FOLDER LIST = ' + fname)
    with open(fname, 'r') as f:
        for line in f:
            if line != '':
                if line[0:1] != '#':
                    res.append(line.strip('\n'))
    print(res)                    
    return res


#output_folder = mod_cfg.index_folder
output_folder = r"\\FANGORN\user\duncan\LifePIM_Data\index"
op_full_list = os.path.join(output_folder, 'full_filelist.csv')
# ONLY DO THIS IF CONFIG NEEDED fldr_list = get_folder_list(mod_cfg.folder_list_file)

excluded_files = [
    'myenv', 
    '__pycache__', 
    'htmlcov'
]


def collect_raw_filelists():
    lg('START', 'filelist')
    for fldr in fldr_list[0:3]:
        print('scanning folder ' + fldr)
        op_fname = get_index_filename_from_path(fldr)
        res_fl = mod_fl.FileList([fldr], ['*.*'], excluded_files, op_fname)
        res_fl.save_filelist(op_fname, ["name", "path", "size", "date"])
        lg('FOLDER', fldr + ' has ' + str(len(res_fl.get_list())) + ' files')
    lg('FINISH', 'filelist')
    

def get_index_filename_from_path(fldr):
    short_name = 'raw_' + hostname + '_' + fldr.replace('\\', '_').replace(':','_') + '.csv'
    op_fname = os.path.join(output_folder, short_name)
    return op_fname

 

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




def get_file_metadata(file_path):
    """Extract metadata for a single file on Windows."""
    try:
        stat_info = os.stat(file_path)

        # Owner lookup
        sd = win32security.GetFileSecurity(file_path, win32security.OWNER_SECURITY_INFORMATION)
        owner_sid = sd.GetSecurityDescriptorOwner()
        name, domain, _ = win32security.LookupAccountSid(None, owner_sid)
        file_owner = f"{domain}\\{name}"

        metadata = {
            "full_path_and_name": file_path,
            "path": os.path.dirname(file_path),
            "filename": os.path.basename(file_path),
            "file_size": stat_info.st_size,
            "date_modified": datetime.datetime.fromtimestamp(stat_info.st_mtime),
            "date_created": datetime.datetime.fromtimestamp(stat_info.st_ctime),
            "date_accessed": datetime.datetime.fromtimestamp(stat_info.st_atime),
            "file_owner": file_owner,
        }

        return metadata

    except Exception as e:
        # Return partial metadata if error
        return {
            "full_path_and_name": file_path,
            "path": os.path.dirname(file_path),
            "filename": os.path.basename(file_path),
            "file_size": None,
            "date_modified": None,
            "date_created": None,
            "date_accessed": None,
            "file_owner": f"Error: {e}",
        }


def process_folder(folder_name, output_csv):
    """Recursively scan a folder and save file metadata to CSV as it goes."""
    fieldnames = [
        "full_path_and_name",
        "path",
        "filename",
        "file_size",
        "date_modified",
        "date_created",
        "date_accessed",
        "file_owner",
    ]

    # Open CSV in append mode so we can save as we go
    with open(output_csv, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for root, _, files in os.walk(folder_name):
            for fname in files:
                file_path = os.path.join(root, fname)
                metadata = get_file_metadata(file_path)
                writer.writerow(metadata)
                csvfile.flush()  # ensure data is written immediately


if __name__ == '__main__':
    collect_raw_filelists()
    #print('hello from filelister')

