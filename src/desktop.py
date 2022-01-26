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

from PyQt5.QtWidgets import (QFileSystemModel)
from PyQt5.QtWidgets import (QTreeView, QListView)

from PyQt5.QtGui import QIcon


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
        self.currentFile = ''
        self.curTab = 'home'
        # create the components that might be used in the layout
        self.lpWidgetCalendar = self.create_widget_calendar()
        self.lpWidgetTreeview = self.create_widget_treeview()
        self.lpWidgetTextEdit = self.create_widget_text_editor()
        self.lpWidgetFilelist = self.create_widget_filelist()

        self.load_settings_data()
        self.build_gui()


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

        self.update_layout(self.curTab)


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
        print('running dummy command ' )  
        self.curTab = 'dummy'
        self.update_layout(self.curTab)

    def actCal(self):  
        print('running calendar command ' )  
        self.curTab = 'cal'
        self.update_layout(self.curTab)

    def actHome(self):  
        print('running home command ' )  
        self.curTab = 'home'
        self.update_layout(self.curTab)

    def actAddr(self):  
        print('running Addr command ' )  
        self.update_layout(self.curTab)

    def actAddr(self):  
        print('running Addr command ' )  
        self.update_layout(self.curTab)

    def actAddr(self):  
        print('running Addr command ' )  
        self.update_layout(self.curTab)

    def actBell(self):  
        print('running Bell command ' )  
        self.update_layout(self.curTab)

    def actBook(self):  
        print('running Book command ' )  
        self.update_layout(self.curTab)
        self.update_layout(self.curTab)

    def actBookshelf(self):  
        print('running Bookshelf command ' )  
        self.update_layout(self.curTab)

    def actChalkboard(self):  
        print('running Chalkboard command ' )  
        self.update_layout(self.curTab)

    def actCamera(self):  
        print('running Image command ' )  
        self.update_layout(self.curTab)

    def actSearch(self):  
        print('running Search command ' )  
        self.update_layout(self.curTab)

    def actCut(self):  
        print('running Data Cut command ' )  
        self.update_layout(self.curTab)

    def actFix(self):  
        print('running Data Fix command ' )  
        self.update_layout(self.curTab)

    def actDig(self):  
        print('running Data Dig command ' )  
        self.statusBar().showMessage(str(glbMainTextEditor))
        self.update_layout(self.curTab)



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


    def update_layout(self, tabName):
        """
        High level function called when use switches mode eg
        from Calendar to Notes, Tasks, Apps etc.
        This changes the screen layout and sets the ALREADY CREATED 
        widgets in the window location that is specified.
        """
        print('TAB MODE - is now ' + tabName)
        if tabName == 'home':
            self.lpWidgetCalendar.setParent(None)
            self.lpWidgetTreeview.setParent(self.UIleftMid)
            self.lpWidgetTextEdit.setParent(self.UImid)
            self.lpWidgetFilelist.setParent(self.UIleftBottom)

        elif tabName == 'cal':
            self.lpWidgetCalendar.setParent(self.UIleftTop)
            self.lpWidgetTreeview.setParent(self.UIleftMid)
            self.lpWidgetTextEdit.setParent(None)
            self.lpWidgetFilelist.setParent(self.UIleftBottom)

        elif tabName == 'book':
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
        print('view ing ' + self.MainGUI.currentFile)
        text=open(self.MainGUI.currentFile).read()
        self.MainGUI.MainTextEditor.setText(text)
        
        



if __name__ == '__main__':  
    main()        