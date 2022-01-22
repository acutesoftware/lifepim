#!/usr/bin/python3
# coding: utf-8
# desktop.py 

import os 
import sys
import sys
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import  QAction 
from PyQt5.QtWidgets import  QTextEdit 
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtGui import QIcon




from interfaces import lp_screen
import config as mod_cfg



def main():
    app = QApplication(sys.argv)
    ex = LifePIM_GUI()
    sys.exit(app.exec_())


class LifePIM_GUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.build_gui()


    def build_gui(self):
        self.setGeometry(100, 100, 900, 600)
        self.setWindowTitle('LifePIM Desktop')
        self.setWindowIcon(QIcon('static/favicon.ico'))


        textEdit = QTextEdit()
        self.setCentralWidget(textEdit)

        exitAct = QAction(QIcon('exit24.png'), 'Exit', self)
        exitAct.setShortcut('Ctrl+Q')
        exitAct.setStatusTip('Exit application')
        exitAct.triggered.connect(self.close)


        self.statusBar().showMessage('Ready')


        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(exitAct)

        toolbar = self.addToolBar('Exit')
        toolbar.addAction(exitAct)

        self.show()





if __name__ == '__main__':  
    main()        