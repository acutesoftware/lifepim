#!/usr/bin/python3
# coding: utf-8
# quickadd.py 

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
from PyQt5.QtWidgets import QPushButton

import config as mod_cfg

def main():

    print('todo fix slider resize issue - see https://www.pythonguis.com/tutorials/pyqt-layouts/')

    app = QApplication(sys.argv)

    window = Main_GUI()
    window.show()

    app.exec()

class Main_GUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("LifePIM - Quick Add")

        btnAdd = QPushButton("Add Note")
        btnAdd.clicked.connect(self.event_btnAdd_clicked)

        self.qLabel = QLabel()
        self.qTextEdit = QLineEdit()
        
        # debug
        self.qTextEdit.textChanged.connect(self.qLabel.setText)

        layout = QVBoxLayout()
        layout.addWidget(self.qTextEdit)
        layout.addWidget(self.qLabel)
        layout.addWidget(btnAdd)

        container = QWidget()
        container.setLayout(layout)

        # Set the central widget of the Window.
        self.setCentralWidget(container)

        #self.setFixedSize(QSize(400, 300))

    def mouseMoveEvent(self, e):
        self.qLabel.setText("mouseMoveEvent")

    def mousePressEvent(self, e):
        self.qLabel.setText("mousePressEvent")

    def mouseReleaseEvent(self, e):
        self.qLabel.setText("mouseReleaseEvent")

    def mouseDoubleClickEvent(self, e):
        self.qLabel.setText("mouseDoubleClickEvent")


    def event_btnAdd_clicked(self):
        print('Adding Note - ' + self.qLabel.text())


main()