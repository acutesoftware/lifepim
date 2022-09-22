#!/usr/bin/python3
# coding: utf-8
# test_interface_netdiary.py
import os
import sys
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." )
pth = os.path.join(root_folder, '..', 'lifepim', 'src')

sys.path.append(pth)

from interfaces.file_system import interface_netdiary as mod_if



class TestInterfaceNetdiary(unittest.TestCase):

    def test_01_import_module(self):

        mod_if.query_diary()
        self.assertEqual(200, 200)



if __name__ == '__main__':
    unittest.main()
