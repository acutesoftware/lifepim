#!/usr/bin/python3
# coding: utf-8
# test_area_data.py
import os
import sys
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + 'src')
pth = os.path.join(root_folder,  'common')

print (pth)
sys.path.append(pth)

import if_sqlite as mod_sqlite


class TestETL(unittest.TestCase):

    def test_01_check_etl(self):

        self.assertEqual(1, 1)




if __name__ == '__main__':
    unittest.main()
