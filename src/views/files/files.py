# files.py

import os
import sys
import config as mod_cfg

from views.data import data as mod_data

from PyQt5.QtGui import QPixmap

class cFileManager(object):
    def __init__(self):
        #print('initialising file manager')
        self.file_types = {}
        self.load_file_types()
        #print('xtns = ' + str(self.file_types))

    def load_file_types(self):
        """
        reads settings.cfg to work out how to show different files
        """
        raw_setting = mod_cfg.read_user_setting('index_file_types')
        index_file_types = raw_setting.split(',')
        for file_type in index_file_types:
            cur_xtn_list = mod_cfg.read_user_setting('file_type_' + file_type)
            xtns = cur_xtn_list.split(',')
            #print(cur_type)
            self.file_types[file_type] = xtns
       

    def show_file(self, rootGui, fname):
        """
        high level function called when user clicks a file to have it shown in 
        its native format - for text, edit it - for images show image view, etc
        rootGui = main lifepim root window
        fname = name of file to display  (gui will make visible the approp widget)
        """
        tpe = self.identify_file_type(fname)
        # TODO - make ONE widget in 'mid' visible and others hidden 
        # rootGui.set_display_mode('text')
        #print('fname ' + fname + ' is file_type ' + tpe)
        if tpe in [ 'text', 'markdown','code','web' ]:
            self.display_as_text(rootGui, fname)
        elif tpe == 'data':
            self.display_as_data(rootGui, fname)
           

        elif tpe == 'picture':
            print('todo - show image')
            self.display_as_image(rootGui, fname)


        elif tpe == 'video':
            print('todo - play video')
            self.display_as_text(rootGui, fname)
        elif tpe == 'audio':
            self.display_as_music(rootGui, fname)
        elif tpe == '3D':
            print('todo - show 3D image')
            self.display_as_text(rootGui, fname)
        elif tpe == 'strings':
            print('todo - extract strings from binary file')
            self.display_as_text(rootGui, fname)
        elif tpe == 'metadata':
            print('todo - show metadata - first and last 10 lines of file with num lines, etc')
            self.display_as_text(rootGui, fname)
        else:
            print('todo - show file in image or media player')
            self.display_as_text(rootGui, fname)

    def identify_file_type(self, fname):
        xtn = self.get_file_extension(fname)
        for k,v in self.file_types.items():
            #print(k,v)
            if xtn in v:
                #print('fname is type ' + k)
                return k
        return 'text'

    def get_file_extension(self, fname):
        parts = fname.split('.')
        xtn = parts[-1].upper()
        #print('XTN = ' + xtn)
        return xtn

    def display_as_text(self, rootGui, fname):
        try:
            text=open(fname).read()
            rootGui.MainGUI.MainTextEditor.setText(text)      
            rootGui.MainGUI.set_one_widget_visible('text')  
            print('display_as_text(self, rootGui, fname) TOK ')
        except:
            text = 'Cant display ' + fname
            rootGui.MainGUI.MainTextEditor.setText(text)      
            rootGui.MainGUI.set_one_widget_visible('text')  


    def display_as_data(self, rootGui, fname):
        #csv_viewer = mod_data.lpData(rootGui.MainGUI)
        #csv_viewer.show_file(fname)
        rootGui.MainGUI.lpWidgetDataview.show_file(fname)
        print(rootGui.MainGUI.lpWidgetDataview.get_data())
        rootGui.MainGUI.set_one_widget_visible('data')
        print('display_as_data(self, rootGui, fname) TOK ')

    def display_as_image(self, rootGui, fname):
        #rootGui.MainGUI.lpWidgetDataview.setParent(self.UImid)
        rootGui.MainGUI.lpPixelMap = QPixmap(fname)
        rootGui.MainGUI.MainWidgetImageview.setPixmap(rootGui.MainGUI.lpPixelMap)
        # rootGui.MainGUI.lpPixelMap
        rootGui.MainGUI.MainWidgetImageview.resize(rootGui.MainGUI.lpPixelMap.width(), rootGui.MainGUI.lpPixelMap.height())
        #rootGui.MainGUI.lpWidgetDataview.setPixmap(rootGui.MainGUI.lpPixelMap)
        rootGui.MainGUI.set_one_widget_visible('image')

    def display_as_music(self, rootGui, fname):
        rootGui.MainGUI.lpMusicWidget.setVisible(True)
        rootGui.MainGUI.lpMusicWidget.play_music_file(fname)


class FileView(object):
    def __init__(self, fname):
        self.filename = fname
    
    def display_in_widget(self, gui):
        """
        
        """
        pass