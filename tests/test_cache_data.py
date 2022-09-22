#!/usr/bin/python3
# coding: utf-8
# test_cache_data.py
import os
import sys
import unittest

import time

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." )
pth = os.path.join(root_folder, '..', 'lifepim', 'src')

sys.path.append(pth)
import cache_data as mod_data

cache_path = os.path.abspath(os.path.dirname(os.path.abspath(__file__))) #'.'
my_cache = mod_data.CacheManager(cache_path)


class TestCacheData(unittest.TestCase):
    def test_01_data_definition(self):
        dt = mod_data.DataDefinition(my_cache,  'test data', 30)
        self.assertEqual(dt.name, 'test data')
        self.assertEqual(dt.cache_result, 'test_data.csv')
        self.assertEqual(dt.max_age, 30)

    def test_02_data_cache(self):
        dt = mod_data.DataDefinition(my_cache,  'test2', 1)
        test_data = [['hi','there'],['this is a field, WITH a comma','3']]

        my_data = mod_data.CacheDataSet(dt)
        my_data.refresh_data(test_data)
        self.assertEqual(my_data.is_data_dirty(), False)
        time.sleep(1)
        self.assertEqual(my_data.is_data_dirty(), True)
        
        res = my_data.get_data()
        self.assertEqual(res,test_data)
 
    def test_03_data_cache_WATCH_NUMBERS(self):
        dt = mod_data.DataDefinition(my_cache, 'test3', 1)

        test_data = [['hi','there'],[345.331,12000]]
        my_data = mod_data.CacheDataSet(dt)
        my_data.refresh_data(test_data)

        # original code returned list as numbers, but to make it consistant
        # will force reload from CSV on refresh to ensure consistancy
        # (meaning original tests below )
        #res1 = my_data.get_data()
        #self.assertEqual(res1,[['hi','there'],['345.331','12000']])  # used to be the same
        #time.sleep(2)
        
        res2 = my_data.get_data()  # after CSV reload, numbers are quoted
        self.assertEqual(res2,[['hi','there'],['345.331','12000']])


    def test_04_cache_manager(self):

        # recreate objects above 
        dt1 = mod_data.DataDefinition(my_cache,  'test2', 1)
        test_data1 = [['hi','there'],['this is a field, WITH a comma','3']]
        my_data1 = mod_data.CacheDataSet(dt1)
        my_data1.refresh_data(test_data1)

        dt2 = mod_data.DataDefinition(my_cache,  'test3', 1)
        test_data2 = [['hi','there'],[345.331,12000]]
        my_data2 = mod_data.CacheDataSet(dt2)
        my_data2.refresh_data(test_data2)

        my_cache.add_dataset(my_data1)
        my_cache.add_dataset(my_data2)
        self.assertEqual(str(my_cache), '-=+ CACHE MANAGER +=-\ntest2 = test2.csv\ntest3 = test3.csv\n')
        self.assertEqual(my_cache.cache_data_path, os.path.abspath(os.path.dirname(os.path.abspath(__file__))))
        #print(my_cache)
        
    def test_05_check_valid_cache_names(self):
        dt = mod_data.DataDefinition(my_cache,  'BLAH', 99)
        self.assertEqual(dt.get_clean_file_name('ABC/DEF'), 'ABC_DEF.csv')
        self.assertEqual(dt.get_clean_file_name('ABC,DEF'), 'ABC_DEF.csv')
        self.assertEqual(dt.get_clean_file_name('ABC\DEF'), 'ABC_DEF.csv')
        self.assertEqual(dt.get_clean_file_name('ABC\\DEF'), 'ABC_DEF.csv')
        self.assertEqual(dt.get_clean_file_name('ABC DEF'), 'ABC_DEF.csv')
        self.assertEqual(dt.get_clean_file_name('ABC.DEF'), 'ABC_DEF.csv')




if __name__ == '__main__':
    unittest.main()
