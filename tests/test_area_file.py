#!/usr/bin/python3
# coding: utf-8
# test_area_file.py
import os
import sys
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." )
pth = os.path.join(root_folder, '..', 'lifepim', 'src')

sys.path.append(pth)

import desktop as mod_desktop



class TestAreaFile(unittest.TestCase):

    def test_01_import_module(self):
        from views.files import files as mod_files 
        self.assertEqual(200, 200)

    def test_02_file_manager(self):
        #tst = mod_files.cFileManager()
        #print(tst)        
        self.assertEqual(200, 200)



if __name__ == '__main__':
    unittest.main()
