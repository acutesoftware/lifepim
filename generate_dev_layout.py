# generate_dev_layout.py
# written by Duncan Murray 15/9/2025

from src import config as mod_cfg
from pprint import pprint

def main():
    show_layout()
    render_layout('test.html')
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



def render_layout(html_file="lifepim.html", css_file="lifepim.css"):
    """Render compact static HTML layout for LifePIM top and side tabs."""

    # --- CSS stored separately ---
    css = """
/* LifePIM Layout - clean, compact, modern */
body {
    margin: 0;
    font-family: system-ui, sans-serif;
    background-color: #fafafa;
}

/* --- TOP TABS --- */
.top-tabs {
    display: flex;
    background: #2f3542;
    overflow-x: auto;
    white-space: nowrap;
    border-bottom: 1px solid #444;
}
.top-tabs a {
    display: inline-flex;
    align-items: center;
    color: #eee;
    text-decoration: none;
    padding: 6px 10px;
    font-size: 13px;
}
.top-tabs a:hover {
    background: #444;
    color: #fff;
}
.top-tabs span.icon {
    margin-right: 6px;
}

/* --- LHS SIDE TABS --- */
.side-tabs {
    position: fixed;
    top: 36px;
    bottom: 0;
    left: 0;
    width: 130px;
    background: #f3f3f3;
    border-right: 1px solid #ccc;
    overflow-y: auto;
    padding: 4px 0;
}
.side-tabs a {
    display: flex;
    align-items: center;
    color: #333;
    text-decoration: none;
    font-size: 13px;
    padding: 4px 6px;
    border-radius: 4px;
    margin: 2px 4px;
}
.side-tabs a:hover {
    background: #ddd;
}
.side-tabs span.icon {
    margin-right: 6px;
}

/* --- CONTENT AREA --- */
.content {
    margin-left: 140px;
    margin-top: 40px;
    padding: 10px;
    font-size: 14px;
}
"""

    # --- HTML content ---
    html = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='utf-8'/>",
        "  <title>LifePIM UI</title>",
        f"  <link rel='stylesheet' href='{css_file}'/>",
        "</head>",
        "<body>",
        "",
        "  <!-- Top Tabs -->",
        "  <div class='top-tabs'>"
    ]

    # render top tabs
    for t in mod_cfg.TABS:
        desc = t.get("desc", "")
        html.append(
            f"    <a href='#{t['id']}' title='{desc}'><span class='icon'>{t['icon']}</span>{t['label']}</a>"
        )

    html.append("  </div>")

    # side tabs
    html.append("\n  <!-- Side Tabs -->")
    html.append("  <div class='side-tabs'>")

    for s in mod_cfg.SIDE_TABS:
        desc = s.get("label", "")
        html.append(
            f"    <a href='#{s['id']}' title='{desc}'><span class='icon'>{s['icon']}</span>{s['label']}</a>"
        )

    html.append("  </div>")

    # placeholder for main content
    html.append("\n  <div class='content'>Select a tab to view content.</div>")
    html.append("</body></html>")

    # --- Write files ---
    with open(html_file, "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    with open(css_file, "w", encoding="utf-8") as f:
        f.write(css)

    print(f"✅ Wrote: {html_file} and {css_file}")




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