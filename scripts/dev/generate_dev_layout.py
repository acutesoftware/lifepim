# generate_dev_layout.py
# written by Duncan Murray 15/9/2025

"""
samples from config.py below: 

SIDE_TABS = [  # Tabs down left side of LifePIM - any project goes into one of these groups
    { 'icon': '*', 'id': 'any', 'label': 'All Projects'},
    { 'icon': '', 'id': 'spacer', 'label': 'PERS________'}, 
    { 'icon': '💊', 'id': 'health', 'label': 'Health'}, 
    { 'icon': '👪', 'id': 'family', 'label': 'Family'}, 
    { 'icon': '🏚️', 'id': 'house', 'label': 'House'}, 
    { 'icon': '🌴', 'id': 'garden', 'label': 'Garden'}, 
    { 'icon': '🚗', 'id': 'car', 'label': 'Car'}, 
    { 'icon': '', 'id': 'fun', 'label': 'FUN________'}, 
    { 'icon': '🎉', 'id': 'fun/events', 'label': 'Events'},  # note that top tabs separate movies,
    { 'icon': '🕹️', 'id': 'fun/games', 'label': 'Games'}, 
    { 'icon': '🍕', 'id': 'fun/food', 'label': 'Food'}, 
]

TABS = [  #Tabs across top of LifePIM
    { 'icon': '🏠', 'id': 'home', 'label': 'Overview', 'desc': 'Overview Dashboard'},
    { 'icon': '🕐', 'id': 'calendar', 'label': 'Cal', 'desc': 'Calendar, Appointments, Events, Reminders (WHEN)'},
    { 'icon': '🏆', 'id': 'goals', 'label': 'Goals', 'desc': 'Goals and Achievements (WHY)'},
    { 'icon': '📝', 'id': 'tasks', 'label': 'Tasks', 'desc': 'Tasks (actual list of things to do)'},
    { 'icon': '📘', 'id': 'how', 'label': 'How', 'desc': 'Blueprints, Task Templates, Processes, Jobs (HOW)'},
    { 'icon': '📔', 'id': 'notes', 'label': 'Notes', 'desc': 'Notes'},
    { 'icon': '▦', 'id': 'data', 'label': 'Data', 'desc': 'Data' },
    { 'icon': '📂', 'id': 'files', 'label': 'Files', 'desc': 'Files'},
    { 'icon': '🖼️', 'id': 'media', 'label': 'Media', 'desc': 'Images / Videos / 2D things'},
    { 'icon': '🎵', 'id': 'audio', 'label': 'Audio', 'desc': 'Music / Podcasts / Sound Effects'},
    { 'icon': '🧱', 'id': '3d', 'label': '3D',  'desc': 'Objects / 3D / Things'},
    { 'icon': '💲', 'id': 'money', 'label': 'Money', 'desc': 'Money'},
    { 'icon': '👤', 'id': 'contacts', 'label': 'People', 'desc': 'Contacts (WHO)'},
    { 'icon': '🌏', 'id': 'places', 'label': 'Places', 'desc': 'Places (WHERE - real life, URL or virt location)'},
    
    #{ 'icon': '📰', 'id': 'news', 'label': 'News', 'desc': 'News, reddit, twitter, RSS feeds'},
    #{ 'icon': '📩', 'id': 'comms', 'label': 'Comms', 'desc' : 'Mail, Chat, Social, Messages  📱📲'},
    #{ 'icon': '💿', 'id': 'media', 'label': 'Media', 'desc': 'Images, Audio, Video'},
    { 'icon': '🎮', 'id': 'apps', 'label': 'Apps', 'desc': 'Apps'},
    #{ 'icon': '💻', 'id': 'etl', 'label': 'ETL', 'desc': 'ETL'},
    # { 'icon': '📜', 'id': 'logs', 'label': 'Logs', 'desc': 'Journal / Logs'},
    #{ 'icon': '⚙', 'id': 'admin', 'label': 'Admin', 'desc': 'Admin'},
    { 'icon': '🤖', 'id': 'agent', 'label': 'Agent', 'desc': 'Agent'},
]


sub_menus = [
    {'root':'notes', 'name':'Ideas'},
    {'root':'notes', 'name':'Meeting Notes'},
    {'root':'notes', 'name':'Project Info'},
    {'root':'notes', 'name':'Research'},
    {'root':'tasks', 'name':'Today'},
    {'root':'tasks', 'name':'This Week'},
    {'root':'tasks', 'name':'This Month'},
    {'root':'tasks', 'name':'Completed'},
    {'root':'calendar', 'name':'Appointments'},
    {'root':'calendar', 'name':'Events'},
    {'root':'calendar', 'name':'Logs'},
    {'root':'data', 'name':'Databases'},
    {'root':'data', 'name':'Spreadsheets'},
    {'root':'data', 'name':'Checklists'},
    ]

"""
from src import config as mod_cfg
from pprint import pprint

