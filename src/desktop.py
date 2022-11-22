#!/usr/bin/python3
# coding: utf-8
# desktop.py 

import os 
import sys

from PyQt5.QtCore import *

from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QAction 
from PyQt5.QtWidgets import QTextEdit 
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QCalendarWidget
from PyQt5.QtWidgets import (QTreeWidget, QTreeWidgetItem)
from PyQt5.QtWidgets import QMessageBox

from PyQt5.QtWidgets import QTableView
from PyQt5.QtWidgets import QTableWidget

from PyQt5.QtGui import QPixmap



from PyQt5.QtGui import QIcon

from views.home import home as home
from views.calendar import calendar as calendar
from views.tasks import tasks as tasks
from views.notes import notes as notes
from views.contacts import contacts as contacts
from views.places import places as places
from views.data import data as mod_data
from views.badges import badges as badges
from views.money import money as money
from views.music import music as mod_music
from views.images import images as images
from views.apps import apps as apps
from views.files import files as mod_files
from views.admin import admin as admin
from views.options import options as options
from views.about import about as about

 
from views import lp_screen  # make a copy of this for different interfaces (lp_web, lp_console, etc)
import config as mod_cfg
import lp_core as mod_lp_core

def main():
    app = QApplication(sys.argv)
    ex = LifePIM_GUI()
    sys.exit(app.exec_())


