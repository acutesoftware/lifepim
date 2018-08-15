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


print('collecting metadata')


aikif_fl = fl.FileList([music_folder], ['*.mp3'], [],  'music_list.csv')
aikif_fl.save_filelist('music_list.csv', ["name", "path", "size", "date"])

print('done')
#dct_result = get_audio_metadata(fname):
