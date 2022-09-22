#!/usr/bin/python3
# coding: utf-8
# test_area_data.py
import os
import sys
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." )
pth = os.path.join(root_folder, '..', 'lifepim', 'src')

sys.path.append(pth)

import desktop
from PyQt5.QtWidgets import QApplication

from views.data import data as mod_data

class TestAreaFile(unittest.TestCase):

    def test_01_create_widget(self):
        app = QApplication(sys.argv)
        wdt = mod_data.lpDataWidget()
        self.assertEqual(wdt.data, [[1, 2, 3],['a', 'b', 'c']])

        # data as data frame
        #df = wdt.tbl
        #print(df)

    def test_02_data_manager(self):

        self.data = [[1, 2, 3],['a', 'b', 'c']]

        self.assertEqual(200, 200)



if __name__ == '__main__':
    unittest.main()
