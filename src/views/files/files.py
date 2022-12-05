# files.py

import os
import sys
import config as mod_cfg
from views.data import data as mod_data
from interfaces.web import web_data as web
from PyQt5.QtCore import *

from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QTextEdit 
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import (QFileSystemModel)
from PyQt5.QtWidgets import (QTreeView, QListView)
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QComboBox


class FileWidget(QWidget):
    def __init__(self, *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)

        pth = mod_cfg.file_startup_path  # r"D:\dev"
        
        hlay = QVBoxLayout(self)  # was HBox
        #hlay.addStretch(6)
        #hlay.showMaximized(True) 

        self.cmbDrive = QComboBox(self)
        self.cmbDrive.addItem('C:/')
        self.cmbDrive.addItem('D:/')
        self.cmbDrive.addItem('E:/')
        self.cmbDrive.addItem('M:/')
        self.cmbDrive.addItem('N:/')
        self.cmbDrive.addItem('P:/')
        self.cmbDrive.addItem('T:/')
        self.cmbDrive.addItem('U:/')



        self.cmbDrive.activated[str].connect(self.onDriveChanged)


        self.treeview = QTreeView()
        self.listview = QListView()
        self.lblCurFolder = QLineEdit(pth)
        self.lblCurFolder.setText(pth)
        hlay.addWidget(self.cmbDrive)
        hlay.addWidget(self.lblCurFolder)
        hlay.addWidget(self.treeview)
        hlay.addWidget(self.listview)

        path = QDir.rootPath()

        self.dirModel = QFileSystemModel()

        self.dirModel.setRootPath(pth)
        self.dirModel.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs)

        self.fileModel = QFileSystemModel()
        self.fileModel.setFilter(QDir.NoDotAndDotDot |  QDir.Files)

        self.treeview.setModel(self.dirModel)
        self.listview.setModel(self.fileModel)

        self.treeview.setRootIndex(self.dirModel.index(pth))  # was path but defaults to C:
        self.listview.setRootIndex(self.fileModel.index(pth)) # was path but defaults to C:

        self.treeview.clicked.connect(self.on_clicked_folder)
        self.listview.clicked.connect(self.on_clicked_file)
        self.lblCurFolder.editingFinished.connect(self.on_editingFinished)

    def _set_folder_to_list_files(self, path):
        self.dirModel.setRootPath(path)
        self.listview.setRootIndex(self.fileModel.setRootPath(path))
        self.treeview.setModel(self.dirModel)
        self.lblCurFolder.setText(path)

        self.treeview.setRootIndex(self.dirModel.index(path)) 

        self.showMaximized()
        self.listview.showMaximized()
        # error self.dirModel.showMaximized()

    def attach_parent_reference(self, parentGui):
        """
        TODO - this is a terrible idea, but I havent worked out PyQT signals yet
        """
        self.MainGUI = parentGui

    def onDriveChanged(self, index):
        #web.lg('you changed the drive to ' + str(index))
        self._set_folder_to_list_files(index)
        


    def on_clicked_folder(self, index):
        path = self.dirModel.fileInfo(index).absoluteFilePath()
        self.listview.setRootIndex(self.fileModel.setRootPath(path))
        self.lblCurFolder.setText(path)

    def on_clicked_file(self, index):
        self.MainGUI.currentFile = self.fileModel.filePath(index)
        web.lg('viewing ' + self.MainGUI.currentFile)
        self.lblCurFolder.setText( self.MainGUI.currentFile)
        self.MainGUI.lpFileManager.show_file(self, self.MainGUI.currentFile)

    def on_editingFinished(self):
        new_path = self.lblCurFolder.text()
        web.lg('left text edit - new url is ' + new_path)
        try:
            self._set_folder_to_list_files(new_path)
        except:
            web.lg_err('on_editingFinished - invalid path to set folder, new_path = ' + new_path)
 

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
            web.lg('todo - show image')
            self.display_as_image(rootGui, fname)


        elif tpe == 'video':
            web.lg('todo - play video')
            self.display_as_text(rootGui, fname)
        elif tpe == 'audio':
            self.display_as_music(rootGui, fname)
        elif tpe == '3D':
            web.lg('todo - show 3D image')
            self.display_as_text(rootGui, fname)
        elif tpe == 'strings':
            web.lg('todo - extract strings from binary file')
            self.display_as_text(rootGui, fname)
        elif tpe == 'metadata':
            web.lg('todo - show metadata - first and last 10 lines of file with num lines, etc')
            self.display_as_text(rootGui, fname)
        else:
            web.lg('todo - show file in image or media player')
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
            web.lg('display_as_text(self, rootGui, fname) TOK ')
        except:
            text = 'Cant display ' + fname
            rootGui.MainGUI.MainTextEditor.setText(text)      
            rootGui.MainGUI.set_one_widget_visible('text')  
            web.lg_err('files: display_as_text - ' + text)


    def display_as_data(self, rootGui, fname):
        #csv_viewer = mod_data.lpData(rootGui.MainGUI)
        #csv_viewer.show_file(fname)
        try:
            rootGui.MainGUI.lpWidgetDataview.show_file(fname)
            #web.lg(rootGui.MainGUI.lpWidgetDataview.get_data())
            rootGui.MainGUI.set_one_widget_visible('data')
            web.lg('display_as_data: fname = ' + fname)
        except Exception as ex:
            web.lg_err('display_as_data: fname = ' + fname + ', err = ' + str(ex))

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