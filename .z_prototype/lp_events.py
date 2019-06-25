#!/usr/bin/python3
# coding: utf-8
# lp_events.py

import os
import sys

def TEST():
    """
    self test for events
    """
    print('generating test events')
    e = LifePIM_Event('20180309', 'testing')
    print(e)
    
    event_list = LifePIM_EventList('Sample Event List')
    event_list.add_event('2018', 'Christmas')
    event_list.add_event('Thu', 'Payday')
    
    print(event_list)
    
    
    
class LifePIM_Event(object):
    """
    handles a single lifepim event, with formatting
    ready for website
    """
    def __init__(self, dte_str, details):
        self.dte_str = dte_str
        self.details = details
    def __str__(self):
        res = self.dte_str + ' ' + self.details + '\n'
        return res
        
        
class LifePIM_EventList(object):
    """
    handles a collection of events, usually parsed from 
    a logfile ready to be uploaded
    """
    def __init__(self, nme):
        self.nme = nme
        self.events = []
        
    def __str__(self):
        res = self.nme + '\n'
        for e in self.events:
            res += str(e)
        return res
    
    def add_event(self, dte_str, details):
        e = LifePIM_Event(dte_str, details)
        self.events.append(e)
        
    def get_list_for_upload(self):
        """
        returns the list ready for upload to lifepim
        """
        return self.events
        
    def create_from_logfile(self, fname):
        """
        
        """
        print('loading file... TODO')
        

if __name__ == '__main__':
    TEST()
    