class LifePIM_GUI(QMainWindow):   # works for menu and toolbar as QMainWindow

    def __init__(self):
        super().__init__()

        # initial basic functions for LifePIM application
        self.lp_core = mod_lp_core.LifePIM_Core()

        # global references for Widgets created here (across all focus modes - may not be used)
        self.MainTextEditor = None
        self.MainWidgetFilelist = None
        self.MainWidgetDataview = None
        self.currentFile = ''
        self.curTab = 'home'
        # create the components that might be used in the layout
        self.lpWidgetCalendar = self.create_widget_calendar()
        self.lpWidgetTreeview = self.create_widget_treeview()
        self.lpWidgetTextEdit = self.create_widget_text_editor()
        self.lpWidgetFilelist = self.create_widget_filelist()
        self.lpWidgetImageview = self.create_widget_imageview()
        self.lpMusicWidget = self.create_wiget_musicview()
        

        self.lpWidgetDataview = mod_data.lpDataWidget(self)
        

        self.load_settings_data()
        self.build_gui()

        # load modules used in the application
        self.lpFileManager = mod_files.cFileManager()

        # populate user data for first time (from cache)
        


    def load_settings_data(self):
        """
        loads basic settings data (themes, default folders) as well
        as cached info to allow for quick display of window while
        full data set loads in background (should be seconds anyway)
        """
        self.setting_window_title = mod_cfg.read_user_setting('window_title')
        self.setting_window_location = mod_cfg.read_user_setting('window_location_main')
        self.setting_window_icon =  mod_cfg.read_user_setting('window_icon')
        self.filename_theme_default =  mod_cfg.read_user_setting('filename_theme_default')

        self.theme = lp_screen.load_theme_icons(os.path.join(mod_cfg.local_folder_theme, self.filename_theme_default))
        


    def build_gui(self):

        self.setWindowTitle(self.setting_window_title)
        self.setWindowIcon(QIcon(self.setting_window_icon))
        x, y, width, height =self.setting_window_location.split(' ')
        self.setGeometry(int(x), int(y), int(width), int(height))

        # set up the root widget and assign to main Window
        self.rootWidget = QWidget() 
        self.setCentralWidget(self.rootWidget)

        self._build_menu_and_toolbar(self.theme)
        self._build_main_layout(self.rootWidget)
        self.statusBar().showMessage('Ready')

        self.show()

    def _build_menu_and_toolbar(self, theme):
        ########################################################################
        #   TOOLBAR
        ########################################################################
        tbarPim = self.addToolBar('PIM')
        actHome = self.make_toolbar_button(tbarPim, theme, 'home', 'home', 'home', 'Ctrl+1', 'Overview')
        actCal = self.make_toolbar_button(tbarPim, theme, 'Events', 'events', 'events', 'Ctrl+2', 'Calendar')
        actTasks = self.make_toolbar_button(tbarPim, theme, 'Tasks', 'tasks', 'tasks', 'Ctrl+3', 'Tasks List')
        actNotes = self.make_toolbar_button(tbarPim, theme, 'Notes', 'notes', 'notes', 'Ctrl+4', 'Notes')
        actData = self.make_toolbar_button(tbarPim, theme, 'Data', 'data', 'data', 'Ctrl+5', 'Data Tables')
        actFiles = self.make_toolbar_button(tbarPim, theme, 'files', 'files', 'files', 'Ctrl+6', 'Files')
        actInfo = self.make_toolbar_button(tbarPim, theme, 'info', 'info', 'info', 'Ctrl+7', 'info')
        actMedia = self.make_toolbar_button(tbarPim, theme, 'media', 'media', 'media', 'Ctrl+8', 'media')
        actApps = self.make_toolbar_button(tbarPim, theme, 'apps', 'apps', 'apps', 'Ctrl+9', 'apps')
        actBadges = self.make_toolbar_button(tbarPim, theme, 'badges', 'badges', 'badges', 'Ctrl+0', 'badges')
        act3D = self.make_toolbar_button(tbarPim, theme, '3D', '3D', '3D', 'Ctrl+-', '3D')
        actComms = self.make_toolbar_button(tbarPim, theme, 'comms', 'comms', 'comms', 'Ctrl+=', 'comms')
        actAudio = self.make_toolbar_button(tbarPim, theme, 'music', 'audio', 'music', 'Ctrl+m', 'music')
        


        # make_toolbar_button(self, toolbar, theme, name, icon_name, cmd_name, shortcut, tooltip)
        # Projects (Focus) Toolbar - this is mainly user generated
        tbarProj = self.addToolBar('Project')
        projAllAct = self.make_toolbar_button(tbarProj, theme, 'All', '', 'all', '', 'Show all projects')
        
        projFilterAct = []
        for pnum, prj in enumerate(mod_cfg.proj_list):
            #projFilterAct = self.make_toolbar_button(tbarProj, theme, 'Proj1', '', 'proj_filter', '', 'Filtered projects')
            newAction = self.make_toolbar_button(tbarProj, theme, prj, '', 'proj_filter', '', prj + ' projects')
            projFilterAct.append(newAction)

        # Search in Toolbar
        tbarSearch = self.addToolBar('Search')
        search = QLineEdit()
        tbarSearch.addWidget(search)
        searchAct = self.make_toolbar_button(tbarSearch, theme, 'Search', 'search', 'search', 'Ctrl+F', 'Search for data')

        actExit = self.make_toolbar_button(tbarSearch, theme, 'Exit', 'exit', 'quit', 'Ctrl+Q', 'Exit application')

        """
        # Data Toolbar (in fact - dont put this in yet)
        toolbarFile = self.addToolBar('Data')
        exitAct = self.make_toolbar_button(toolbarFile, theme, 'Exit', 'exit', 'quit', 'Ctrl+Q', 'Exit application')
        cutAct = self.make_toolbar_button(toolbarFile, theme, 'Cut', 'cut', 'cut', 'Ctrl+W', 'Cut data')
        fixAct = self.make_toolbar_button(toolbarFile, theme, 'Fix', 'fix', 'fix', 'Ctrl+G', 'Fix data')
        digAct = self.make_toolbar_button(toolbarFile, theme, 'Dig', 'dig', 'dig', 'Ctrl+D', 'Dig into data')
        """

        #=====================================================================================
        #=  MENU
        #=====================================================================================
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(actExit)

        pimMenu = menubar.addMenu('&PIM')
        pimMenu.addAction(actHome)
        pimMenu.addAction(actCal)
        pimMenu.addAction(actTasks)
        pimMenu.addAction(actNotes)
        pimMenu.addAction(actData)
        pimMenu.addAction(actFiles)
        pimMenu.addAction(actInfo)
        pimMenu.addAction(actBadges)
        pimMenu.addAction(actMedia)
        pimMenu.addAction(act3D)
        pimMenu.addAction(actApps)
        pimMenu.addAction(actAudio)
        pimMenu.addAction(actComms)

        dataMenu = menubar.addMenu('&Data')
        dataMenu.addAction(searchAct)

        dataMenu = menubar.addMenu('&Apps')
        dataMenu.addAction(actApps)



    def _build_main_layout(self, rootWidget):

        # Step 1 - make the splitter interface
        self.rootBox = QHBoxLayout(self)
        """
        lblLeftTop = QLabel(' Left Top - FileLists')
        lblLeftMid = QLabel(' Left Mid - Folders')
        lblLeftBottom = QLabel(' Left Bottom - Files')
        lblCentre = QLabel(' Centre - NOTES')
        lblRight = QLabel(' Right - quick jump')
        """



        self.UIleftTop = QFrame(self)
        self.UIleftTop.setFrameShape(QFrame.StyledPanel)
        self.UIleftTop.resize(350,340)

        
        self.UIleftMid = QFrame(self)
        self.UIleftMid.setFrameShape(QFrame.StyledPanel)
        self.UIleftMid.resize(350,200)
        #lblLeftMid.setParent(leftMid)
          
        self.UIleftBottom = QFrame(self)
        self.UIleftBottom.setFrameShape(QFrame.StyledPanel)
        self.UIleftBottom.resize(350,501)
        #lblLeftBottom.setParent(leftBottom)

        self.UImid = QFrame(self)
        self.UImid.setFrameShape(QFrame.StyledPanel)
        self.UImid.resize(500,800)
        
        #lblCentre.setParent(mid)
        

        self.UIright = QFrame(self)
        self.UIright.setFrameShape(QFrame.StyledPanel)
        self.UIright.resize(100,700)
        #lblRight.setParent(right)
        
        splitter1 = QSplitter(Qt.Vertical)  # splitter1 = QSplitter(Qt.Horizontal)
        splitter1.resize(350,350)
        splitter1.addWidget(self.UIleftTop)
        splitter1.addWidget(self.UIleftMid)
        splitter1.addWidget(self.UIleftBottom)

    
        splitter2 = QSplitter(Qt.Horizontal)
        splitter2.addWidget(splitter1)
        splitter2.addWidget(self.UImid)
        splitter2.addWidget(self.UIright)

        # ------------------------------------------------------------------------------------
        # add components to layout depending on focus mode or toolbar

        self.lpWidgetCalendar.setParent(self.UIleftTop)
        self.lpWidgetTreeview.setParent(self.UIleftMid)
        self.lpWidgetDataview.tbl.setParent(self.UImid)   # testing
        self.lpWidgetTextEdit.setParent(self.UImid)
        self.lpWidgetFilelist.setParent(self.UIleftBottom)
        self.lpWidgetImageview.setParent(self.UImid)
        self.lpMusicWidget.setParent(self.UImid)
        # works but in very toip left under menu        self.lpMusicWidget.visWidget.setParent(self.UImid)

        self.rootBox.setSpacing(20)

        self.update_layout()


        # -----------------------------------------------------------------------------------
        #my_cal.setParent(leftTop)     




        # finally add the main horiz splitter to the root
        self.rootBox.addWidget(splitter2)
        rootWidget.setLayout(self.rootBox)    
        


    def make_toolbar_button(self, toolbar, theme, name, icon_name, cmd_name, shortcut, tooltip):
        thisAct = QAction(QIcon(lp_screen.get_theme_icon(theme, icon_name)), name, self)
        thisAct.setShortcut(shortcut)
        thisAct.setStatusTip(tooltip)
        thisAct.triggered.connect(self.get_run_command(cmd_name))
        toolbar.addAction(thisAct)


        return thisAct


    ######################################################################################################
    ######################################################################################################

    def get_run_command(self, cmd_name, param=[]):
        """
        high level function to parse commands to correct module.
        Tempted to use pass by name, but this might cause issues
        if users mess up settings.cfg (or try to do injections 
        of sys commands), so just hard code maps from strings to
        action commands
        """
        valid_commands = {
            'home':self.actHome,
            'events':self.actCal,
            'tasks':self.actTasks,
            'notes':self.actNotes,
            'data':self.actData,
            'files':self.actFiles,
            'info':self.actInfo,
            'media':self.actMedia,
            'apps':self.actApps,
            'badges':self.actBadges,
            '3D':self.act3D,
            'comms':self.actComms,
            'music':self.actAudio,
            'search':self.actSearch,
            'quit':self.actExit,
            'all':self.projAllAct,
            'proj_filter':self.projFilterAct,
            'dummy':self.actDummy


        #projAllAct = self.make_toolbar_button(tbarProj, theme, 'All', '', 'all', '', 'Show all projects')
        #projFilterAct = self.make_toolbar_button(tbarProj, theme, 'Proj1', '', 'proj_filter', '', 'Filtered projects')


        }

        self.curTab = cmd_name
        return valid_commands[cmd_name]



    def actExit(self):  
        reply = QMessageBox.question(self, 'Exit LifePIM', 'Are you sure you want to close the window?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.close()
            print('Window closed')
        else:
            pass
        self.close

    def actDummy(self):  
        self.curTab = 'dummy'
        self.update_layout()

    def actHome(self):  
        self.curTab = 'home'
        self.update_layout()

    def actCal(self):  
        self.curTab = 'cal'
        self.update_layout()

    def actTasks(self):  
        self.curTab = 'tasks'  
        self.update_layout()

    def actNotes(self):  
        self.curTab = 'notes'
        self.update_layout()

    def actData(self):  
        self.curTab = 'data'
        self.update_layout()

    def actFiles(self):  
        self.curTab = 'files'
        self.update_layout()

    def actInfo(self):  
        self.curTab = 'info'
        self.update_layout()

    def actMedia(self):  
        self.curTab = 'media'
        self.update_layout()

    def actApps(self):  
        self.curTab = 'apps'
        self.update_layout()

    def actBadges(self):  
        self.curTab = 'badges'
        self.update_layout()

    def act3D(self):  
        self.curTab = '3D'
        self.update_layout()

    def actComms(self):  
        self.curTab = 'comms'
        self.update_layout()

    def actAudio(self):  
        self.curTab = 'audio'
        self.update_layout()

    def actSearch(self):  
        self.curTab = 'search'  
        self.update_layout()

    def projAllAct(self):  
        print('TODO - change project to all')  
        self.update_layout()

    def projFilterAct(self):  
        print('TODO - FILTER project based on combo box or selection from list')    
        self.update_layout()


       #projAllAct = self.make_toolbar_button(tbarProj, theme, 'All', '', 'all', '', 'Show all projects')
        #projFilterAct = self.make_toolbar_button(tbarProj, theme, 'Proj1', '', 'proj_filter', '', 'Filtered projects')


    ######################################################################################################
    ######################################################################################################

    def create_widget_calendar(self):
        # should we add this to gridMainArea
        
        # Add a calendar widget to the top left
        vbox = QVBoxLayout(self)

        cal = QCalendarWidget(self)
        cal.setGridVisible(True)
        cal.clicked[QDate].connect(self.showDate)

        vbox.addWidget(cal)

        date = cal.selectedDate()
        #self.lbl = QLabel(self)
        #self.lbl.setText(date.toString())
        #vbox.addWidget(self.lbl)
        self.glbCal = cal
        return cal
        #return vbox
    def showDate(self, date):
        self.lbl.setText(date.toString())
        print('todo')
        

    def create_widget_treeview(self):
        tree    = QTreeWidget (self)
        #headerItem  = QTreeWidgetItem()
        #item    = QTreeWidgetItem()

        
        parent = QTreeWidgetItem(tree)
        parent.setText(0, "Inbox")
        parent.setFlags(parent.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
        parent.setCheckState(0, Qt.Checked)
        parent2 = QTreeWidgetItem(tree)
        parent2.setText(0, "Archive")
        parent2.setCheckState(0, Qt.Unchecked)
        parent3 = QTreeWidgetItem(tree)
        parent3.setText(0, "Folders")
        parent3.setFlags(parent3.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)

        child = QTreeWidgetItem(parent3)
        child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
        child.setText(0, "House")
        child.setCheckState(0, Qt.Unchecked)
        child2 = QTreeWidgetItem(parent3)
        child2.setFlags(child2.flags() | Qt.ItemIsUserCheckable)
        child2.setText(0, "Work")
        child2.setCheckState(0, Qt.Unchecked)

        """
        for i in range(3):
            parent = QTreeWidgetItem(tree)
            parent.setText(0, "Parent {}".format(i))
            parent.setFlags(parent.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
            for x in range(5):
                child = QTreeWidgetItem(parent)
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setText(0, "Child {}".format(x))
                child.setCheckState(0, Qt.Unchecked)
        """

        tree.show()         
        self.glbTree = tree

        #print('TREEVIEW CREATED')

        return tree

    def create_widget_text_editor(self):
        self.MainTextEditor = QTextEdit(self)
        self.MainTextEditor.resize(600,600)
        
        
        return self.MainTextEditor

    def create_widget_filelist(self):
        self.MainWidgetFilelist = mod_files.FileWidget()
        #self.MainWidgetFilelist.resize(600,600)
        self.MainWidgetFilelist.attach_parent_reference(self)

        return self.MainWidgetFilelist

    """
    def create_widget_dataview(self):
        
        self.MainWidgetDataview =  QTableView() #QTableWidget #
        self.MainWidgetDataview.resize(900,900)
        return self.MainWidgetDataview
    """

    def create_widget_imageview(self):
        self.MainWidgetImageview =  QLabel()
        self.lpPixelMap = QPixmap()
        return self.MainWidgetImageview

    def create_wiget_musicview(self):
        self.lpMusicWidget =  mod_music.lpMusicWidget(self)
        self.lpMusicWidget.setParent(self)
        
        return self.lpMusicWidget


    def set_one_widget_visible(self, widName):
        """
        This is called when user clicks a file and only affects 
        which MID (main one) widget gets shown based on the filetype
        """
        if widName == 'text':
            self.lpWidgetTextEdit.setVisible(True)
            self.lpWidgetDataview.tbl.setVisible(False)
            self.lpWidgetImageview.setVisible(False)
            #self.lpMusicWidget.visWidget.setVisible(False)
        elif widName == 'data':
            self.lpWidgetTextEdit.setVisible(False)
            self.lpWidgetDataview.tbl.setVisible(True)
            self.lpWidgetImageview.setVisible(False)
            #self.lpMusicWidget.visWidget.setVisible(False)
        elif widName == 'image':
            self.lpWidgetTextEdit.setVisible(False)
            self.lpWidgetDataview.tbl.setVisible(False)
            self.lpWidgetImageview.setVisible(True)
            #self.lpMusicWidget.visWidget.setVisible(False)
        elif widName in ['sound', 'music']:
            self.lpWidgetTextEdit.setVisible(False)
            self.lpWidgetDataview.tbl.setVisible(False)
            self.lpWidgetImageview.setVisible(False)

            self.lpMusicWidget.visWidget.setVisible(True)
            print('activating music widget')
        else:
            self.lpWidgetTextEdit.setVisible(True)
            self.lpWidgetDataview.tbl.setVisible(True)
            self.lpWidgetImageview.setVisible(True)
            #self.lpMusicWidget.visWidget.setVisible(True)



    def update_layout(self):
        """
        High level function called when use switches mode eg
        from Calendar to Notes, Tasks, Apps etc.
        This changes the screen layout and sets the ALREADY CREATED 
        widgets in the window location that is specified.
        """
        print('TAB MODE - is now ' + self.curTab)
        
        if self.curTab == 'home':
            self.lpWidgetCalendar.setVisible(False)
            self.lpWidgetTreeview.setParent(self.UIleftMid)
            self.lpWidgetTextEdit.setParent(self.UImid)
            self.lpWidgetFilelist.setParent(self.UIleftBottom)
            self.lpWidgetTextEdit.setVisible(True)
            self.lpWidgetDataview.setVisible(True)
            self.lpMusicWidget.setVisible(True)
            #self.lpWidgetDataview.setParent(self.UImid)  # TODO - fix

        elif self.curTab == 'cal':
            self.lpWidgetCalendar.setVisible(True)
            self.lpWidgetCalendar.setParent(self.UIleftTop)
            self.lpWidgetTreeview.setParent(self.UIleftMid)
            self.lpWidgetTextEdit.setVisible(False)
            self.lpWidgetFilelist.setParent(self.UIleftBottom)
            self.lpMusicWidget.setVisible(False)

        elif self.curTab == 'notes':
            notes.build_screen(self.lpWidgetTextEdit)
            #self.lpWidgetCalendar.setParent(self.UIleftTop)
            #self.lpWidgetTreeview.setParent(self.UIleftMid)
            self.lpWidgetTextEdit.setParent(self.UImid)
            self.lpWidgetFilelist.setParent(self.UIleftBottom)
            self.lpMusicWidget.setVisible(False)
            self.lpWidgetTextEdit.setVisible(True)
            self.lpWidgetTextEdit.adjustSize()

        elif self.curTab == 'audio':
            #self.lpWidgetCalendar.setParent(self.UIleftTop)
            #self.lpWidgetTreeview.setParent(self.UIleftMid)
            self.lpWidgetTextEdit.setParent(self.UImid)
            self.lpWidgetFilelist.setParent(self.UIleftBottom)
            self.lpMusicWidget.setVisible(True)
            self.lpWidgetTextEdit.setVisible(False)

            #self.lpMusicWidget.visWidget.setVisible(True)
            print('activating music widget')            
        else:
            self.lpWidgetTextEdit.setParent(self.UImid)



if __name__ == '__main__':  
    main()        