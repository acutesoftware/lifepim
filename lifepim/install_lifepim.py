# install_lifepim.py

import os

cur_fldr = os.path.abspath(os.path.dirname(os.path.abspath(__file__))) 
settings_file = 'lifepim.cfg'
cfg_file = cur_fldr + os.sep + settings_file
print('LifePIM public folder is at : ' , cfg_file)

def main():
    if not os.path.isfile(cfg_file):
        configure()
    start_lifepim()

def configure():
    print('\n /-----------------------\\ ')
    print(' |  Welcome to LifePIM  | ')
    print(' \-----------------------/ \n')
    print('This script asks for a folder to save to, and builds the database scripts.')
    print('You can do this manually by setting creating the file ' + settings_file )
    print('in your current folder (' + cur_fldr + ')')
    print('')
    fldr = get_local_config()
    if fldr == '':
        fldr = ask_for_folder()
    print('Folder = ' + fldr)
    
    
def ask_for_folder():
    print('Please enter the folder to save your personal data [press enter to use current folder]\n')
    fldr = input('Current Folder = ' + cur_fldr)
    if fldr == '':
        fldr = cur_fldr
        with open(cfg_file, 'w') as f:
            f.write(fldr)
    return fldr
    
def get_local_config():
    fldr = ''
    try:
        with open(cfg_file, 'r') as f:
            fldr = f.read()
    except Exception:
        pass
    return fldr

def start_lifepim():
    """
    starts the web interface and possibly other processes
    """
    os.system("start go_web_lifepim.bat") 

main()
