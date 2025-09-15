# generate_dev_layout.py
# written by Duncan Murray 15/9/2025

from src import config as mod_cfg


def main():
    show_layout()



def get_table_name(top_menu, sub_menu):
    if sub_menu == '':
        return f"c_{top_menu}".replace(" ","_").lower()
    return f"c_{top_menu}_{sub_menu}".replace(" ","_").lower()

def show_layout():    
    for tab in mod_cfg.TABS:
        tbl = get_table_name(tab['id'], '')
        print(f"Top Menu =  {tab['icon']} {tab['label']}  (data = '{tbl}')")
        
        for sub_menu in mod_cfg.sub_menus:
            if sub_menu['root'] == tab['id']:
                tbl = get_table_name(tab['id'], sub_menu['name'])
                print(f"    - {sub_menu['name']}  (data = '{tbl}')")

main()        