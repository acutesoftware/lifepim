#!/usr/bin/python3
# coding: utf-8
# desktop.py 

import os 
import sys

from PyQt5.QtCore import QDate
from PyQt5.QtCore import Qt
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
        self.build_gui()


    def build_gui(self):
        self.setGeometry(100, 100, 900, 600)
        self.setWindowTitle('LifePIM Desktop')
        self.setWindowIcon(QIcon('static/favicon.ico'))


        # WORKS        textEdit = QTextEdit()
        # self.setCentralWidget(textEdit)
        #rootWidget = QHBoxLayout(self) # doesnt work QWidget()   # 
        rootWidget = QWidget() 
        self.setCentralWidget(rootWidget)




        self.build_main_layout(rootWidget)

        theme = lp_screen.load_theme_icons(os.path.join(mod_cfg.local_folder_theme, 'theme_djm.txt'))
    
    


        ########################################################################
        #   TOOLBAR
        ########################################################################
        tbarPim = self.addToolBar('PIM')
        calAct = self.make_toolbar_button(tbarPim, theme, 'cal', 'cal', 'cal', 'Ctrl+1', 'Calendar')
        addrAct = self.make_toolbar_button(tbarPim, theme, 'addr', 'addr', 'addr', 'Ctrl+2', 'Address Book')
        taskAct = self.make_toolbar_button(tbarPim, theme, 'bell', 'bell', 'bell', 'Ctrl+3', 'Todo List and Reminders')
        noteAct = self.make_toolbar_button(tbarPim, theme, 'book', 'book', 'book', 'Ctrl+4', 'Add Note')
        shelfAct = self.make_toolbar_button(tbarPim, theme, 'bookshelf', 'bookshelf', 'bookshelf', 'Ctrl+4', 'All Notes')

        drawAct = self.make_toolbar_button(tbarPim, theme, 'chalkboard', 'chalkboard', 'chalkboard', 'Ctrl+5', 'Drawings and Ideas')
        imgAct = self.make_toolbar_button(tbarPim, theme, 'camera', 'camera', 'camera', 'Ctrl+7', 'Images')

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



        # ------------------------------------------------------------------------------------
        #   [ S T A T U S    B A R ]
        # ------------------------------------------------------------------------------------
        self.statusBar().showMessage('Ready')

        

        #[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]
        #   G R I D    L A Y O U T 
        #[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]

        gridMainArea = QHBoxLayout()  #QFrame(self)
        """

        # should we add this to gridMainArea
        
        # Add a calendar widget to the top left
        vbox = QVBoxLayout(self)

        cal = QCalendarWidget(self)
        cal.setGridVisible(True)
        cal.clicked[QDate].connect(self.showDate)

        vbox.addWidget(cal)

        self.lbl = QLabel(self)
        date = cal.selectedDate()
        self.lbl.setText(date.toString())

        vbox.addWidget(self.lbl)

        self.setLayout(vbox)
        #gridMainArea.setLayout(vbox)
        """


        self.show()



    def build_main_layout(self, rootWidget):

        # Step 1 - make the splitter interface
        rootBox = QHBoxLayout(self)

        #leftBox = QVBoxLayout(self)
        #leftBox.addWidget(QLabel('Left Main'))

        leftTop = QFrame(self)
        leftTop.setFrameShape(QFrame.StyledPanel)
        leftTop.resize(300,300)
        
        leftMid = QFrame(self)
        leftMid.setFrameShape(QFrame.StyledPanel)
        leftMid.resize(300,400)
        
        leftBottom = QFrame(self)
        leftBottom.setFrameShape(QFrame.StyledPanel)
        leftBottom.resize(300,501)
        

        mid = QFrame(self)
        mid.setFrameShape(QFrame.StyledPanel)
        mid.resize(500,800)

        right = QFrame(self)
        right.setFrameShape(QFrame.StyledPanel)
        right.resize(100,700)

        
        textEdit = QTextEdit()
        #rootBox.addWidget(textEdit)        # doesnt work adding to rootBox

        splitter1 = QSplitter(Qt.Vertical)  # splitter1 = QSplitter(Qt.Horizontal)
        splitter1.resize(300,300)
        splitter1.addWidget(leftTop)
        splitter1.addWidget(leftMid)
        splitter1.addWidget(leftBottom)

    
        splitter2 = QSplitter(Qt.Horizontal)
        splitter2.addWidget(splitter1)
        splitter2.addWidget(mid)
        splitter2.addWidget(right)

        # finally add the main horiz splitter to the root
        rootBox.addWidget(splitter2)
        rootWidget.setLayout(rootBox)    
        


    def build_frame_left(self):
        pass


    def showDate(self, date):
        self.lbl.setText(date.toString())

    def make_toolbar_button(self, toolbar, theme, name, icon_name, cmd_name, shortcut, tooltip):
        thisAct = QAction(QIcon(lp_screen.get_theme_icon(theme, icon_name)), name, self)
        thisAct.setShortcut(shortcut)
        thisAct.setStatusTip(tooltip)
        thisAct.triggered.connect(self.get_run_command(cmd_name))
        toolbar.addAction(thisAct)


        return thisAct


    def get_run_command(self, cmd_name, param=[]):
        """
        high level function to parse commands to correct module 
        """
        if cmd_name == 'quit':
            return self.close

        return self.dummy

    def dummy(self):  
        print('running dummy command ' )  


if __name__ == '__main__':  
    main()        