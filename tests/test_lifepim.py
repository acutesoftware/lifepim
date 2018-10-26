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

local_site = 'http://127.0.0.1:5000'
live_site = 'https://www.lifepim.com'

#site_to_test = local_site
site_to_test = live_site


class TestLifePIM(unittest.TestCase):

    def test_01_connect(self):
        res = mod_lp.connect()
        self.assertEqual(res, 200)

    def test_02_valid_page(self):

        c = mod_lp.LifePimConnect(site_to_test,'')
        res = c.get_page('/about', 200)
        self.assertTrue(len(res) > 500)




    def test_03_no_such_page(self):

        c = mod_lp.LifePimConnect(site_to_test,'')
        res = c.get_page('/blahBLAH', 200)
        if res:
            self.assertEqual('this should have failed', 'YES')
        else:
            self.assertEqual(1,1)


    def test_04_API_public(self):
        c = mod_lp.LifePimConnect(site_to_test, '')
        #print(c)
        #http://127.0.0.1:5000/API/V1/get_note/fsdf
        res = c.get_page('/API/V1/get_note/My Note', '200')
        print(res)


if __name__ == '__main__':
    unittest.main()
