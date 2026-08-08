# LifePIM Apps — Launchables and Code Management

## 1. Intent and Design Philosophy

The LifePIM **Apps** area should not simply be a list of installed applications.

Its purpose is to provide a central place for managing **things that can be launched or opened to perform work**.

This includes traditional applications such as:

* Blender
* VS Code
* Android Studio
* GIMP
* DB Browser for SQLite

but should also include:

* development projects
* source-code repositories
* Python scripts
* PowerShell scripts
* batch files
* SQL scripts
* executables
* command-line tools
* websites
* web applications
* database connections
* SSH connections
* development environments
* build commands
* utility scripts

The useful abstraction is therefore:

> **An App is a launchable LifePIM object.**

LifePIM should manage and organise these objects, but it should **not attempt to become an IDE, compiler or source-code repository**.

Actual source files remain in the filesystem or Git repository. Existing specialist applications continue doing the work:

* VS Code edits source
* Blender edits `.blend` files
* Visual Studio builds applications
* Android Studio builds Android projects
* Python executes scripts
* browsers open web applications
* terminals execute shell commands

LifePIM acts as the layer above these tools.

It answers questions such as:

* What applications do I use for Design?
* What development projects am I currently working on?
* What Python utilities have I written?
* What program opens this project?
* How do I build or run this application?
* Where is its repository?
* What documentation, notes or tasks relate to it?
* What tools belong to this Area or Project?

The Apps screen should therefore behave partly like a **personal application launcher**, partly like a **software/project catalogue**, and partly like a **command centre**.

---

# 2. Relationship to Other LifePIM Content

Apps should complement existing LifePIM content rather than duplicate it.

### Apps

Represents applications and launchable software objects.

Examples:

* Blender
* LifePIM Desktop
* LifePIM Pocket
* LifePIM Logger
* `duncansProdApp.py`
* database cleanup script
* SQLite Browser
* Fabric portal

### Notes

Used for informal information about development work.

Examples:

* implementation ideas
* debugging notes
* code experiments
* architecture thoughts
* TODO notes

Source code itself should normally **not** be stored as a Note.

### How

Used for structured documentation and procedures.

Examples:

* How the Logger pipeline works
* How to build LifePIM Pocket
* How to deploy LifePIM Desktop
* Database schema documentation
* Development environment setup

### Files

Represents files and folders themselves.

Examples:

* source-code directory
* compiled executable
* installer
* database file
* project assets

Apps can reference these Files/Folders.

### Tasks / Goals

Used for work that needs to be done.

Examples:

* fix Logger sync bug
* upgrade Android SDK
* rebuild database loader
* release LifePIM Pocket

An App or development project may have related tasks.

---

# 3. Apps Are Not Restricted to Executables

The system should avoid assuming that an App is an `.exe`.

Example App records could include:

| Name            | Kind        | Launch Behaviour                 |
| --------------- | ----------- | -------------------------------- |
| Blender         | Application | Launch `blender.exe`             |
| LifePIM Desktop | Project     | Open source folder/editor        |
| LifePIM Logger  | Project     | Open Android Studio              |
| Logger Rebuild  | Script      | Execute Python                   |
| Backup NAS      | Script      | Execute PowerShell               |
| Fabric          | Web App     | Open URL                         |
| SQLite Browser  | Application | Launch executable                |
| LifePIM DB      | Database    | Open database in configured tool |
| Treebeard       | SSH         | Open terminal/SSH connection     |
| Cleanup SQL     | SQL Script  | Open SQL file/editor             |

The Apps system should therefore use a flexible **App Kind** rather than application-specific behaviour.

Initial suggested kinds:

* Application
* Development Project
* Repository
* Script
* Executable
* Command
* Web App
* Website
* Database
* SQL Script
* Development Environment
* Service
* Connection
* Utility
* Other

These should use LifePIM's existing content-kind architecture where practical rather than hard-coded behaviour.

---

# 4. Areas Are the Primary Navigation Model

Apps should primarily be organised according to **what the user uses them for**, rather than according to technical type.

For example:

### Design

* Blender
* GIMP
* Inkscape
* PureRef

### Development

* VS Code
* Cursor
* Android Studio
* GitHub Desktop
* DB Browser for SQLite
* LifePIM Desktop
* Logger database loader

### Media

* VLC
* Audacity
* HandBrake

### Data

* Fabric
* SSMS
* SQLite Browser
* database utilities

