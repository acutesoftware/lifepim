#!/usr/bin/python3
# coding: utf-8
# db_config_to_csv.py
# reads the random stuff in config.py and creates CSV
# for importing to SQLite (actually probably generates).

import os , sys
import random

op_folder = os.path.abspath(os.path.join(os.path.join(os.path.dirname(__file__), '..','..', 'data')))

cfg_path = os.path.abspath(os.path.join(os.path.join(os.path.dirname(__file__), '..', ',,', 'src', 'common')))
                           
print('cfg_path = ' + cfg_path)
sys.path.append(cfg_path)

import config as mod_cfg

# ---------------------------------------------------------------
# Old Config notes pasted


all_tables = [
    {'nme':'event',
     'cols':['id','dateevent_str','timeevent', 'details','event_type', 'proj'],
     'imp_cols':['dateevent_str','details'],
     'col_types':['id','Date','Time','Note','Text','List'],
     'search_col':['details','dateevent_str'],
     'url':'calendar',
       'page_function':'page_calendar',
     },
    {'nme':'note',  #      'cols':['id','title','pinned', 'important', 'content','proj','is_archived','is_private','is_encrypted','due_date', 'color'],
     'cols':['id','title','pinned', 'important','is_archived', 'color', 'content','proj'], #,'is_encrypted'],
     'imp_cols':['proj','title','content'],
     'col_types':['id','Text','Checkbox','Checkbox','Checkbox','Color', 'Note','List'], #'Checkbox'], #,'Checkbox','Checkbox','Checkbox', 'Date', 'Text'],
     'search_col':['title','content'],
     'url':'notes',
     'page_function':'page_notes',
    },
    {'nme':'task',
    'cols':['id','Title','Pinned', 'Important', 'Notes','proj','Done'],   # , 'due_date'
    'imp_cols':['proj','title','notes', 'Date'],
    'col_types':['id','Text','Checkbox','Checkbox', 'Note','List','Checkbox'],
     'search_col':['title','notes'],
    'url':'tasks',
    'page_function':'page_tasks',
    },

    {'nme':'task_project',
    'cols':['id','category', 'title','proj'],   # , 'due_date'
    'imp_cols':['title'],
    'col_types':['id','Number','Text','List'],
    'search_col':['title'],
    'url':'projects',
    'page_function':'page_projects',
    },
    {'nme':'goal',
    'cols':['id','goal_area','goal_name','proj', 'goal_note'],
    'imp_cols':['goal_area','goal_name','goal_note'],
    'col_types':['id','Text','Text','List','Text'],
     'search_col':['goal_area','goal_name','goal_note'],
    'url':'goals',
    'page_function':'page_goals',
    },
    {'nme':'place',
     'cols':['id','nme','proj'],
     'imp_cols':['nme'],
     'col_types':['id','List', 'Text'],
     'search_col':[],
     'url':'places',
     'page_function':'page_places',
    },
    {'nme':'money',
     'cols':['id','nme','proj', 'amount'],
     'imp_cols':['nme'],
     'col_types':['id','List','Text','Number'],
     'search_col':[],
     'url':'money',
     'page_function':'page_money',
    },
    {'nme':'ref_badges',
     'cols':['badge_area', 'badge_name', 'badge_desc'],
     'imp_cols':['badge_name'],
     'col_types':['Text','Text','Text'],
     'search_col':[],
     'url':'badges',
     'page_function':'page_badges',
    },
    {'nme':'music',
     'cols':['id','nme','proj'],
     'imp_cols':['nme'],
     'col_types':['id','Text','List'],
     'search_col':[],
     'url':'music',
     'page_function':'page_music',
    },
    {'nme':'images',
     'cols':['id','nme','proj'],
     'imp_cols':['nme'],
     'col_types':['id','Text','List'],
     'search_col':[],
     'url':'images',
     'page_function':'page_images',
    },
    {'nme':'files',
     'cols':['id','nme','proj'],
     'imp_cols':['nme'],
     'col_types':['id','Text','List'],
     'search_col':[],
     'url':'files',
     'page_function':'page_files',
    },
    {'nme':'apps',
    'cols':['id','proj','app_name','app_desc','app_launch_url', 'app_notes'],
    'imp_cols':['app_name','app_desc','app_launch_url','app_notes','proj'],
    'col_types':['id','List','Text','Text','Text', 'Note'],
     'search_col':['app_name','app_desc','app_launch_url'],
    'url':'apps',
    'page_function':'page_apps',
    },
    {'nme':'data_tables', #    'cols':['id','table_name','color','proj','num_rows','num_cols', 'table_desc'],
    'cols':['id','table_name','color','proj', 'table_desc'],
    'imp_cols':['table_name','table_desc'],
    'col_types':['id','Text','Color','List','Text','Text','Text'],
     'search_col':['table_name', 'table_desc'],
    'url':'data_tables',
    'page_function':'page_data',
    },
    {'nme':'data_values',
    'cols':['id','table_id', 'is_header','is_hdr_short_name','is_col_type_def', 'is_default_values', 'is_row_data',
            'col1','col2','col3','col4','col5','col6','col7','col8','col9' ],
    'imp_cols':['col1','col2','col3','col4','col5','col6','col7','col8','col9'],
    'col_types':['id','Hidden','Hidden','Hidden','Hidden','Hidden','Hidden','Text','Text','Text','Text','Text','Text','Text','Text','Text'],
     'search_col':['col1','col2','col3','col4','col5','col6','col7','col8','col9'],
    'url':'data_values',
    'page_function':'page_data_values',
    }
    ]



