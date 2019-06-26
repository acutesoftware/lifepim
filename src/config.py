# config.py

base_url = 'https://www.lifepim.com'    # testing, point to live site for API
base_url = '127.0.0.1:5000'             # running local (default)

toolbar_definition =  [  # [icon, name, function, comments]
    ['🏠', 'home',     'tb_home',         '🏠📰 This is the overview page'],
    ['🕐', 'calendar', 'tb_calendar', '⌚📅 🕐 Project overview showing current list of tasks being worked on'],
    ['☑',  'tasks',    'tb_tasks',    '☑✔📎🔨✘☑ ⛏ ☹     💻 💹 Tasks'],
    ['📝', 'notes',    'tb_notes',    '🗒✎📝 ✏ 🗊Team wiki page - ultra simple'], #
    ['👤', 'contacts', 'tb_contacts',     '☎👱  👤  Contacts view'],
    ['🌏️', 'places',   'tb_places',    '🌏🛰️⛟ ⌖ ⛰    💻 💹Locations - maps, people finder'],
    ['▦',  'data',     'tb_data',    '▧🗒 🗊data tables'],
    ['🏆', 'badges',   'tb_badges',     '★ ⛤ ✵ ✭ ⚜'],
    ['💲', 'money',    'tb_money',      ''],
    ['♬',  'music',    'tb_music',     '🗒 🗊music'],
    ['🖼',  'images',  'tb_images',      '🗒 🗊images'],
    ['🎮', 'apps',     'tb_apps',     '👍 👎 '],
    ['📂',  'files',   'tb_files',     '🗒 🗊images and files'],
    ['⚿',  'admin',   'tb_admin',      'passwords'],
    ['⚙',  'options', 'tb_options',     'Options for LifePIM'],
    ['⚙',  'about',   'tb_about',    'About LifePIM']
    ]

api_routes = [
    '/',
    '/notes',
    '/notes/<id>',
    '/tasks',
    '/tasks/<id>',
    '/calendar',
    '/calendar/<id>',
    '/files',
    '/files/<filename>',
    '/options',
]

def build_toolbar_file(fname):
    df = '# LifePIM Toolbar definitions for Tkinter\n'
    df += "tb_font = tkFont.Font(family='Helvetica', size=36, weight='bold')\n\n"

    fn = '# Function handling for LifePIM Toolbar clicks\n'
    fn += ''
    for ndx, tb in enumerate(toolbar_definition):
        print(tb)
        cmd = 'button_click_' + tb[2]
        df += 'btn' + str(ndx+1) + " = Button(window, text='" + tb[0] + "', "
        df += 'command=' + cmd + ')\n'
        df += 'btn' + str(ndx+1) + '.font = tb_font\n'  
        df += 'btn' + str(ndx+1) + '.grid(column=' + str(ndx) + ', row=0)\n\n'

        fn += 'def ' + cmd + '():\n'
        fn += '    """ user clicked toolbar ' + tb[1] + '"""\n'
        fn += "    print('user clicked toolbar " + tb[1] + "')\n\n"

    print(df)

    with open(fname + 'tb_def.txt', 'w') as f:
        f.write(df)
    
    with open(fname + 'tb_events.txt', 'w') as f:
        f.write(fn)
    
## to build the definitions and functions file
# run python in command line
# import config
# config.build_toolbar_file('lp')

"""
def add_toolbar_buttons(window):
    # LifePIM Toolbar definitions for Tkinter
    tb_font = font.Font(family='Helvetica', size=30, weight='bold')

    btn1 = Button(window, text='❗', command=button_click_tb_home)
    btn1.font = tb_font
    btn1.grid(column=0, row=0)

    btn2 = Button(window, text='➀', command=button_click_tb_calendar)
    btn2.font = tb_font
    btn2.grid(column=1, row=0)

    btn3 = Button(window, text='✔', command=button_click_tb_tasks)
    btn3.font = tb_font
    btn3.grid(column=2, row=0)

    btn4 = Button(window, text='✍', command=button_click_tb_notes)
    btn4.font = tb_font
    btn4.grid(column=3, row=0)

    btn5 = Button(window, text='✉', command=button_click_tb_contacts)
    btn5.font = tb_font
    btn5.grid(column=4, row=0)

    btn6 = Button(window, text='✈', command=button_click_tb_places)
    btn6.font = tb_font
    btn6.grid(column=5, row=0)

    btn7 = Button(window, text='▦', command=button_click_tb_data)
    btn7.font = tb_font
    btn7.grid(column=6, row=0)

    btn8 = Button(window, text='✮', command=button_click_tb_badges)
    btn8.font = tb_font
    btn8.grid(column=7, row=0)

    btn9 = Button(window, text='$', command=button_click_tb_money)
    btn9.font = tb_font
    btn9.grid(column=8, row=0)

    btn10 = Button(window, text='♬', command=button_click_tb_music)
    btn10.font = tb_font
    btn10.grid(column=9, row=0)

    btn11 = Button(window, text='✾', command=button_click_tb_images)
    btn11.font = tb_font
    btn11.grid(column=10, row=0)

    btn12 = Button(window, text='☑', command=button_click_tb_apps)
    btn12.font = tb_font
    btn12.grid(column=11, row=0)

    btn13 = Button(window, text='', command=button_click_tb_files)
    btn13.font = tb_font
    btn13.grid(column=12, row=0)

    btn14 = Button(window, text='✋', command=button_click_tb_admin)
    btn14.font = tb_font
    btn14.grid(column=13, row=0)

    btn15 = Button(window, text='⚙', command=button_click_tb_options)
    btn15.font = tb_font
    btn15.grid(column=14, row=0)

    btn16 = Button(window, text='?', command=button_click_tb_about)
    btn16.font = tb_font
    btn16.grid(column=15, row=0)

"""