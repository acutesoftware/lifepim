#!/usr/bin/python3
# coding: utf-8
# server.py

import os
import time 
import config as mod_cfg
import index as mod_index

import interfaces.web.web_server as web_server

def start_server():
    """
    run server locally for a single user
    """
    print('Welcome', mod_cfg.get_conn_str()['user'])
    if not is_authorised():
        print('Sorry, wrong password')
        exit(1)
    print('server started...')

    # startup tasks
    mod_index.refresh_indexes_if_needed()
    TEST()

    # start web server
    web_server.start_server()




def is_authorised():
    res = input('Enter password ')
    if res != mod_cfg.get_conn_str()['pass']:
        time.sleep(2)
        return False
    return True

def TEST():
    """
    display status
    """

    print('data_folder = ', mod_cfg.data_folder)
    print('index_folder = ', mod_cfg.index_folder)
    print('logon_file = ', mod_cfg.logon_file)


#############################################################
## Server background tasks
#############################################################

"""
TODO
- long running jobs like index get called and return immediately
- status saved to show on webserver (last updated| running )

"""




if __name__ == '__main__':
    start_server()

