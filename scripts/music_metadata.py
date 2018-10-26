#!/usr/bin/python3
# coding: utf-8
# music_metadata.py



import os
import sys

import aikif.toolbox.audio_tools as audio_tools
import aikif.lib.cls_filelist as fl

print('If you get a Error cant import mutagen, you need to run')
print(' >  sudo pip3 install mutagenx')

####################################################3333
#  Set your music folder here

music_folder = '~/Music/Linux Action News/'
music_folder = '~/Music'
music_folder = '/home/duncan/Music/Linux Action News'
music_folder = '/home/duncan/Music'
#root_folder =  os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + "..")
root_folder =  os.path.abspath(os.path.dirname(music_folder))


print('collecting metadata')


aikif_fl = fl.FileList([root_folder], ['*.mp3'], [],  'music_list2.csv')
aikif_fl.save_filelist('music_list2.csv', ["name", "path", "size", "date"])

print('done')
#dct_result = get_audio_metadata(fname):
