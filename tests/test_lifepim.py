#!/usr/bin/python3
# coding: utf-8
# test_environment.py
import os
import sys
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." ) 
pth = root_folder + os.sep + 'lifepim'
sys.path.append(pth)

import lifepim as mod_lp

class TestLifePIM(unittest.TestCase):
    
    def test_01_connect(self):
        res = mod_lp.connect()
        self.assertEqual(res, 200)


    
if __name__ == '__main__':
    unittest.main()
