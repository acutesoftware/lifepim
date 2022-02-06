#!/usr/bin/python3
# coding: utf-8
# lp_core.py



class LifePIM_Core(object):
    """
    this is the main core module for LifePIM that mananges all the 
    business rules (via data files) and has standard functionality.
    Note that all views are handled by the /views/ and data reading
    and writing is handled by /models/
    """
    def __init__(self):
        self.mod_lg = 'logfile handler'
        self.rules = 'rules handler'

    def lg(self, txt):
        """
        logfile wrapper for all lifepim desktop apps - uses users
        settings but called from lp_core for simplicity
        """
        print('TODO - log this message : ' + txt)

    def fn_search(self, dataset, txt):
        print('searching for ' + txt + ' in dataset ' + str(dataset))

    def fn_add(self, dataset, tbl, cols):
        print('adding ' + str(cols) + ' to ' + tbl + ' in dataset ' +  str(dataset))

        