def main():
    show_layout()
    render_layout('test.html')

    #print(mod_cfg.filters)

    spec_cal = generate_table_spec("calendar", "date DATE, time TEXT 4, event_summary TEXT 200, event_type TEXT 200, details TEXT BLOB")
    spec_note = generate_table_spec("note", "date DATE, time TEXT 4, note_summary TEXT 2000, note_type TEXT 200, details TEXT BLOB")
        
    """
    pprint(spec_cal,sort_dicts=False)
    spec_cal_view_list = generate_view_spec(spec_cal, 'LIST', ['date', 'time', 'event_summary'])
    pprint(spec_cal_view_list,sort_dicts=False)

    spec_note_view_card = generate_view_spec(spec_note, 'CARD', ['details'])
    pprint(spec_note_view_card,sort_dicts=False)
    """

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

def render_layout(html_file="lifepim.html"):
    """Render compact static HTML layout for LifePIM top and side tabs."""

    # --- HTML content ---
    html = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='utf-8'/>",
        "  <title>LifePIM UI</title>",
        "  <link rel='stylesheet' href=""lifepim_test.css"">",
        "</head>",
        "<body>",
        "",
        "  ",
        "  <div class='top-nav-container'>",  # "    <div class='top-tabs'>"
    ]

    # render top tabs
    for t in mod_cfg.TABS:
        tab_id = t['id']
        desc = t.get("desc", "")
        
        # Find sub-menus for this tab
        sub_items = [s for s in mod_cfg.sub_menus if s['root'] == tab_id]
        print('sub items for menu = ' + str(sub_items))
       
        if not sub_items:
            # No dropdown, just the plain link
            html.append(
                f"      <a href='#{tab_id}' title='{desc}' class='top-tab-link'><span class='icon'>{t['icon']}</span>{t['label']}</a>"
            )
        else:
            # This tab HAS a dropdown

            html.append("      <div class='top-tab-item'>")
            # Add the main link
            html.append(
                f"        <a href='#{tab_id}' title='{desc}' class='top-tab-link'><span class='icon'>{t['icon']}</span>{t['label']}</a>"
            )
            
            # Add the dropdown menu
            html.append("        <div class='dropdown-menu'>")
            for sub in sub_items:
                sub_name = sub['name']
                print(' sub = ' + str(sub))
                
                # Create a simple ID from the name (e.g., "Meeting Notes" -> "meeting_notes")
                sub_id = sub['fn']# sub_name.replace(' ', '_').lower()
                # Route to [TAB]_[SUBTAB]  f"#{tab_id}_{sub_id}"
                href = f"?tab={sub['fn']}?proj=any"

                print('href = ' + href )
                html.append(f"          <a href='{href}'>{sub_name}</a>")
            
            html.append("        </div>") # close dropdown-menu
            html.append("      </div>") # close top-tab-item

    html.append("    </div>") # close .top-tabs
    html.append("  </div>")   # # side tabs
    html.append("\n  ")
    html.append("  <div class='side-tabs'>")

    for s in mod_cfg.SIDE_TABS:
        desc = s.get("label", "")
        href = f"?tab=home?proj={s['id']}"

        # is this a side spacer?
        if desc.endswith("___") or s['icon'] == '':
            html.append(f"    <a href='{href}' title='{desc}'><B>{s['label']}</B></a>")
        else:
            html.append(f"    <a href='{href}' title='{desc}'><span class='icon'>{s['icon']}</span>{s['label']}</a>")

    html.append("  </div>")

    # placeholder for main content
    html.append("\n  <div class='content'>Select a tab to view content.</div>")
    html.append("</body></html>")

    # --- Write file ---
    with open(html_file, "w", encoding="utf-8") as f:
        f.write("\n".join(html))

    print(f"✅ Wrote: {html_file}")

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