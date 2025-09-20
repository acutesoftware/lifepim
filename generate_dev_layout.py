# generate_dev_layout.py
# written by Duncan Murray 15/9/2025

from src import config as mod_cfg
from pprint import pprint

def main():
    show_layout()
    print(mod_cfg.ui_actions)
    print(mod_cfg.filters)

    spec_cal = generate_table_spec("calendar", "date DATE, time TEXT 4, event_summary TEXT 200, event_type TEXT 200, details TEXT BLOB")
    spec_note = generate_table_spec("note", "date DATE, time TEXT 4, note_summary TEXT 2000, note_type TEXT 200, details TEXT BLOB")
        
    
    pprint(spec_cal,sort_dicts=False)
    spec_cal_view_list = generate_view_spec(spec_cal, 'LIST', ['date', 'time', 'event_summary'])
    pprint(spec_cal_view_list,sort_dicts=False)

    spec_note_view_card = generate_view_spec(spec_note, 'CARD', ['details'])
    pprint(spec_note_view_card,sort_dicts=False)


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


def generate_table_spec(nme, cols_as_string):
    """
    {'tbl': 'c_calendar',
    'cols': [{'nme': 'date', 'tpe': 'DATE', 'sze': ''},
            {'nme': 'time', 'tpe': 'TEXT', 'sze': '4'},
            {'nme': 'event_summary', 'tpe': 'TEXT', 'sze': '200'},
            {'nme': 'event_type', 'tpe': 'TEXT', 'sze': '200'},
            {'nme': 'details', 'tpe': 'TEXT', 'sze': 'BLOB'}]}
    """
    cols = [c.strip() for c in cols_as_string.split(',')]
    tbl = f"c_{nme}".replace(" ","_").lower()
    op = {'id': 'tbl_' + nme}
    op['tbl'] = tbl 
    op['cols'] = []
    for c in cols:
        col_name = c.split(' ')[0]  # in case of types like "id INTEGER"
        col_type = c.split(' ')[1] if len(c.split(' ')) > 1 else 'TEXT'
        col_len = c.split(' ')[2] if len(c.split(' ')) > 2 else ''
        op['cols'].append({'nme':col_name, 'tpe':col_type, 'sze':col_len})

    return op

def generate_view_spec(spec_cal, tpe, col_lis_view):
    """
    attempts to define a standard way of displaying any data
    This will start with STANDARD ones which should cover most cases
    but there will be custom jinja pages needed (eg Maps, ETL)

    {'id': 'layout_c_calendar_list',
    'tbl': 'c_calendar',
    'view': 'list',
    'display_cols': [{'nme': 'date'}, {'nme': 'time'}, {'nme': 'event_summary'}]}
    """

    op = {'id': 'layout_' + spec_cal['tbl'] + '_' + tpe.lower(), 
          'tbl':spec_cal['tbl']}

    if tpe == 'LIST':
        op['view'] = 'list'
        op['display_cols'] = []
        for c in col_lis_view:
            op['display_cols'].append({'nme':c})
    elif tpe == 'CARD':
        op['view'] = 'card'
        op['display_cols'] = []
        for c in col_lis_view:
            op['display_cols'].append({'nme':c})

    else:
        print(f"ERROR - view type {tpe} not recognised")
        return {}
    return op

def generate_filter_spec():
    """
    creates a filter spec for tables to be displayed.
    Shopping List = select from FOOD where PROJ = 'Home'
    Holiday Pictures = select from photos where location != 'Home'
    PC Notes = select from NOTES where project = 'PC'
    Weekend Tasks = select from TASKS where due_date >= '2024-09-21' and due_date <= '2024-09-22'

    """
    print('TODO')



main()        