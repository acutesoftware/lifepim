# data.py


import sys
import os 
import csv

#import numpy as np

from PyQt5.QtCore import Qt, QDir, QItemSelectionModel, QAbstractTableModel, QModelIndex, QVariant, QSize, QSettings
from PyQt5.QtWidgets import (QMainWindow, QTableView, QApplication, QToolBar, QLineEdit, QComboBox, QDialog, 
                                                            QAction, QMenu, QFileDialog, QAbstractItemView, QMessageBox, QWidget)
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QCursor, QIcon, QKeySequence, QTextDocument, QTextCursor, QTextTableFormat
from PyQt5 import QtPrintSupport

from PyQt5.QtWidgets import QVBoxLayout

import pandas as pd

"""
def create_widget_dataview(parentGUI):
    wid =  QTableView() #QTableWidget #
    wid.resize(900,900)
    return wid
"""



class lpDataWidget(QWidget):
    def __init__(self, *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        vlay = QVBoxLayout(self)  # was HBox


        self.tbl = QTableView() # parentUI.MainWidgetDataview

        vlay.addWidget(self.tbl)

        

        self.tbl.resize(900,900)
        self.settings = QSettings('Axel Schneider', 'QTableViewPandas')
        self.table = self.tbl # parentUI.MainWidgetDataview

        self.data = [
          [4, 9, 2],
          [1, 0, 0],
          [3, 5, 0],
          [3, 3, 2],
          [7, 8, 9],
        ]


        self.tbl.model =  PandasModel()
        self.tbl.setModel(self.tbl.model)
        self.tbl.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        self.tbl.setSelectionMode(self.tbl.SingleSelection)


        self.tbl.verticalHeader().setVisible(True)
        self.tbl.setGridStyle(1)
        self.model =  PandasModel()
        self.tbl.setModel(self.model)
        self.tbl.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        self.tbl.setSelectionMode(self.tbl.SingleSelection)
        self.setStyleSheet(stylesheet(self))
        self.tbl.setAcceptDrops(True)
        #self.setCentralWidget(self.tbl)
        self.setContentsMargins(10, 10, 10, 10)

        #self.model = TableModel_OLD(self.data)
        #self.setStyleSheet(stylesheet(self))
        self.tbl.setAcceptDrops(True)
        self.tbl.setFocus()    
        
    def get_data(self):
        return self.model._df.values

    def setParent(self, parentUI):
        self.parentUI = parentUI  # this is a frame
        #parentUI.setCentralWidget(self.table)
        self.show()

    def show_file(self, fname):
        self.cur_filename = fname 
        self.load_csv(self.cur_filename)
        print(self.tbl.model)
        self.show()
        

    def load_csv(self, filename):
        self.csv_text = open(filename, "r").read()
        self.data = []
        delimiter = ","

        f = open(filename, 'r+b')
        with f:
            df = pd.read_csv(f, delimiter = ',', keep_default_na = False, low_memory=False, header=None)
            f.close()
            self.tbl.model = PandasModel(df)
            self.tbl.setModel(self.tbl.model)
            self.tbl.resizeColumnsToContents()
            self.tbl.selectRow(0)
        print('loaded pandas model')    
        print(str(self.tbl))


    def load_csv_OLD_works(self, filename):
        self.csv_text = open(filename, "r").read()
        self.data = []
        delimiter = ","
        row = 0
        for listrow in self.csv_text.splitlines():
            #print('adding row = ' + str(listrow))
            self.data.append(listrow.split(delimiter))
            row += 1
        #print(self.data)
        print('read ' + str(row) + ' rows')
        self.model = TableModel_OLD(self.data)
        self.table.setModel(self.model)



class TableModel_OLD(QAbstractTableModel):
    def __init__(self, data):
        super(TableModel_OLD, self).__init__()
        self._data = data

    def data(self, index, role):
        return self._data[index.row()][index.column()]

    def rowCount(self, index):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, index):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        return len(self._data[0])


class PandasModel(QAbstractTableModel):
    def __init__(self, df = pd.DataFrame(), parent=None): 
        QAbstractTableModel.__init__(self, parent=None)
        self._df = df
        self.setChanged = False
        self.dataChanged.connect(self.setModified)


    def setModified(self):
        self.setChanged = True
        print(self.setChanged)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            try:
                return self._df.columns.tolist()[section]
            except (IndexError, ):
                return QVariant()
        elif orientation == Qt.Vertical:
            try:
                return self._df.index.tolist()[section]
            except (IndexError, ):
                return QVariant()

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if (role == Qt.EditRole):
                return self._df.values[index.row()][index.column()]
            elif (role == Qt.DisplayRole):
                return self._df.values[index.row()][index.column()]
        return None

    def setData(self, index, value, role):
        row = self._df.index[index.row()]
        col = self._df.columns[index.column()]
        self._df.values[row][col] = value
        self.dataChanged.emit(index, index)
        return True

    def rowCount(self, parent=QModelIndex()): 
        return len(self._df.index)

    def columnCount(self, parent=QModelIndex()): 
        return len(self._df.columns)

    def sort(self, column, order):
        colname = self._df.columns.tolist()[column]
        self.layoutAboutToBeChanged.emit()
        self._df.sort_values(colname, ascending= order == Qt.AscendingOrder, inplace=True)
        self._df.reset_index(inplace=True, drop=True)
        self.layoutChanged.emit()

def stylesheet(self):
        return """
    QMainWindow
        {
         background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                 stop: 0 #E1E1E1, stop: 0.4 #DDDDDD,
                                 stop: 0.5 #D8D8D8, stop: 1.0 #D3D3D3);
        }
        QMenuBar
        {
            background: transparent;
            border: 0px;
        }
        QTableView
        {
            background: qlineargradient(y1:0,  y2:1,
                        stop:0 #d3d7cf, stop:1 #ffffff);
            border: 1px solid #d3d7cf;
            border-radius: 0px;
            font-size: 8pt;
            selection-color: #ffffff
        }
        QTableView::item:hover
        {   
            color: #eeeeec;
            background: #c4a000;;           
        }
        
        
        QTableView::item:selected {
            color: #F4F4F4;
            background: qlineargradient(y1:0,  y2:1,
                        stop:0 #2a82da, stop:1 #1f3c5d);
        } 
        QTableView QTableCornerButton::section {
            background: transparent;
            border: 0px outset black;
        }
    QHeaderView
        {
         background: qlineargradient( y1: 0, y2: 1,
                                 stop: 0 #E1E1E1, stop: 0.4 #DDDDDD,
                                 stop: 0.5 #D8D8D8, stop: 1.0 #D3D3D3);
        color: #888a85;
        }
    QToolBar
        {
        background: transparent;
        border: 0px;
        }
    QStatusBar
        {
        background: transparent;
        border: 0px;
        color: #555753;
        font-size: 7pt;
        }
    """        