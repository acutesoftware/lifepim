#!/usr/bin/python3
# coding: utf-8
# shortcut_to_individ_markdown.py
# takes a folder of shortcuts and generates individual markdown files for each row
# used for free form datasets in PIMs like Obsidian or general notes.

import os 
import sys
import time
import glob
import re
import config as mod_cfg

ip_fldr = r'C:\Users\duncan\Desktop\Game Dev Shortcuts'
op_fldr = r'N:\duncan\LifePIM_Data\DATA\notes\00-META\05-Apps\53-Links'


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
    with open(fname, 'r', encoding = "ISO-8859-1") as fip:
        file_content = fip.read()
        #print(file_content)
        raw = re.findall("D:.*?exe", file_content, flags=re.DOTALL)
        if raw == []:
            raw = re.findall("C:.*?exe", file_content, flags=re.DOTALL)
        if not raw:
            raw = re.findall("E:.*?exe", file_content, flags=re.DOTALL)
        if not raw:
            raw = re.findall("N:.*?exe", file_content, flags=re.DOTALL)
        if not raw:
            return ''
        try:
            if len(raw) > 1:
                pth = str(raw[1]) #.lower()
            else:
                pth = raw

            if '.exe' in pth:
                res = pth
            if '.bat' in pth:
                res = pth

        except Exception as ex:
            print('cant extract fname - ' + str(ex))
            print('RAW = ' + str(raw))
    
    return res


def make_markdown(name, link_to_run):
    
    file_parts = link_to_run.split(os.sep)
    folder = os.sep.join( p for p in file_parts[0:len(file_parts) - 1])



    txt = '---\n'
    txt += 'file_type : exe\n'
    txt += 'name : ' + name + '\n'
    txt += 'folder : ' + folder + '\n'
    txt += 'link_to_run : ' + link_to_run + '\n'
    txt += '---\n'
    txt += '### ' + name + ' Notes\n\n'
    txt += 'This application is used for ...'
    return txt


main()
