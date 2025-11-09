
# shows that some paths have odd unicode characters
# ['0x20', '0x20', '0x20', '0x20', '0x20', '0x2d']
import os, unicodedata
p = r"N:/DATA/3D_gdrive_backedup/PURCHASED/GUI_user_interface/humble_bundle_2021_GUI/guiiconspack1/icon set 700/icon (260  260)/101-200/120.png"
print(len(p))
print([hex(ord(c)) for c in p if c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_/\\:.()"])

