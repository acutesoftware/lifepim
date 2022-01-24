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
        tbar2 = self.addToolBar('PIM')
        calAct = self.make_toolbar_button(tbar2, theme, 'cal', 'cal', 'cal', 'Ctrl+1', 'Calendar')
        addrAct = self.make_toolbar_button(tbar2, theme, 'addr', 'addr', 'addr', 'Ctrl+2', 'Address Book')
        taskAct = self.make_toolbar_button(tbar2, theme, 'bell', 'bell', 'bell', 'Ctrl+3', 'Todo List and Reminders')
        noteAct = self.make_toolbar_button(tbar2, theme, 'book', 'book', 'book', 'Ctrl+4', 'Add Note')
        shelfAct = self.make_toolbar_button(tbar2, theme, 'bookshelf', 'bookshelf', 'bookshelf', 'Ctrl+4', 'All Notes')

        drawAct = self.make_toolbar_button(tbar2, theme, 'chalkboard', 'chalkboard', 'chalkboard', 'Ctrl+5', 'Drawings and Ideas')
        imgAct = self.make_toolbar_button(tbar2, theme, 'camera', 'camera', 'camera', 'Ctrl+7', 'Images')

        toolbar = self.addToolBar('Data')
        exitAct = self.make_toolbar_button(toolbar, theme, 'Exit', 'exit', 'quit', 'Ctrl+Q', 'Exit application')
        cutAct = self.make_toolbar_button(toolbar, theme, 'Cut', 'cut', 'cut', 'Ctrl+W', 'Cut data')
        fixAct = self.make_toolbar_button(toolbar, theme, 'Fix', 'fix', 'fix', 'Ctrl+G', 'Fix data')
        digAct = self.make_toolbar_button(toolbar, theme, 'Dig', 'dig', 'dig', 'Ctrl+D', 'Dig into data')



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
        print('building main screen into ' + str(rootWidget))

        """ BELOW 3 lines work - attaches a text editor in a widget under main window
        textEdit = QTextEdit()
        lay = QVBoxLayout(rootWidget)
        lay.addWidget(textEdit)

        """
        # Step 1 - make the splitter interface
        hbox = QHBoxLayout(self)

        topleft = QFrame(self)
        topleft.setFrameShape(QFrame.StyledPanel)

        topright = QFrame(self)
        topright.setFrameShape(QFrame.StyledPanel)

        bottom = QFrame(self)
        bottom.setFrameShape(QFrame.StyledPanel)


        
        #textEdit = QTextEdit()
        #bottom.addWidget(textEdit)        

        splitter1 = QSplitter(Qt.Horizontal)
        splitter1.addWidget(topleft)
        splitter1.addWidget(topright)

        

        splitter2 = QSplitter(Qt.Vertical)
        splitter2.addWidget(splitter1)
        splitter2.addWidget(bottom)

        hbox.addWidget(splitter2)
        rootWidget.setLayout(hbox)    
        


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