# ---------------------------------------------------------------

def main():
    generate_csv_from_db_config()
    create_ref_tables()


def lst_to_csv_str(lst):
    return  ','.join(lst)

def generate_csv_from_db_config():

    #-------- TABS -------------
    opfile = op_folder + os.sep + 'ui_tabs.csv'
    with open(opfile, 'w', encoding='utf-8') as fop:
        fop.write('id,icon,label,desc\n')
        for tb in mod_cfg.TABS:
            fop.write(lst_to_csv_str([tb['id'] ,tb['icon'], tb['label'],  '"' + tb['desc'] + '"']))
            fop.write('\n')


    #-------- SIDETABS -------------
    fprj = open(op_folder + os.sep + 'd_ref_proj.csv', 'w', encoding='utf-8')  
    fprj.write('id,label,desc,is_fav,is_current\n')    

    proj_list = []
    opfile = op_folder + os.sep + 'ui_sidetabs.csv'
    with open(opfile, 'w', encoding='utf-8') as fop:
        fop.write('id,icon,label\n')
        for tb in mod_cfg.SIDE_TABS:
            fop.write(lst_to_csv_str([tb['id'] ,tb['icon'], tb['label']]))
            fop.write('\n')

            # also write this data to projects
            fprj.write(lst_to_csv_str([tb['id'] , tb['label'], tb['label'].title(), '0', '1']))    
            fprj.write('\n')
            proj_list.append(tb['label'])
    
    #--------- TABLES -------------
    ftbl = open(op_folder + os.sep + 'sys_tables.csv', 'w', encoding='utf-8')  
    fcol = open(op_folder + os.sep + 'sys_cols.csv', 'w', encoding='utf-8')  

    ftbl.write('table_name,cols,col_types,imp_cols,search_col,url,page_function\n')
    ftbl.write('ui_tabs,"id,icon,label,desc","id,Text,Text,Text",,,,\n')
    
    ftbl.write('ui_sidetabs,"id,icon,label","id,Text,Text",,,,\n')
    
    fcol.write('table_name,col_name,col_type,display_widget,display_length_max,edit_widget\n')   

    for table in all_tables:
        print(table['nme'])
        opfile = op_folder + os.sep + 'd_' + table['nme'] + '.csv'
        with open(opfile, 'w', encoding='utf-8') as fop:
            fop.write(lst_to_csv_str(table['cols']))
            fop.write('\n')
            fop.write(get_dummy_data_by_col_types(table['nme'], table['col_types'], proj_list) + '\n')
            fop.write(get_dummy_data_by_col_types(table['nme'], table['col_types'], proj_list) + '\n')
            fop.write(get_dummy_data_by_col_types(table['nme'], table['col_types'], proj_list) + '\n')

            
            # add the table definition to master table list
            ftbl.write(lst_to_csv_str([table['nme'],
                                       '"' + ','.join(table['cols']) + '"',
                                       '"' + ','.join(table['col_types']) + '"',
                                       '"' + ','.join(table['imp_cols']) + '"',
                                       '"' + ','.join(table['search_col']) + '"',
                                       table['url'],
                                       table['page_function']
                                      ]))
            ftbl.write('\n')


            # save table definitions to master col list
            for col_num, col in enumerate(table['cols']):
                col_type = table['col_types'][col_num]
                fcol.write(lst_to_csv_str([table['nme'], col, col_type]) + ',' + get_col_spec_by_type(col_type) + '\n')


    ftbl.close()
    fcol.close()
    fprj.close()

