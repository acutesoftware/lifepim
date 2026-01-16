#!/usr/bin/python3
# -*- coding: utf-8 -*-
# run_tests.py

import os
import time
import unittest as unittest

# List of temp files to wipe after tests run

files_to_wipe = [
]

# run all tests in tests folder
all_tests = unittest.TestLoader().discover('.', pattern='test*.py')
unittest.TextTestRunner().run(all_tests)    

def wipe_file(fname):
    """
    removes test file left behind without worrying if they cant be 
    deleted. Used only to make a git status look clean.
    """
    try:
        os.remove(fname)
        print('deleted ' + fname)
    except Exception as ex:
        print('ERROR - cant delete ' + fname + ' : ' + str(ex))
        
print('Did the tests fail.... DID YOU TURN ON VIRTUALENV!   ". ~/p von"')
print('WIPING ALL TEST RESULTS - PRESS CTRL C TO STOP')

time.sleep(5)

for f in files_to_wipe:
    wipe_file(f)    



