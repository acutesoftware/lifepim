# data.py


import sys
import os 
import csv

#import numpy as np

from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import QTableView

from PyQt5.QtCore import QAbstractTableModel

from PyQt5 import Qt

class lpData(object):
    def __init__(self, parentUI) -> None:
        self.parentUI = parentUI
        self.lb = parentUI.MainWidgetDataview
        self.table = parentUI.MainWidgetDataview

        self.data = [
          [4, 9, 2],
          [1, 0, 0],
          [3, 5, 0],
          [3, 3, 2],
          [7, 8, 9],
        ]

        self.model = TableModel(self.data)
        self.table.setModel(self.model)


    def show_file(self, fname):
        self.cur_filename = fname 
        self.load_csv(self.cur_filename)
        

    def load_csv(self, filename):
        self.csv_text = open(filename, "r").read()
        self.data = []
        delimiter = ","
        row = 0
        for listrow in self.csv_text.splitlines():
            print('adding row = ' + str(listrow))
            self.data.append(listrow.split(delimiter))
            row += 1
        #print(self.data)
        print('read ' + str(row) + ' rows')
        self.model = TableModel(self.data)
        self.table.setModel(self.model)



class TableModel(QAbstractTableModel):
    def __init__(self, data):
        super(TableModel, self).__init__()
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


