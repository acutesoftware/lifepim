#!/usr/bin/python3
# coding: utf-8
# folder_to_individ_markdown.py
# takes a folder and generates individual markdown files for each row
# used for free form datasets in PIMs like Obsidian or general notes.

import os 
import sys
from datetime import datetime
import glob
import re
import config as mod_cfg


op_fldr = r'N:\duncan\LifePIM_Data\DATA\notes\00-META\06-Config\62-Folders_via_config'


def read_folder_list():
    """ TYPE, NAME, PATH
        Folders,Dev Local,D:\dev\src
        Config,Index Folder,D:\lifepim_cache\index
        Folders,Docs Local,D:\docs    
    """    
    folder_list = []
    with open(os.path.join(op_fldr, 'folders_djm.csv'), 'r') as fip:
        for line in fip:
            if line:
                if line[0:1] != '#':
                    if 'BACKUP,' not in line:
                        folder_list.append(line.replace('\n','').split(','))
    return folder_list


def main():
    folder_list = read_folder_list()
    print('folder_list= ' + str(folder_list))
    for folder in folder_list[0:999]:
        if folder[1] != '':
            area = folder[0]
            name = folder[1]
            link = folder[2]
            id = link.replace(':', '').replace('\\', '_')
            
            print('Processing "' + id + ' (' + name + ') " = ' + link )
            
            try:
                res = make_markdown(id, area, name, link)
                markdown_fname = os.path.join(op_fldr, id + '.md')
                print('saving to ' + markdown_fname)
                with open(markdown_fname, 'w') as fop:
                    fop.write(res)
                print('saved ' + markdown_fname)
            except Exception as ex:
                print("Cant process folder - " + str(folder) + '\nERROR = ' + str(ex))

def make_markdown(id, area, name, pth):

    # get extra details for metadata here from the file shortcut
    ###############################################################
    num_files = ''
    num_folders = ''
    size_folder = ''
    date_folder = os.path.getmtime(pth)  # gets LATEST date of any file there


    if pth:
        print('checking ... ' + pth)
        if os.path.isdir(pth):
            size_folder, num_files, num_folders,  date_folder = get_folder_stats(pth)

    display_size = ''
    if size_folder > 1000000000:
        display_size = "{:.1f}".format(size_folder/1000000000) + ' Gb\n'
    elif size_folder > 1000000:
        display_size = "{:.1f}".format(size_folder/1000000) + ' Mb\n'
    elif size_folder > 1000:
        display_size = "{:.1f}".format(size_folder/1000) + ' kb\n'
    else:
        display_size = str(size_folder) + ' byte\n'
        

    #  output the results
    ###############################################################
    txt = '---\n'
    txt += 'file_type : folder\n'
    txt += 'id : ' + id + '\n'
    txt += 'name : ' + name + '\n'
    txt += 'area : ' + area + '\n'
    txt += 'folder : ' + pth + '\n'
    txt += 'display_size : ' + display_size
    txt += 'size_folder : ' + str(int(size_folder)) + '\n'
    txt += 'date_folder : ' + datetime.fromtimestamp(date_folder).strftime('%Y-%m-%d %H:%M:%S') + '\n'
    txt += 'num_files : ' + str(num_files) + '\n'
    txt += 'num_folders : ' + str(num_folders) + '\n'
    
    txt += '---\n'
    txt += '### ' + name + ' Notes\n\n'
    txt += 'This Folder is used for ...'
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


if __name__ == '__main__':
    main()
#save_folder_code_to_csv()
