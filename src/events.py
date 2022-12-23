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


def get_events_for_date(lst, dte):
    op = []
    for row in lst:
        if row[0] == dte:
            op.append(row)
    return op


###############################################
#  Classes for Event and Events
###############################################

class Event(object):
    def __init__(self, raw_line):
        cols = raw_line.split(',')
        self.dte_as_string = cols[0]
        self.time_as_string = cols[1]
        self.length = cols[2] 
        self.details = cols[3].replace('\n', '')
       
    def get_cols(self):
        return [self.dte_as_string, self.time_as_string, self.length, self.details]   

    def __str__(self):
        res = self.dte_as_string + ' ' + self.time_as_string + ' (' 
        res += self.length + ') '
        res += self.details
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

def process_pc_usage(fname):
    """
    takes a filename and summarises into events by day.

    """
    raw_dat = []
    all_dates = []
    with open(fname, 'r') as fip:
        raw = fip.readlines()
        #print('processing ' + str(len(raw)) + ' events')

    for line in raw:
        cur_event = Event(line)
        raw_dat.append(cur_event.get_cols())
        if cur_event.dte_as_string not in all_dates:
            all_dates.append(cur_event.dte_as_string)

    print(str(len(raw_dat)) + ' records')

    print('all dates = ' + str(all_dates))

    for dte in all_dates:
        cur_events = get_events_for_date(raw_dat, dte)
        cur_filename = mod_cfg.diary_pcusage_base_fname + '_' + dte + '.md'
        save_daily_diary_file(dte, cur_events, cur_filename)

    print('Finished processing')


def save_daily_diary_file(dte, cur_events, cur_filename):
    tot_time = 0
    pc_usage = []
    pc_apps = []
    raw_apps = []
    raw_usage = []
    time_start = '99:99'
    time_end = '00:00'

    for cur_line in cur_events:
        app = ''
        doc = ''
        try:
            cols = cur_line[3].split(' - ')
            if len(cols) == 1:
                doc = cols[0]
                app = cols[0] # ''
            elif len(cols) == 2:
                doc = cols[0]
                app = cols[1]
            else:
                doc = ''.join(c for c in cols[0:len(cols) - 1])
                app = cols[len(cols) - 1]
        except Exception as ex:
            print('doc = ' + doc + ', app = ' + app + '. ignore exception - ' + str(ex))
            pass

        
        raw_apps.append([app, int(cur_line[2])])
        raw_usage.append([cur_line[3], int(cur_line[2])])

    d_usage = {}
    for k, v in raw_usage:
        d_usage[k] = d_usage.get(k, 0) + v

    print('\n--------------------------------------\nUsage for ' + dte)
    for k, v in d_usage.items():
        if int(v/60) > 2:
            print(k + ' = ' + str(int(v/60)))


    d = {}
    for k, v in raw_apps:
        d[k] = d.get(k, 0) + v

    print('\n--------------------------------------\nApps for ' + dte)
    for k, v in d.items():
        if int(v/60) > 2:
            print(k + ' = ' + str(int(v/60)))


    with open(cur_filename, 'w') as fop:
        fop.write('---\n')
        fop.write('title : ' + dte + '\n')
        fop.write('tags :\n')
        fop.write('  - calendar\n')
        fop.write('  - d' + dte + '\n')
        fop.write('  - y' + dte[0:4] + '\n')
        fop.write('---\n\n')

        fop.write('### Application Summary\n```')
        for k, v in d.items():
            if int(v/60) > 2:
                fop.write(k + ' = ' + str(int(v/60)) + '\n')
        fop.write('```\n')
        
        fop.write('### PC Usage\n```')
        for k, v in d_usage.items():
            if int(v/60) > 2:
                fop.write(k + ' = ' + str(int(v/60)) + '\n')
        fop.write('```\n')
  




def TEST():
    process_pc_usage(r'N:\duncan\LifePIM_Data\DATA\diary\diary_sapling_duncan.txt')


TEST()