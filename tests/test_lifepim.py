#!/usr/bin/python3
# coding: utf-8
# test_environment.py
import os
import sys
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." )
pth = os.path.join(root_folder, '..', 'lifepim', 'src')

sys.path.append(pth)

import desktop as mod_desktop



class TestLifePIM(unittest.TestCase):

    def test_01_import_desktop(self):
        import desktop
        self.assertEqual(200, 200)

    def test_02_import_infolink(self):
        import infolink
        self.assertEqual(200, 200)

    def test_02_import_config(self):
        import config 
        self.assertTrue(len(config.user_folder) > 1)


if __name__ == '__main__':
    unittest.main()
