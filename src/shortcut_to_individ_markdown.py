#!/usr/bin/python3
# coding: utf-8
# shortcut_to_individ_markdown.py
# takes a folder of shortcuts and generates individual markdown files for each row
# used for free form datasets in PIMs like Obsidian or general notes.

import os 
import sys
from datetime import datetime
import glob
import re
import config as mod_cfg

ip_fldr = r'C:\Users\duncan\Desktop\Game Dev Shortcuts'
op_fldr = r'N:\duncan\LifePIM_Data\DATA\notes\00-META\05-Apps\53-Links\53-1-Win'


def main():

    fl = glob.glob(ip_fldr + os.sep + '*.*')
    for fname in fl:
        name = fname.replace(ip_fldr, '')[1:][:-4]
        link = extract_shortcut_path(fname)
        if link:
            #print('Processing "' + name + '" = ' + link )
                    
            res = make_markdown(name, link)
            markdown_fname = os.path.join(op_fldr, name + '.md')
            with open(markdown_fname, 'w') as fop:
                fop.write(res)
            print('saved ' + markdown_fname)

def extract_shortcut_path(fname):
    res = ''
    pth = ''
    raw = try_extract_link_from_drive(fname, 'D')
    #print(raw)
    if raw == []:
        raw = try_extract_link_from_drive(fname, 'C')
        print(raw)
        if raw == []:
            raw = try_extract_link_from_drive(fname, 'E')
            
            if raw == []:
                raw = try_extract_link_from_drive(fname, 'N')
                print(raw)
    if not raw:
        return ''
    try:
        if len(raw) > 1:
            pth = str(raw[1]).replace( "\x00", "", -1) #.lower()
        else:
            pth = raw.replace( "\x00", "", -1)

        if '.exe' in pth:
            res = pth
        if '.bat' in pth:
            res = pth
        

    except Exception as ex:
        print('cant extract fname - ' + str(ex))
        print('RAW = ' + str(raw))

    return res

def try_extract_link_from_drive(fname, drive_letter):
    with open(fname, 'r', encoding = "ISO-8859-1") as fip:
        return re.findall(drive_letter + ":.*?exe", fip.read(), flags=re.DOTALL)


def make_markdown(name, link_to_run):
    
    # get the folder from the full link to run
    file_parts = link_to_run.split(os.sep)
    folder = os.sep.join( p for p in file_parts[0:len(file_parts) - 1])

    # get extra details for metadata here from the file shortcut
    ###############################################################
    num_files = ''
    num_folders = ''
    size_app = ''
    size_folder = ''
    #last_date = datetime.strptime('Jan-01-1975', '%m/%d/%y')
    #date_folder = datetime.strptime('Jan-01-1975', '%m/%d/%y')
    date_app = os.path.getmtime(link_to_run)  # fixed
    date_folder = os.path.getmtime(link_to_run)  # gets LATEST date of any file there


    if folder:
        print('checking ... ' + folder)
        if os.path.isdir(folder):
            size_folder, num_files, num_folders,  date_folder = get_folder_stats(folder)



    #  output the results
    ###############################################################
    txt = '---\n'
    txt += 'file_type : exe\n'
    txt += 'name : ' + name + '\n'
    txt += 'link_to_run : ' + link_to_run + '\n'
    txt += 'folder : ' + folder + '\n'
    txt += 'size_app : ' + size_app + '\n'
    txt += 'size_folder : ' + str(int(size_folder/1000000)) + 'Mb\n'
    txt += 'date_app : ' +  datetime.fromtimestamp(date_app).strftime('%Y-%m-%d') + '\n'
    txt += 'date_folder : ' + datetime.fromtimestamp(date_folder).strftime('%Y-%m-%d %H:%M:%S') + '\n'
    txt += 'num_files : ' + str(num_files) + '\n'
    txt += 'num_folders : ' + str(num_folders) + '\n'
    
    txt += '---\n'
    txt += '### ' + name + ' Notes\n\n'
    txt += 'This application is used for ...'
    return txt

def get_folder_stats(start_path):
    size_folder = 0
    num_files = 0
    num_folders = 0
    last_date = os.path.getmtime(start_path)
    


    uniq_folders = []
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if dirpath not in uniq_folders:
                uniq_folders.append(dirpath)

            # skip if it is symbolic link
            if not os.path.islink(fp):


                size_folder += os.path.getsize(fp)
                num_files += 1
                if last_date < os.path.getmtime(fp):
                    last_date = os.path.getmtime(fp)

    num_folders = len(uniq_folders)
    return size_folder, num_files, num_folders, last_date

main()
