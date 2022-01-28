#!/usr/bin/python3
# coding: utf-8
# desktop.py 

import os 
import sys

from PyQt5.QtCore import QDate
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QDir
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

from PyQt5.QtWidgets import (QFileSystemModel)
from PyQt5.QtWidgets import (QTreeView, QListView)

from PyQt5.QtGui import QIcon

from views.home import home as home
from views.calendar import calendar as calendar
from views.tasks import tasks as tasks
from views.notes import notes as notes
from views.contacts import contacts as contacts
from views.places import places as places
from views.data import data as data
from views.badges import badges as badges
from views.money import money as money
from views.music import music as music
from views.images import images as images
from views.apps import apps as apps
from views.files import files as files
from views.admin import admin as admin
from views.options import options as options
from views.about import about as about


from interfaces import lp_screen
import config as mod_cfg


def main():
    app = QApplication(sys.argv)
    ex = LifePIM_GUI()
    sys.exit(app.exec_())


class LifePIM_GUI(QMainWindow):   # works for menu and toolbar as QMainWindow

    def __init__(self):
        super().__init__()

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
        self.lpWidgetDataview = self.create_widget_dataview()
        self.lpWidgetImageview = self.create_widget_imageview()
        

        self.load_settings_data()
        self.build_gui()

        # load modules used in the application
        self.lpFileManager = files.cFileManager()

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
        rootWidget = QWidget() 
        self.setCentralWidget(rootWidget)

        self._build_menu_and_toolbar(self.theme)
        self._build_main_layout(rootWidget)
        self.statusBar().showMessage('Ready')

        self.show()

    def _build_menu_and_toolbar(self, theme):
        ########################################################################
        #   TOOLBAR
        ########################################################################
        tbarPim = self.addToolBar('PIM')
        homeAct = self.make_toolbar_button(tbarPim, theme, 'home', 'home', 'home', 'Ctrl+1', 'Overview')
        calAct = self.make_toolbar_button(tbarPim, theme, 'cal', 'cal', 'cal', 'Ctrl+2', 'Calendar')
        addrAct = self.make_toolbar_button(tbarPim, theme, 'addr', 'addr', 'addr', 'Ctrl+3', 'Address Book')
        taskAct = self.make_toolbar_button(tbarPim, theme, 'bell', 'bell', 'bell', 'Ctrl+4', 'Todo List and Reminders')
        noteAct = self.make_toolbar_button(tbarPim, theme, 'book', 'book', 'book', 'Ctrl+5', 'Add Note')
        shelfAct = self.make_toolbar_button(tbarPim, theme, 'bookshelf', 'bookshelf', 'bookshelf', 'Ctrl+6', 'All Notes')

        drawAct = self.make_toolbar_button(tbarPim, theme, 'chalkboard', 'chalkboard', 'chalkboard', 'Ctrl+7', 'Drawings and Ideas')
        imgAct = self.make_toolbar_button(tbarPim, theme, 'camera', 'camera', 'camera', 'Ctrl+8', 'Images')

        # Search in Toolbar
        tbarSearch = self.addToolBar('Search')
        search = QLineEdit()
        tbarSearch.addWidget(search)
        searchAct = self.make_toolbar_button(tbarSearch, theme, 'Search', 'search', 'search', 'Ctrl+F', 'Search for data')

        toolbarFile = self.addToolBar('Data')
        exitAct = self.make_toolbar_button(toolbarFile, theme, 'Exit', 'exit', 'quit', 'Ctrl+Q', 'Exit application')
        cutAct = self.make_toolbar_button(toolbarFile, theme, 'Cut', 'cut', 'cut', 'Ctrl+W', 'Cut data')
        fixAct = self.make_toolbar_button(toolbarFile, theme, 'Fix', 'fix', 'fix', 'Ctrl+G', 'Fix data')
        digAct = self.make_toolbar_button(toolbarFile, theme, 'Dig', 'dig', 'dig', 'Ctrl+D', 'Dig into data')


        #=====================================================================================
        #=  MENU
        #=====================================================================================
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(digAct)
        fileMenu.addAction(exitAct)

        pimMenu = menubar.addMenu('&PIM')
        pimMenu.addAction(homeAct)
        pimMenu.addAction(calAct)
        pimMenu.addAction(addrAct)
        pimMenu.addAction(taskAct)
        pimMenu.addAction(noteAct)
        pimMenu.addAction(shelfAct)
        pimMenu.addAction(drawAct)
        pimMenu.addAction(imgAct)


        dataMenu = menubar.addMenu('&Data')
        dataMenu.addAction(digAct)
        dataMenu.addAction(cutAct)
        dataMenu.addAction(fixAct)
        dataMenu.addAction(digAct)
        dataMenu.addAction(searchAct)



    def _build_main_layout(self, rootWidget):

        # Step 1 - make the splitter interface
        rootBox = QHBoxLayout(self)
        """
        lblLeftTop = QLabel(' Left Top - FileLists')
        lblLeftMid = QLabel(' Left Mid - Folders')
        lblLeftBottom = QLabel(' Left Bottom - Files')
        lblCentre = QLabel(' Centre - NOTES')
        lblRight = QLabel(' Right - quick jump')
        """



        self.UIleftTop = QFrame(self)
        self.UIleftTop.setFrameShape(QFrame.StyledPanel)
        self.UIleftTop.resize(350,540)

        
        self.UIleftMid = QFrame(self)
        self.UIleftMid.setFrameShape(QFrame.StyledPanel)
        self.UIleftMid.resize(350,400)
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
        self.lpWidgetTextEdit.setParent(self.UImid)
        self.lpWidgetFilelist.setParent(self.UIleftBottom)
        self.lpWidgetDataview.setParent(self.UImid)
        self.lpWidgetImageview.setParent(self.UImid)

        self.update_layout()


        # -----------------------------------------------------------------------------------
        #my_cal.setParent(leftTop)     




        # finally add the main horiz splitter to the root
        rootBox.addWidget(splitter2)
        rootWidget.setLayout(rootBox)    
        


    def make_toolbar_button(self, toolbar, theme, name, icon_name, cmd_name, shortcut, tooltip):
        thisAct = QAction(QIcon(lp_screen.get_theme_icon(theme, icon_name)), name, self)
        thisAct.setShortcut(shortcut)
        thisAct.setStatusTip(tooltip)
        thisAct.triggered.connect(self.get_run_command(cmd_name))
        toolbar.addAction(thisAct)


        return thisAct


    def get_run_command(self, cmd_name, param=[]):
        """
        high level function to parse commands to correct module.
        Tempted to use pass by name, but this might cause issues
        if users mess up settings.cfg (or try to do injections 
        of sys commands), so just hard code maps from strings to
        action commands
        """
        valid_commands = {
            'quit':self.actExit,
            'dummy':self.actDummy,
            'home':self.actHome,
            'addr':self.actAddr,
            'bell':self.actBell,
            'book':self.actBook,
            'bookshelf':self.actBookshelf,
            'chalkboard':self.actChalkboard,
            'camera':self.actCamera,
            'search':self.actSearch,
            'cut':self.actCut,
            'fix':self.actFix,
            'dig':self.actDig,
            'cal':self.actCal
        }
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

    def actCal(self):  
        self.curTab = 'cal'
        self.update_layout()

    def actHome(self):  
        self.curTab = 'home'
        self.update_layout()

    def actAddr(self):  
        self.curTab = 'addr'
        self.update_layout()


    def actBell(self):  
        self.curTab = 'bell'  
        self.update_layout()

    def actBook(self):  
        self.curTab = 'book'  


        self.update_layout()

    def actBookshelf(self):  
        self.curTab = 'bookshelf'  
        self.update_layout()

    def actChalkboard(self):  
        self.curTab = 'chalkboard'  
        self.update_layout()

    def actCamera(self):  
        self.curTab = 'camera'  
        self.update_layout()

    def actSearch(self):  
        self.curTab = 'search'  
        self.update_layout()

    def actCut(self):  
        self.curTab = 'cut'
        self.update_layout()

    def actFix(self):  
        self.curTab = 'fix'
        self.update_layout()

    def actDig(self):  
        self.curTab = 'dig'  
        self.update_layout()



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
        headerItem  = QTreeWidgetItem()
        item    = QTreeWidgetItem()

        for i in range(3):
            parent = QTreeWidgetItem(tree)
            parent.setText(0, "Parent {}".format(i))
            parent.setFlags(parent.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
            for x in range(5):
                child = QTreeWidgetItem(parent)
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setText(0, "Child {}".format(x))
                child.setCheckState(0, Qt.Unchecked)
        tree.show()         
        self.glbTree = tree
        return tree

    def create_widget_text_editor(self):
        self.MainTextEditor = QTextEdit(self)
        self.MainTextEditor.resize(600,600)
        
        return self.MainTextEditor

    def create_widget_filelist(self):
        self.MainWidgetFilelist = FileWidget()
        #self.MainWidgetFilelist.resize(600,600)
        self.MainWidgetFilelist.attach_parent_reference(self)

        return self.MainWidgetFilelist

    def create_widget_dataview(self):
        self.MainWidgetDataview =  QTableView() #QTableWidget #
        return self.MainWidgetDataview

    def create_widget_imageview(self):
        self.MainWidgetImageview =  QLabel()
        self.lpPixelMap = QPixmap()
        return self.MainWidgetImageview

    def set_one_widget_visible(self, widName):
        """
        This is called when user clicks a file and only affects 
        which MID (main one) widget gets shown based on the filetype
        """
        if widName == 'text':
            self.lpWidgetTextEdit.setVisible(True)
            self.lpWidgetDataview.setVisible(False)
            self.lpWidgetImageview.setVisible(False)
        elif widName == 'data':
            self.lpWidgetTextEdit.setVisible(False)
            self.lpWidgetDataview.setVisible(True)
            self.lpWidgetImageview.setVisible(False)
        elif widName == 'image':
            self.lpWidgetTextEdit.setVisible(False)
            self.lpWidgetDataview.setVisible(False)
            self.lpWidgetImageview.setVisible(True)
        else:
            self.lpWidgetTextEdit.setVisible(True)
            self.lpWidgetDataview.setVisible(True)
            self.lpWidgetImageview.setVisible(True)



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

        elif self.curTab == 'cal':
            self.lpWidgetCalendar.setVisible(True)
            self.lpWidgetCalendar.setParent(self.UIleftTop)
            self.lpWidgetTreeview.setParent(self.UIleftMid)
            self.lpWidgetTextEdit.setVisible(False)
            self.lpWidgetFilelist.setParent(self.UIleftBottom)

        elif self.curTab == 'book':
            #self.lpWidgetCalendar.setParent(self.UIleftTop)
            #self.lpWidgetTreeview.setParent(self.UIleftMid)
            self.lpWidgetTextEdit.setParent(self.UImid)
            self.lpWidgetFilelist.setParent(self.UIleftBottom)
        else:
            self.lpWidgetTextEdit.setParent(self.UImid)



class FileWidget(QWidget):
    def __init__(self, *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        hlay = QHBoxLayout(self)
        self.treeview = QTreeView()
        self.listview = QListView()
        
        hlay.addWidget(self.treeview)
        hlay.addWidget(self.listview)

        path = QDir.rootPath()

        self.dirModel = QFileSystemModel()

        pth = mod_cfg.file_startup_path  # r"D:\dev"
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

    def attach_parent_reference(self, parentGui):
        """
        TODO - this is a terrible idea, but I havent worked out PyQT signals yet
        """
        self.MainGUI = parentGui

    def on_clicked_folder(self, index):
        path = self.dirModel.fileInfo(index).absoluteFilePath()
        self.listview.setRootIndex(self.fileModel.setRootPath(path))

    def on_clicked_file(self, index):
        self.MainGUI.currentFile = self.fileModel.filePath(index)
        print('viewing ' + self.MainGUI.currentFile)

        
        self.MainGUI.lpFileManager.show_file(self, self.MainGUI.currentFile)
 
        


if __name__ == '__main__':  
    main()        