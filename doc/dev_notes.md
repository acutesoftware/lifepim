## Developer Notes for LifePIM Desktop



## Layout

```
    lifepim/
    ├── app.py
    ├── static/lifepim.css
    ├── templates/layout.html
    ├── common/
    │   ├── utils.py
    │   ├── data.py
    └── modules/
        └── notes/
            ├── __init__.py
            ├── routes.py
            └── templates/
                ├── notes_list.html
                ├── note_view.html
                └── note_edit.html
```


Notes for developers.

## Developing locally on your PC

### Setup local environment

1. make a new blank directory

2. setup a git repository

```
git init lifepim
```

3. get the source code

```
git pull https://github.com/acutesoftware/lifepim.git
```

4. get additional libraries

```
pip install pycalendar
```

### Coding standards

1. PEP8
2. no calls to external API's from any core code
3. no cryptic looking code

### Uploading changes

make the changes locally, including tests then commit

NOTE - steps below are for master branch only (Duncans notes - fix this for merging)

```
git add [yourfile].py
git commit -m "useful message"
git remote add origin https://github.com/acutesoftware/lifepim.git
git push --set-upstream origin master
```

## How it works

### Design Overview

desktop.py - main program

/interfaces - folder for interfacing to systems, databases, files

/views - folder for each of the main areas (each toolbar - notes, tasks, apps has a folder)

When the user clicks the toolbar or chooses a different view (notes, tasks, etc) the "build_screen" function is called 
which needs to be in each of the /views/<area_folder>/area.py 

def build_screen(root):
    console_frame = Frame(root, bg='white', width=850, height=250, pady=1)
    console_frame.grid(row=0, column=0, sticky="nesw")
    print('building screen_notes...')

    txt = 'welcome to notes\n'
    console_label = Label(root, text=txt, bg='white', foreground='blue', justify=LEFT)
    console_label.grid(row=0, column=0)
    console_entry = Entry(root,  bg='gray12', foreground='green')
    console_entry.grid(row=1, column=0, sticky="ew")




### User Interface

Toolbar - swoitches between main modes

Folders - filters data based on project. Initially this was the folder string in Lifepim.com but on the desktop version it is the subfolder

Top Left
- Calendar

Mid Left
- 

Bottom Left

Mid Screen
- this is the main work area, depending on the mode
Notes = text editor
Tasks = task details
Music = list of music
Apps = list of apps

Right = not sure, probably auto contents of notes, or sub tasks or properties details



### Views folder

The views folder contains a subfolder

```

    from views.home import home as home
    from views.calendar import calendar as calendar
    from views.tasks import tasks as tasks
    from views.notes import notes as notes
    from views.contacts import contacts as contacts
    from views.places import places as places
    from views.data import data as mod_data
    from views.badges import badges as badges
    from views.money import money as money
    from views.music import music as mod_music
    from views.images import images as images
    from views.apps import apps as apps
    from views.files import files as mod_files
    from views.admin import admin as admin
    from views.options import options as options
    from views.about import about as about

```


### Program Execution Steps

Main module loads and calls LifePIM_GUI(QMainWindow)

        # global references for Widgets created here (across all focus modes - may not be used)
        # create the components that might be used in the layout
        self.load_settings_data()
        self.build_gui()
        # load modules used in the application
        # populate user data for first time (from cache)
        

