#!/usr/bin/python3
# coding: utf-8
# server.py

import os
import time 
import config as mod_cfg

def start_server():
    """
    run server locally for a single user
    """
    print('Welcome', mod_cfg.get_conn_str()['user'])
    if is_authorised():
        server_loop()
    else:
        print('Sorry, wrong password')

def server_loop():
    print('server started...')

    TEST()

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


if __name__ == '__main__':
    start_server()

