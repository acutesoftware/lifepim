# lifepim.py

import os
import sys
import requests


lp_url = 'https://www.lifepim.com'
lp_user = 'YOUR_USERNAME'
lp_pass = 'YOUR_PASSWORD'



def connect():
    print('connecing to lifepim...')

    c = LifePimConnect(lp_url,'')
    res = c.get_page('/about', 200)
    if res:
        return 200
    else:
        return 404


class LifePimConnect(object):
    def __init__(self, base_url, logon_data):
        self.url = base_url
        self.logon_data =  logon_data


    def get_page(self, page_short, expected_response):
        r = requests.get(self.url + page_short)
        if r.status_code == expected_response:
            return r.text.encode('utf8')
        else:
            return False



    def post_data(self, page_short, payload, expected_response):
        with requests.Session() as s:
            r = s.post(self.url + '/login', data=self.logon_data)
            if 'Please Enter your username and password' in r.text:
                print('Wrong username - login failed ' , str(self.logon_data))
            else:
                r = s.post(self.url + page_short, data= payload, verify=False)
                if r.status_code == expected_response:
                    return r.text.encode('utf8')
                else:
                    return False





if __name__ == '__main__':
    TEST()