def get_dummy_data_by_col_types(nme, col_types, proj_list):
    dummy_vals = []
    for ct in col_types:
        if ct == 'id':
            dummy_vals.append(str(random.randint(1,500)))
        elif ct == 'Text':
            dummy_vals.append(nme + ' example')
        elif ct == 'Note':
            dummy_vals.append(nme + ' note_longer_text_area')
        elif ct == 'Date':
            dummy_vals.append('2024-01-01')
        elif ct == 'Time':
            dummy_vals.append('12:00')
        elif ct == 'Checkbox':
            dummy_vals.append(random.choice(['1','0']))
        elif ct == 'List':
            dummy_vals.append(random.choice(proj_list))
        elif ct == 'Number':
            dummy_vals.append(str(random.randint(1,500)))
        elif ct == 'Color':
            dummy_vals.append(random.choice(['#FF0000', '#00FF00', '#0000FF', '#FFFF00']))
        else:
            dummy_vals.append(nme + '_sample_text')
        
    return lst_to_csv_str(dummy_vals)


def get_col_spec_by_type(col_type):
    if col_type == 'id':
        return 'Label,20,HIDDEN'    
    if col_type == 'Text':
        return 'Label,80,TEXTBOX'
    elif col_type == 'Note':
        return 'Label,200,TEXTAREA'
    elif col_type == 'Date':
        return 'Label,12,DATEPICKER'
    elif col_type == 'Time':
        return 'Label,8,TEXTBOX'
    elif col_type == 'Checkbox':
        return 'Label,10,TEXTBOX'
    elif col_type == 'List':
        return 'DROPDOWNLIST,80,DROPDOWNLIST'
    elif col_type == 'Number':
        return 'Label,80,TEXTBOX'
    elif col_type == 'Color':
        return 'Label,20,TEXTBOX'
    else:
        return 'Label,80,TEXTBOX'

def create_ref_tables():
    fref = open(op_folder + os.sep + 'sys_cat_widgets.csv', 'w', encoding='utf-8')  
    fref.write('widget, html_pre, html_post, notes\n')
    fref.write('Label, <label>, </label>,Simple text label\n')
    fref.write('TEXTBOX, <input type="text" value=",">,Single line text input box\n')
    fref.write('TEXTAREA, <textarea>, </textarea>,Multi-line text area input box\n')
    fref.write('DROPDOWNLIST, <select>, </select>,Drop down List to pick a string\n')
    fref.write('DATEPICKER, <input type="date" value=",">,Date picker input box\n')
    fref.write('DATETIMEPICKER,<input type="datetime-local" value=",">,Date and time picker input box\n')



main()        