Apps should support **multiple Areas**.

For example:

Blender:

* Design
* 3D
* LifePIM

VS Code:

* Development
* LifePIM
* AI
* Work

An App must therefore not have a single `area_id` field if LifePIM already supports generic many-to-many Area relationships.

Use the existing Area/object association mechanism.

---

# 5. Collections

Apps should use the existing generic LifePIM Collections engine.

Do not implement a separate Apps-specific collection system.

Example collections might include:

* Daily Tools
* Development Tools
* Current Projects
* Utilities
* Database Tools
* AI Tools
* Media Tools
* Server Tools

A single App may appear in multiple collections.

Collections provide deliberate curated groupings, while Areas provide broader organisational context.

---

# 6. Apps Screen Layout

Use the standard LifePIM multi-pane design where practical.

Suggested layout:

```text
+---------------------------------------------------------------+
| Apps                                      Search...      + Add |
+-------------------+-------------------------------------------+
|                   |                                           |
| FILTERS           |              APP VIEW                     |
|                   |                                           |
| Areas             |   Blender                                 |
| Development       |   VS Code                                 |
| Design            |   LifePIM Desktop                         |
| Media             |   Logger Database Loader                  |
| Data              |                                           |
| ...               |                                           |
|                   |                                           |
| Collections       |                                           |
| Favorites         |                                           |
| Current Projects  |                                           |
| Daily             |                                           |
|                   |                                           |
+-------------------+-----------------------------+-------------+
|                                                 | Inspector   |
+-------------------------------------------------+-------------+
```

Exact positioning should follow existing LifePIM interface conventions rather than forcing a completely new UI pattern.

---

# 7. Primary Filter: Area

The left-hand navigation should prominently show Areas.

Example:

```text
AREAS

All Apps

Development
Design
3D
Media
Data
Home
Finance
Work
LifePIM
AI
```

Selecting an Area filters the App list.

The Area list should ideally show item counts if existing LifePIM UI conventions support this.

Example:

```text
Development     23
Design          11
Media            8
```

Apps belonging to multiple Areas appear in every applicable Area.

---

# 8. Secondary Navigation / Saved Views

Across the top of the Apps view, provide simple predefined views.

Suggested initial tabs:

```text
All | Favorites | Recent | Projects | Scripts | Applications
```

These should conceptually behave as filters rather than entirely separate systems.

### All

All Apps matching the current Area/Collection filters.

### Favorites

Apps marked as favourite.

### Recent

Apps recently launched/opened through LifePIM.

### Projects

Development Project / Repository type records.

### Scripts

Scripts, commands and SQL utilities.

### Applications

Traditional installed applications/executables.

Avoid adding dozens of permanent tabs.

Most classification should happen through filtering rather than new screens.

---

# 9. Optional Kind and Tag Filters

Additional filtering should be available without dominating the UI.

Example:

```text
Kind
  Application
  Project
  Script
  Web App

Tags
  Python
  SQL
  Android
  3D
  Database
```

Tags should use LifePIM's generic tagging system if one exists.

These filters can initially live in an expandable filter panel.

---

# 10. Search

Apps should have fast free-text search.

Search should include at minimum:

* title
* description
* executable/file name
* path
* command
* repository
* URL
* tags

For example searching:

```text
python
```

might return:

* Logger Loader
* File Indexer
* Backup Utility
* Python
* VS Code

Search should combine with the currently selected Area or saved view.

---

# 11. Display Modes

Implement at least two views initially.

## Launcher / Grid View

Designed for quickly launching tools.

Example:

```text
[ Blender ]   [ VS Code ]   [ LifePIM ]

[ Logger ]    [ SQLite ]    [ Fabric ]
```

Each item should show:

* icon
* name
* optional short subtitle

Double-click or an obvious launch action executes the default action.

## Detail / List View

Designed for managing Apps.

Suggested columns:

```text
Name
Kind
Areas
Location / Command
Last Used
Favorite
```

Do not make the table excessively wide.

Detailed information belongs in the Inspector.

Future views could include:

* grouped by Area
* grouped by Kind
* grouped by language
* grouped by project

These are not necessary for the initial implementation if they complicate the first version.

---

# 12. App Inspector

Selecting an App should display an Inspector/detail panel.

Example:

