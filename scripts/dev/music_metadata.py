#!/usr/bin/python3
# coding: utf-8
# music_metadata.py



import os
import sys
import csv
import mutagen
import mutagen.id3

path_root =  os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + ".." ) 
print('path root = ' + str(path_root) )
sys.path.append(str(path_root))

import config as mod_cfg

def collect_all():
    src_file = os.path.join(mod_cfg.filelist_merged_files, 'ALL_files_mp3.csv')
    MP3_file = os.path.join(mod_cfg.filelist_merged_files, 'ALL_files_mp3_metadata.csv')
    
    print('collecting music metadata from ' + src_file)
    # for now - just do one file
    process_filelist_file(src_file, MP3_file)

    print('done')

def process_filelist_file(fname, MP3_file):
    print('reading ' + fname)

    with open(fname, 'r') as fip:
        reader = csv.reader(fip)

        with open(MP3_file, 'w') as fop:
            for line in reader:
                try:
                    if '.mp3' in line[0]:
                        fullname = line[0] 
                        shortname = line[1]
                        pth = line[2]
                        sze = line[3]
                        dte = line[4]
                        audio = get_audio_metadata(fullname)
                        #print('audio = ' + str(audio))
                        new_row = make_music_row(fullname, shortname, pth, sze, dte, audio)
                        fop.write(new_row)
                        #print(str(new_row))
                except Exception as ex:
                    print('cant process file ' + str(ex))
                
def make_music_row(fullname, shortname, pth, sze, dte, audio_dict):
    """
    makes a single CSV record for MP3 dataset which combines
    file infor from filelist (line) and the audio information
    from (audio)
    """
    
    op = '"' + fullname + '",'
    op += '"' + shortname + '",'
    op += '"' + pth + '",'
    op += '"' + sze + '",'
    op += '"' + dte + '",'
    op += '"' + audio_dict['album'] + '",'
    op += '"' + audio_dict['title']  + '",'
    op += '"' + audio_dict['artist'] + '",'
    op += '"' + audio_dict['length']  + '",'
    op += '"' + audio_dict['tracknumber']  + '",'
    op += '"' + audio_dict['genre']  + '"\n'

    return op    



def get_audio_metadata(fname):
    """ collects basic MP3 metadata
    Works, once you use mutagenx (buried deep in issues page)
    ['Angels']
    ['Red Back Fever']
    ['Red Back Fever']
    {'album': ['Red Back Fever'], 'title': ['Red Back Fever'], 'artist': ['Angels']}    
    """


    from mutagen.easyid3 import EasyID3
    audio = EasyID3(fname)
    #print('ALL DATA = ' + str(audio))
    audio_dict = {}
    
    try:
        artist = audio["artist"][0]
    except KeyError:
        artist = ''
        
    try:    
        title = audio["title"][0]
    except KeyError:
        title = ''
        
    try:
        album = audio["album"][0]
    except KeyError:
        album = ''
        
    try:
        length = audio["length"][0]
    except KeyError:
        length = ''
        
    try:
        tracknumber = audio["tracknumber"][0]
    except KeyError:
        tracknumber = ''
        
    try:
        genre = audio["genre"][0]
    except KeyError:
        genre = ''
        
    
    audio_dict['album'] = album
    audio_dict['title'] = title
    audio_dict['artist'] = artist
    audio_dict['length'] = length
    audio_dict['tracknumber'] = tracknumber
    audio_dict['genre'] = genre
    
    return audio_dict




if __name__ == '__main__':
    collect_all()