#!/usr/bin/python3
# coding: utf-8
# events.py
# functions to manage loading and saving events

import os 
import sys
import time
import config as mod_cfg

###############################################
#  Public Functions to manage data
###############################################

def get_root_event_folder():
    """
    returns the root folder where events are stored
    """
    return mod_cfg.calendar_folder

def get_calendar_filename_for_date(dte_as_string):
    """
    returns the filename where a calendar event should be kept
    format is events_YYYY_MM.csv
    """
    YYYY, MM = dte_get_YYYY_MM(dte_as_string)

    fname = 'events_' + YYYY + '_' + MM + '.csv'
    full_name = os.path.join(get_root_event_folder(), fname)
    return full_name


def dte_get_YYYY_MM(dte_as_string):
    YYYY = dte_as_string[0:4]
    MM = dte_as_string[5:7]
    return YYYY, MM


def get_events_for_date(dte):
    print('returning events for date ', dte)
    fname = get_calendar_filename_for_date(dte)

    print('loading events from ' + fname)

    return []


###############################################
#  Classes for Event and Events
###############################################

class Event(object):
    def __init__(self, dte_as_string, length, details):
        self.dte_as_string = dte_as_string
        self.details = details
        self.length = length
    def __str__(self):
        res = self.dte_as_string + ' (' 
        res += self.length + ') '
        res += details
        return res

class Events(object):
    def __init__(self, events_list):
        self.events_list = events_list
    def __str__(self):
        res = 'List of Events\n'
        for event in events_list:
            #assert event is 
            res += str(event)

    


###############################################
#  Utils for Events
###############################################

def dte():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def TEST():
    print('Root folder = ', get_root_event_folder())
    print(get_calendar_filename_for_date('2020-06-22'))
    print(get_calendar_filename_for_date('2015-01-01'))
    print(get_events_for_date('2020-07-22'))



TEST()