```text
LifePIM Desktop

Kind
Development Project

Areas
Development
LifePIM

Repository
C:\Projects\LifePIM

Default Action
Open in VS Code

Actions
Open
Run
Build
Test

Language
Python / JavaScript

Last Used
Today

Collections
Current Projects
Daily Tools

Related
Notes
How-To
Tasks
Files
```

The Inspector should make Apps feel connected to the rest of LifePIM.

---

# 13. App Actions

A major part of the Apps model should be **Actions**.

An App can have one or more actions.

Examples:

### Blender

```text
Open
```

### LifePIM Desktop

```text
Open Project
Run
Build
Test
Open Repository
```

### Python Logger Loader

```text
Run
Open Source
Open Log Folder
```

### LifePIM Pocket

```text
Open Android Studio
Build
Run Emulator
Open Repository
```

Each App has one **default action**.

Double-clicking the App executes the default action.

Other actions are available through:

* Inspector
* context menu
* action button/dropdown

---

# 14. Action Data Model

Actions should preferably use a child table rather than adding fields such as:

```text
run_command
build_command
test_command
editor_command
```

to the main App table.

Conceptually:

```text
lp_app
    app_id
    title
    kind
    description
    icon
    favorite
    ...

lp_app_action
    app_action_id
    app_id
    action_name
    action_type
    command
    working_directory
    arguments
    sort_order
    is_default
```

Possible action names:

* Open
* Edit
* Run
* Build
* Debug
* Test
* Deploy
* Browse
* Connect
* Open Folder
* Open Repository

The underlying implementation should remain generic.

An action essentially means:

> Perform this launch operation for this App.

---

# 15. Action Types

Suggested action types:

```text
EXECUTABLE
COMMAND
OPEN_FILE
OPEN_FOLDER
OPEN_URL
SYSTEM_DEFAULT
```

Potential future types:

```text
SSH
SQL
CUSTOM_HANDLER
```

Avoid implementing complicated specialised execution frameworks in Version 1.

Most things can initially resolve to:

* start executable
* execute command
* open file/folder
* open URL

---

# 16. Command Safety

LifePIM must not automatically execute commands simply because an App record exists.

Commands run only following explicit user interaction.

For Version 1:

* actions are locally defined
* no automatic downloading/execution of remote commands
* display the configured command in the Inspector/edit screen
* support working directory
* support command arguments

Use normal OS process execution practices.

---

# 17. Development Projects

Development projects are an important App kind.

For example:

```text
LifePIM Desktop

Kind:
Development Project

Path:
C:\Projects\LifePIM

Repository:
https://github...

Editor:
VS Code

Actions:
Open Project
Run
Build
Test
Open Repository
```

LifePIM should not store or parse the project's entire source tree as part of the App record.

The project record represents the **software project**, while Files continues managing filesystem objects.

---

# 18. Code Files

Individual source-code files should normally remain Files.

For example:

```text
C:\Projects\LifePIM\src\logger\loader.py
```

does not automatically need an App database record.

However, a particularly useful standalone script can explicitly be promoted to an App.

For example:

```text
duncansProdApp.py
```

may have:

```text
Kind:
Script

Language:
Python

Path:
D:\scripts\duncansProdApp.py

Default action:
Run

Other action:
Edit
```

This distinction prevents Apps becoming a catalogue of millions of source files.

---

# 19. Metadata

Suggested core App metadata:

```text
app_id
title
description
kind/content_kind
icon
favorite
enabled
created_date
modified_date
last_used_date
usage_count
```

Useful optional metadata:

```text
path
repository_url
website_url
language
version
comments
```

However, avoid adding highly specialised fields unless they are actually required.

Where possible use:

* generic object relationships
* tags
* Collections
* Areas
* child Actions

rather than making `lp_app` extremely wide.

---

# 20. Icons

Apps should support icons because visual recognition is particularly valuable in launcher mode.

Possible icon sources:

* manually selected image
* executable icon
* generated/default icon by Kind

Version 1 can use:

1. manually configured icon if supplied
2. generic icon based on App Kind otherwise

Automatic executable icon extraction can be added later if inconvenient for the first implementation.

---

# 21. Favorite and Recent Apps

Each App can be marked Favorite.

Apps launched through LifePIM should update:

```text
last_used_date
usage_count
```

This supports:

```text
Favorites
Recent
```

Recent should be ordered descending by `last_used_date`.

Do not attempt to monitor global OS application usage in this feature.

LifePIM Logger may separately collect actual computer usage data later.

---

