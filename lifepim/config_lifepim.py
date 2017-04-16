# config_lifepim.py

import os
import sys
""" 
Main Config File for LifePIM
----------------------------

When developing locally, use the local AIKIF lib folders as they are current

To test a deploy, use the deployed version

You can change the local personal folders here

"""

fldr = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + ".." + os.sep + "..")
cfg_fldr_aikif_lib = os.path.abspath(fldr + os.sep + "AIKIF" + os.sep + "aikif" )
cfg_fldr_aikif_data = os.path.abspath(fldr + os.sep + "AIKIF" + os.sep + "data" + os.sep + "core")
cfg_fldr_lifepim_root = os.path.abspath(fldr + os.sep + "lifepim")
cfg_fldr_lifepim_data = 'T:\\user\\AIKIF\\lifepim'
cfg_fldr_diary_data = 'T:\\user\\AIKIF\\diary'
print("root folder = " + fldr)  # 
print("AIKIF lib folder    = " + cfg_fldr_aikif_lib)
print("AIKIF data folder   = " + cfg_fldr_aikif_data)
print("LifePIM Root folder = " + cfg_fldr_lifepim_root)
print("LifePIM Data folder = " + cfg_fldr_lifepim_data)

sys.path.append(cfg_fldr_aikif_lib)
sys.path.append(cfg_fldr_lifepim_root)
