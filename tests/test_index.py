#!/usr/bin/python3
# coding: utf-8
# test_index.py
import os
import sys
import unittest

import time


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." )
pth = os.path.join(root_folder, '..', 'lifepim', 'src')

sys.path.append(pth)
import index as mod_index

class TestIndex(unittest.TestCase):
    def test_01_load_module(self):
        self.assertTrue('are' in  mod_index.stopwords)
        self.assertTrue('project' not in  mod_index.stopwords)

    def test_02_header(self):
        self.assertEqual(mod_index.extract_header('##My Header'), ('My Header', '1'))
        self.assertEqual(mod_index.extract_header('###Sub Heading'), ('Sub Heading', '2'))
        self.assertEqual(mod_index.extract_header('Just a normal line'), ('', 'normal'))

    def test_03_hashtags(self):
        self.assertEqual(mod_index.extract_hashtags('##My Header'), [])
        self.assertEqual(mod_index.extract_hashtags('#hashtag'), ['hashtag'])
        self.assertTrue(len(mod_index.extract_hashtags('#lots #of #tags')), 3)
        self.assertTrue(len(mod_index.extract_hashtags('not every #word has #tags')), 2)
        self.assertEqual(mod_index.extract_hashtags('##Heading with a #tag'), ['tag'])


if __name__ == '__main__':
    unittest.main()
