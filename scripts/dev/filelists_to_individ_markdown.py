#!/usr/bin/python3
# coding: utf-8
# filelists_to_individ_markdown.py
# creates calendar CSV events based on lists of files
# for fast calendar view of photos / files created

import os 
import sys
import time
import scripts.prod.events as events
import index as index 
import config as mod_cfg

op_fldr = mod_cfg.filelist_op_fldr

excluded_folders = mod_cfg.filelist_excluded_folders

def main():
    print(dte() + ' Generating events from filelist')

    index_list = index.get_list_and_names_index_files()
    print('INDEX = ' + str(index_list))
    print('Total = ' + str(len(index_list)))
    
    for row in index_list:
        create_events_for_index_file(row[0], row[1]) #fname, display_name
        print('generating events from FileList - ' + str(row[0]))
    
    print(dte() + ' Finished')


def create_events_for_index_file(fname, display_name):
    print(dte() + ' creating events from filelist ' + display_name)
    lst = index.read_csv_to_list(fname)

    print('Total Rows = ' + str(len(lst)))
    for line in lst:
        if line:
            try:
                exclude = 'N'
                for excl in excluded_folders:
                    if excl in line[2]:
                        exclude = 'Y'
                if exclude != 'Y':
                    try:
                        op_file = os.path.join(op_fldr, 'files_' + line[4][0:7] + '.csv')
                        #print('saving : ' + str(line) + ' \n  to csv file: ' + op_file)
                        append_event_to_file(line, op_file)
                    except Exception as ex:
                        print("Problem saving " + str(line) + str(ex))
            except Exception as ex:
                print('cant save file ' + op_file + '\n' + str(ex))
                print('line = ' + str(line))

def append_event_to_file(line, op_file):
    """
    save the list data from columns to output format 
    and append to the file
    fullFilename,name,path,size,date,
    """
    txt = '"' + line[0] + '",'
    txt += '"' + line[1] + '",'
    txt += '"' + line[2] + '",'
    txt += '"' + line[3] + '",'
    txt += '"' + line[4] + '"\n'
    
    with open(op_file, 'a') as fop:
        fop.write(txt)


def dte():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())




if __name__ == '__main__':
    main()    
