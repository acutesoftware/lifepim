#!/usr/bin/python3
# coding: utf-8
# log_file_uploader.py

import os
import sys

sys.path.append(os.path.join('..','lifepim'))

import lp_events

logfile_name = 'bank_transactions.csv'
logfile_col_mapping = {'date_str':0, 'details':[1,2]}

def main():
    print('parsing logfile')
    bills = lp_events.LifePIM_EventList('Bills Paid')
    raw = parse_log_file(logfile_name)
    for row in raw:
        bills.events.append(lp_events.LifePIM_Event(row[0],row[1]))
    
    
    #print(bills.get_list_for_upload())
    print(bills)
    
    
 
def parse_log_file(fname):
    lst = []
    with open(fname, 'r') as f:
        for line in f:
            lst.append(read_line(line, logfile_col_mapping))
    return lst
            

def read_line(txt, mapping):
    """
    reads a log line and parses according to mapping rules
    """
    cols = txt.split(',')
    return [cols[0], cols[1] + ':' + cols[2]]
                

if __name__ == '__main__':
    main()
    