# 22. Editing Apps

Provide a straightforward Add/Edit App form.

Core fields:

```text
Name
Kind
Description
Areas
Collections
Tags
Icon
Favorite
```

Launch configuration:

```text
Actions
```

Actions should be editable as a small child list.

Example:

```text
ACTION          TYPE          TARGET
Open Project    Folder        C:\Projects\LifePIM
Run             Command       npm run dev
Build           Command       npm run build
Repository      URL           https://...
```

Allow:

* Add
* Edit
* Delete
* reorder
* mark Default

The editor should be fast and practical rather than an oversized enterprise configuration screen.

---

# 23. Example Initial Records

Populate several demonstration records if useful for development/testing.

### Blender

```text
Kind: Application
Areas: Design, 3D

Action:
Open
EXECUTABLE
C:\Program Files\Blender Foundation\Blender\blender.exe
```

### VS Code

```text
Kind: Application
Areas: Development

Action:
Open
EXECUTABLE
code
```

### LifePIM Desktop

```text
Kind: Development Project
Areas: Development, LifePIM

Actions:
Open Project
Run
Build
```

### duncansProdApp.py

```text
Kind: Script
Areas: Development

Language:
Python

Actions:
Run
Edit
```

### Fabric

```text
Kind: Web App
Areas: Data, Work

Action:
Open
URL
```

These are examples only; do not hard-code them as special cases.

---

# 24. Reuse Existing LifePIM Infrastructure

This implementation should integrate with existing LifePIM architecture.

In particular:

* use existing Areas
* use existing Projects where appropriate
* use existing Collections engine
* use existing generic object relationships
* use existing content-kind architecture
* use existing tagging if available
* follow existing UI component/layout conventions

Do not recreate generic functionality solely for Apps.

The Apps adapter should add only the domain-specific data required for Apps and launch actions.

---

# 25. Apps and LifePIM Projects

Be careful not to confuse:

**LifePIM Projects**

with:

**Development Project App Kind**

A LifePIM Project represents a personal/work project such as:

```text
Build LifePIM Pocket
Renovate House
Rome Holiday
```

A Development Project in Apps represents a software/code project such as:

```text
LifePIM Desktop source repository
```

They can be related.

For example:

```text
LifePIM Project:
Improve Logger Processing

Related Apps:
LifePIM Desktop
LifePIM Logger
VS Code
DB Browser
```

Do not merge these concepts.

---

# 26. Version 1 Scope

Implement the first usable Apps system with:

1. Apps list/database records.
2. App Kind.
3. Areas — including multiple Areas per App.
4. Existing Collections integration.
5. Favorite flag.
6. Search.
7. Grid/Launcher view.
8. Details/List view.
9. Inspector.
10. Multiple launch Actions.
11. Default Action.
12. Open executable.
13. Execute command.
14. Open file.
15. Open folder.
16. Open URL.
17. Recent Apps based on launches performed through LifePIM.
18. Add/Edit App interface.
19. Top views:

* All
* Favorites
* Recent
* Projects
* Scripts
* Applications

Do not attempt to implement:

* an IDE
* source control
* compiler functionality
* source-code indexing
* syntax highlighting
* source file editing
* operating-system application monitoring
* automatic software discovery
* package management

Those may integrate with Apps later but are outside this implementation.

---

# 27. Future Possibilities

The architecture should leave room for later capabilities such as:

* automatic installed application discovery
* executable icon extraction
* Git repository status
* GitHub integration
* build history
* test results
* environment management
* terminal profiles
* SSH connections
* database launch profiles
* recent source projects
* executable/process discovery from Logger data
* suggesting commonly used applications
* "Open With" relationships between Files and Apps
* application usage statistics
* application dependencies
* workflows consisting of several Apps/actions

These are future enhancements, not Version 1 requirements.

---

# 28. Core UX Goal

The Apps screen should make questions like this extremely easy:

> "I'm doing Design work — show me the things I use."

The user selects:

```text
Apps > Design
```

and immediately sees:

```text
Blender
GIMP
Inkscape
PureRef
```

Likewise:

```text
Apps > Development
```

might show:

```text
VS Code
Android Studio
LifePIM Desktop
LifePIM Logger
DB Browser
Logger Loader
duncansProdApp.py
```

The distinction between an executable, project and script should matter when editing the object, but should **not get in the way of finding and launching it**.

That is the central design principle for the Apps feature.
