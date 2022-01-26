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

        # global references across all focus modes
        self.MainTextEditor = None
        self.MainWidgetFilelist = None
        self.currentFile = ''

        self.build_gui()




    def build_gui(self):

        self.setWindowTitle(mod_cfg.read_user_setting('window_title'))
        self.setWindowIcon(QIcon('static/favicon.ico'))

        # Load themes and data needed
        theme = lp_screen.load_theme_icons(os.path.join(mod_cfg.local_folder_theme, 'theme_djm.txt'))

        window_location = mod_cfg.read_user_setting('window_location_main')
        x, y, width, height = window_location.split(' ')
        self.setGeometry(int(x), int(y), int(width), int(height))
    

        # set up the root widget and assign to main Window
        rootWidget = QWidget() 
        self.setCentralWidget(rootWidget)

        self._build_menu_and_toolbar(theme)
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

        lblLeftTop = QLabel(' Left Top - FileLists')
        lblLeftMid = QLabel(' Left Mid - Folders')
        lblLeftBottom = QLabel(' Left Bottom - Files')
        lblCentre = QLabel(' Centre - NOTES')
        lblRight = QLabel(' Right - quick jump')
        

        leftTop = QFrame(self)
        leftTop.setFrameShape(QFrame.StyledPanel)
        leftTop.resize(350,540)
        lblLeftTop.setParent(leftTop)
        
        leftMid = QFrame(self)
        leftMid.setFrameShape(QFrame.StyledPanel)
        leftMid.resize(350,400)
        lblLeftMid.setParent(leftMid)
          
        leftBottom = QFrame(self)
        leftBottom.setFrameShape(QFrame.StyledPanel)
        leftBottom.resize(350,501)
        lblLeftBottom.setParent(leftBottom)

        mid = QFrame(self)
        mid.setFrameShape(QFrame.StyledPanel)
        mid.resize(500,800)
        lblCentre.setParent(mid)
        

        right = QFrame(self)
        right.setFrameShape(QFrame.StyledPanel)
        right.resize(100,700)
        lblRight.setParent(right)
        
        splitter1 = QSplitter(Qt.Vertical)  # splitter1 = QSplitter(Qt.Horizontal)
        splitter1.resize(350,350)
        splitter1.addWidget(leftTop)
        splitter1.addWidget(leftMid)
        splitter1.addWidget(leftBottom)

    
        splitter2 = QSplitter(Qt.Horizontal)
        splitter2.addWidget(splitter1)
        splitter2.addWidget(mid)
        splitter2.addWidget(right)

        # ------------------------------------------------------------------------------------
        # add the components to the layout
        self.create_widget_calendar().setParent(leftTop)
        self.create_widget_treeview().setParent(leftMid)
        self.create_widget_text_editor().setParent(mid)
        self.create_widget_filelist().setParent(leftBottom)

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
        print('running dummy command ' )  
    def actCal(self):  
        print('running calendar command ' )  
    def actHome(self):  
        print('running home command ' )  
    def actAddr(self):  
        print('running Addr command ' )  

    def actAddr(self):  
        print('running Addr command ' )  

    def actAddr(self):  
        print('running Addr command ' )  

    def actBell(self):  
        print('running Bell command ' )  

    def actBook(self):  
        print('running Book command ' )  

    def actBookshelf(self):  
        print('running Bookshelf command ' )  

    def actChalkboard(self):  
        print('running Chalkboard command ' )  

    def actCamera(self):  
        print('running Image command ' )  

    def actSearch(self):  
        print('running Search command ' )  

    def actCut(self):  
        print('running Data Cut command ' )  

    def actFix(self):  
        print('running Data Fix command ' )  

    def actDig(self):  
        print('running Data Dig command ' )  
        self.statusBar().showMessage(str(glbMainTextEditor))



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