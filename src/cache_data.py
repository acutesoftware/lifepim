#!/usr/bin/python3
# coding: utf-8
# cache_data.py

import datetime
import os 
import sys
import time 
import csv
from csv import reader as csvreader


class DataDefinition(object):
    """
    defines how data is retrieved
    """
    def __init__(self, cache_manager, name,  max_age):
        self.name = name
        self.cache_manager = cache_manager
        self.cache_result = self.get_clean_file_name(name)
        self.max_age = max_age
        

    def __str__(self):
        res = ''
        res += 'name         : ' + self.name + '\n'
        res += 'cache_result : ' + self.cache_result + '\n'
        res += 'max_age      : ' + str(self.max_age) + '\n'

        return res

    def get_clean_file_name(self, txt):
        res = txt.replace(' ', '_').replace('\\', '_').replace('/', '_').replace('.', '_').replace(',', '_')

        return os.path.join(self.cache_manager.cache_data_path, res + '.csv')

class CacheManager(object):
    def __init__(self, cache_data_path):
        self.cache_data_path = cache_data_path

        self.cache_objects = []
        # check we can write to the cache path
        with open(os.path.join(self.cache_data_path, '__admin__.txt'), 'w') as f:
            f.write('starting cache manager \n')

    def __str__(self):
        res = '-=+ CACHE MANAGER +=-\n'
        for c in self.cache_objects:
            fname = os.path.join(self.cache_data_path, c.data_def.cache_result)
            res += c.data_def.name + ' = ' + c.data_def.cache_result + '\n'
        return res

    def wipe_cache(self):
        for c in self.cache_objects:
            fname = os.path.join(self.cache_data_path, c.data_def.cache_result)
            print('deleting ', fname)

    def add_dataset(self, data_cache):
        #assert(data_cache is type(CacheDataSet))
        self.cache_objects.append(data_cache)


class CacheDataSet(object):
    def __init__(self, data_def):
        self.data_def = data_def
        self.data = []
        self.time_saved = time.time() 
        self.date_refreshed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S%z")

    def __str__(self):
        res = 'Cached Data Set'
        res += str(self.data_def)
        res += 'Last saved ' + str(self.time_saved)
        return res


    def is_data_dirty(self):
        time_now = time.time() # datetime.datetime.now() #.strftime("%I:%M%p %d-%B-%Y")
        if self.data == []:
            return True 
        if time_now > self.time_saved + self.data_def.max_age:
            return True
        else:
            return False

    def refresh_data(self, data_to_save_as_list):
        """
        takes the list from the calling program and saves it as
        a cached CSV file, ready for other uses.
        Can optionally leave it in memory in the self.data list
        """
        self.time_saved = time.time() # datetime.datetime.now() #.strftime("%I:%M%p %d-%B-%Y")
        self.date_refreshed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S%z")
        self.data = data_to_save_as_list
        # now save the data to csv 

        with open(self.data_def.cache_result, "w", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerows(self.data)
        
        # now force a reload from cache to ensure consistancy
        # (see test_cache_data for oddness with numbers in lists)
        self.reload_data_from_cache()

    def reload_data_from_cache(self):
        """
        force data to be reloaded from cache
        """

        with open(self.data_def.cache_result, 'r') as fp:
            reader = csvreader(fp)
            # works but puts quotes on numbers self.data = list(list(rec) for rec in csv.reader(fp, delimiter=','))
            self.data = []
            for rec in csv.reader(fp, delimiter=','):
                row_dat = []
                for col in rec:
                    row_dat.append(col)
                self.data.append(row_dat)
        self.time_saved = time.time()  # reset this, as the cache is now current  
        self.date_refreshed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S%z")      


    def get_data(self):
        """
        returns the data for data_def which is usually
        the cached version.
        - if cached version doesnt exist, refresh data to TXT
        - if the cached version is old , refresh data to TXT
        - if cached version exists and is current, return TXT
        """
        
        if self.is_data_dirty():
            self.reload_data_from_cache()
            print('Data loaded from cache : ' + self.data_def.name)
        else:
            print('using cached data for ' + self.data_def.name)
        return self.data