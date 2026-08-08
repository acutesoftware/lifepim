# LifePIM Apps — Import Apps Functionality

## 1. Intent

Add an **Import** function to the LifePIM Apps area.

The purpose of Import is to quickly populate the Apps catalogue using things that already exist on the computer, without hard-coding sample records or running scripts that directly inject arbitrary data into the LifePIM database.

The Import workflow should be:

```text
Choose import source
        ↓
Scan computer/source
        ↓
Display discovered candidates
        ↓
User reviews and selects items
        ↓
User optionally changes Area / Kind
        ↓
Import Selected
        ↓
Create normal LifePIM App records
```

Import must be an explicit user-driven operation.

Scanning must **not automatically create App records**.

This is important because the Apps catalogue should remain intentional and curated rather than becoming an inventory of everything installed on the computer.

Version 1 should support three import methods:

1. Dev Folders
2. Taskbar Applications
3. Desktop Applications

These three importers should use a common scanning/import framework so additional import sources can be added later.

---

# 2. Main UX

Add an Import action to the Apps screen.

For example:

```text
Apps

[ + Add App ]   [ Import ]
```

Selecting Import opens:

```text
Apps > Import
```

The Import screen should contain three source tabs or selectors:

```text
Dev Folders | Taskbar | Desktop
```

Each importer provides candidates to the same reusable candidate-review component.

The user should always be able to inspect what will be imported before records are created.

---

# 3. Common Import Workflow

All import types should follow this pattern:

```text
Source configuration
        ↓
Scan
        ↓
Candidate list
        ↓
Select / deselect
        ↓
Optional metadata adjustment
        ↓
Import Selected
```

Example:

```text
Apps > Import > Dev Folders

Root Folder:
D:\Development

Default Area:
Development

Default Kind:
Development Project

[ Scan ]

---------------------------------------------------------------

   Status   Name          Kind                 Area
[x] NEW      LifePIM      Development Project  Development
[x] NEW      Aggie        Development Project  Development
[ ] NEW      TestStuff    Development Project  Development
    EXISTS   OldProject   Development Project  Development

---------------------------------------------------------------

3 new items found
2 selected

[ Select All ] [ Select None ]       [ Import Selected ]
```

The candidate list should not itself write to `lp_app`.

Only `Import Selected` should create records.

---

# 4. Common Candidate Model

Create a reusable application-level candidate structure.

This does not necessarily need to be persisted to the database.

For Version 1, candidates can exist in memory while the Import screen is open.

Conceptually:

```text
AppImportCandidate

candidate_id
source_type
name
kind
area_id
target
arguments
working_directory
icon
source_path
status
selected
metadata
```

Suggested statuses:

```text
NEW
EXISTS
INVALID
```

Potential future status:

```text
CHANGED
```

Do not over-engineer Version 1 around future functionality.

---

# 5. Do Not Create Persistent Test/Seed Data

This feature replaces the need for scripts such as `LOAD_TEST.py` to populate Apps.

Do not:

* create arbitrary test Apps on startup
* inject sample Apps during migrations
* mix test data with real user data
* require a cleanup script after testing

Database migrations should create schema only.

If test data is required for automated tests, it should live entirely inside the test environment/database.

The normal LifePIM database must only receive imported Apps after an explicit user action.

---

# 6. Import Source 1 — Dev Folders

## Purpose

Allow the user to import software/code projects from configured development directories.

Example:

```text
D:\Development
```

may contain:

```text
LifePIM
LifePIM-Pocket
LifePIM-Logger
Aggie
FileIndexer
OldExperiments
```

The importer should present each appropriate child folder as a candidate App.

---

# 7. Dev Folder Scan Behaviour

The user chooses:

```text
Root Folder
Default Area
Default Kind
```

Example:

```text
Root Folder:
D:\Development

Default Area:
Development

Default Kind:
Development Project
```

Clicking:

```text
[ Scan ]
```

should inspect the root.

Version 1 should scan **immediate child folders only**.

Example:

```text
D:\Development\LifePIM
D:\Development\Aggie
D:\Development\FileIndexer
```

Do not recursively turn every source-code directory into an App.

For example, these should NOT become separate Apps:

```text
D:\Development\LifePIM\src
D:\Development\LifePIM\src\logger
D:\Development\LifePIM\node_modules
```

---

# 8. Dev Folder Candidates

Each child folder should initially produce:

```text
Kind:
Development Project

Default Action:
Open Folder
```

Example candidate:

```text
Name:
LifePIM

Target:
D:\Development\LifePIM

Kind:
Development Project

Area:
Development
```

The project does not need an executable or launch command.

Opening its project folder is sufficient for the initial imported App.

Additional actions can be added later through the normal Apps editor.

---

# 9. Dev Project Detection

Version 1 may collect simple project hints while scanning.

For example detect the presence of:

```text
.git
package.json
pyproject.toml
requirements.txt
*.sln
*.csproj
build.gradle
settings.gradle
Cargo.toml
```

These hints may be stored in candidate metadata or used to improve the displayed description.

Example:

```text
LifePIM
Git repository / Node project
```

Do not build complicated language or framework detection yet.

The existence of these files should not be required for import.

A plain folder can still represent a Development Project.

---

# 10. Git Repository Detection

If:

```text
<project>\.git
```

exists, mark the candidate as a detected Git repository.

If straightforward, optionally determine the Git remote URL.

Example:

```text
Repository:
https://github.com/...
```

This is useful metadata, but Git remote detection should not block importing the project if it fails.

Do not add Git operations or source-control functionality as part of this feature.

---

# 11. Dev Folder Default Action

Imported Dev Folder Apps should receive an action equivalent to:

```text
Open Folder
```

using the Apps action architecture already implemented/planned.

Example:

```text
Action Name:
Open Folder

Action Type:
OPEN_FOLDER

Target:
D:\Development\LifePIM

Is Default:
Y
```

---

# 12. Import Source 2 — Taskbar Applications

## Purpose

Import applications the user has deliberately pinned to the Windows Taskbar.

This is useful because pinned applications generally represent tools the user actually uses rather than every application installed on the machine.

The importer should scan Windows Taskbar pinned shortcuts where technically accessible.

---

# 13. Taskbar Scan

The Taskbar importer should provide a simple interface:

```text
Apps > Import > Taskbar

[ Scan Taskbar ]
```

After scanning:

```text
[x] NEW      Firefox
[x] NEW      Visual Studio Code
[x] NEW      Windows Terminal
[ ] NEW      Calculator
    EXISTS   Blender

[ Import Selected ]
```

---

# 14. Taskbar Shortcut Metadata

Where possible, resolve shortcut information including:

```text
Display Name
Shortcut Path
Executable Target
Arguments
Working Directory
Icon
```

For example:

```text
Name:
Visual Studio Code

Executable:
C:\Users\...\Microsoft VS Code\Code.exe
```

The imported App should represent the actual application, not merely the `.lnk` file.

The `.lnk` source path can still be retained as import provenance.

---

# 15. Taskbar Candidate Defaults

Default:

```text
Kind:
Application
```

Default action:

```text
Open
```

Action type should normally be:

```text
EXECUTABLE
```

using the resolved executable and arguments.

If resolving the actual executable is unreliable for a particular shortcut, using the shortcut itself as the launch target is acceptable if Windows can launch it reliably.

Do not reject an otherwise valid item simply because every shortcut property could not be resolved.

---

# 16. Import Source 3 — Desktop Applications

## Purpose

Import launchable shortcuts that exist on the Windows Desktop.

The importer should scan both:

```text
User Desktop
Public Desktop
```

where available.

---

# 17. Desktop Scan

Provide:

```text
Apps > Import > Desktop

[ Scan Desktop ]
```

Example result:

```text
[x] NEW      Blender
[x] NEW      DB Browser for SQLite
[ ] NEW      VLC
[x] NEW      Android Studio
    EXISTS   Visual Studio Code

[ Import Selected ]
```

---

# 18. Desktop Candidate Types

Version 1 should scan suitable launchable shortcut types, primarily:

```text
.lnk
.url
```

Do not treat every Desktop file as an App.

For example, do not import:

```text
notes.txt
photo.jpg
invoice.pdf
random-folder
```

unless a later importer specifically supports such behaviour.

---

# 19. URL Shortcuts

For `.url` shortcuts:

```text
Kind:
Web App
```

or:

```text
Website
```

depending on the existing Apps content kinds.

Default action:

```text
OPEN_URL
```

Example:

```text
Fabric

Kind:
Web App

Action:
Open

URL:
https://...
```

---

# 20. Shared Candidate Grid

Implement one reusable candidate list/grid for all import sources.

Suggested columns:

```text
Select
Status
Name
Kind
Area
Target / Location
```

Example:

```text
☑  NEW      LifePIM      Development Project   Development   D:\Development\LifePIM
☑  NEW      Blender      Application           Design        C:\...\blender.exe
☐  NEW      Calculator   Application           General       C:\...\calc.exe
   EXISTS   VS Code       Application           Development   C:\...\Code.exe
```

Allow selection using checkboxes.

Provide:

```text
Select All
Select None
```

Existing items should normally be disabled/unselected.

---

# 21. Edit Before Import

Allow at least the following candidate values to be adjusted before import:

```text
Kind
Area
```

Ideally these should be editable directly in the grid or via a lightweight candidate editor.

Avoid requiring a full App editing dialog for every item.

The purpose of Import is rapid population.

For example, after scanning Taskbar:

```text
Blender       Application   [Design ▼]
VS Code       Application   [Development ▼]
VLC           Application   [Media ▼]
```

This makes it possible to classify several Apps before importing them.

---

# 22. Area Defaults

Each importer should provide a default Area selection where appropriate.

For Dev Folders:

```text
Default Area:
Development
```

All candidates initially inherit that Area.

For Taskbar/Desktop, the default may be:

```text
Unassigned
```

unless an Area is explicitly selected.

Do not automatically invent Areas from folder names or executable names.

---

# 23. Duplicate Detection

Duplicate detection is required in Version 1.

The importer should check candidate targets against existing Apps before import.

For Dev Folders, the primary duplicate key should be the normalised folder path.

Example:

```text
D:\Development\LifePIM
```

If this project is already an App:

```text
Status:
EXISTS
```

For executable applications, use the normalised executable target/path where practical.

Example:

```text
C:\Program Files\Blender Foundation\Blender\blender.exe
```

For URL Apps, use the URL where practical.

Do not rely on title alone.

For example:

```text
Visual Studio Code
```

could theoretically have multiple installations.

---

# 24. Path Normalisation

Use consistent Windows path normalisation when checking duplicates.

At minimum account for:

* path case
* slash direction
* trailing separators
* environment-variable expansion where appropriate

For example:

```text
D:\Development\LifePIM
```

and:

```text
d:\development\lifepim\
```

should represent the same target.

Prefer using established Python/path utilities rather than manually manipulating strings.

---

# 25. Import Operation

When the user clicks:

```text
Import Selected
```

iterate only over selected candidates with status:

```text
NEW
```

For each candidate:

1. Create normal `lp_app` record.
2. Assign Kind.
3. Create Area relationship if selected.
4. Create default App Action.
5. Store useful candidate metadata.
6. Store import provenance.
7. Commit the import cleanly.

Imported records should immediately behave exactly like manually created Apps.

There should not be a permanent distinction in normal Apps UI between manual and imported Apps.

---

# 26. Import Provenance

Retain lightweight information about how the App entered LifePIM.

Suggested fields, either on `lp_app` or via generic metadata if the existing architecture supports it:

```text
import_source
import_source_path
imported_date
```

Suggested `import_source` values:

```text
DEV_FOLDER
TASKBAR
DESKTOP
MANUAL
```

Examples:

```text
import_source:
DEV_FOLDER

import_source_path:
D:\Development\LifePIM
```

or:

```text
import_source:
DESKTOP

import_source_path:
C:\Users\<user>\Desktop\Blender.lnk
```

Do not make provenance mandatory for existing/manual records.

---

# 27. Why Store Import Provenance

This is primarily for:

* troubleshooting
* understanding where an App originated
* future rescan capability
* possible bulk cleanup/import management later

Do NOT implement bulk removal by import source yet unless it falls out very easily from the existing architecture.

The important requirement is to retain enough information to support it later.

---

# 28. Imported App Actions

Imported Apps should use the same `lp_app_action` functionality as manually configured Apps.

Examples:

## Dev Folder

```text
Name:
LifePIM

Action:
Open Folder

Type:
OPEN_FOLDER

Target:
D:\Development\LifePIM
```

## Desktop Application

```text
Name:
Blender

Action:
Open

Type:
EXECUTABLE

Target:
C:\Program Files\Blender Foundation\...\blender.exe
```

## Web Shortcut

```text
Name:
Fabric

Action:
Open

Type:
OPEN_URL

Target:
https://...
```

Do not create an importer-specific launching system.

---

# 29. Error Handling

Scanning should be resilient.

A malformed shortcut or inaccessible folder should not abort the entire scan.

For example:

```text
17 candidates found
1 shortcut could not be resolved
```

Invalid candidates may be shown with:

```text
INVALID
```

and disabled from import.

Log technical errors through the normal LifePIM logging framework.

Do not display stack traces in the Import UI.

---

# 30. Permissions and Missing Sources

The importer must handle sources that do not exist or are not available.

Examples:

* no Taskbar shortcut directory found
* Public Desktop does not exist
* selected Dev directory no longer exists
* access denied to directory

Display a friendly result such as:

```text
No Taskbar applications were found.
```

rather than treating this as a fatal application error.

---

# 31. Scan Performance

Scanning these sources should be lightweight.

Dev Folder scan:

* immediate child directories only
* basic marker-file checks
* no recursive indexing

Taskbar/Desktop:

* shortcut files only
* resolve relevant metadata

Do not perform full-drive executable scans.

Do not query every installed Windows application in Version 1.

---

# 32. UI State

Scanning should not alter database state.

The user should be able to:

```text
Scan
change selections
change Area/Kind
cancel
close Import
```

without creating any Apps.

If they close the Import screen before clicking Import, candidate state can simply be discarded.

No persistent staging table is required for Version 1.

---

# 33. Import Completion

After a successful import, show a concise result.

Example:

```text
Import complete.

5 Apps imported.
2 existing Apps skipped.
```

Provide an obvious way back to:

```text
Apps
```

The newly imported Apps should appear immediately without requiring a LifePIM restart.

---

# 34. Reusable Scanner Architecture

Do not implement three completely unrelated import systems.

Create a small reusable architecture.

Conceptually:

```text
AppImporter
    scan() -> list[AppImportCandidate]
```

Implementations might be:

```text
DevFolderAppImporter
TaskbarAppImporter
DesktopAppImporter
```

The UI should consume common `AppImportCandidate` records regardless of source.

This makes future importers easy to add.

Possible future sources include:

```text
Installed Applications
Start Menu
Git Repositories
Script Folders
PATH Commands
Browser Web Apps
SSH Hosts
Databases
Steam / Games
```

These are not part of Version 1.

---

# 35. Suggested File Structure

Fit this into the existing LifePIM source structure rather than forcing these exact paths, but a logical structure would be similar to:

```text
src/
    apps/
        import/
            models.py
            base.py
            dev_folders.py
            taskbar.py
            desktop.py
            windows_shortcuts.py
```

The Windows shortcut resolving code should ideally be reusable by both Taskbar and Desktop importers.

UI components should live alongside the existing Apps UI structure.

Do not duplicate Windows shortcut parsing code across importers.

---

# 36. Platform Behaviour

Version 1 Taskbar/Desktop importing is specifically Windows functionality.

The Apps feature itself should remain platform-neutral.

If running on another operating system:

```text
Taskbar
Desktop
```

should either be hidden/disabled appropriately or report that this importer is not available.

Dev Folder importing should remain usable cross-platform.

Avoid spreading Windows-specific path/shortcut logic throughout generic Apps code.

---

# 37. Tests

Add tests where practical.

At minimum test:

### Dev Folder importer

* finds immediate child directories
* does not recursively import nested folders
* handles missing root
* identifies project markers
* produces correct default action
* duplicate path is marked EXISTS

### Desktop importer

* filters supported shortcut types
* ignores normal files
* handles invalid shortcut gracefully

### Duplicate logic

* normalises case
* normalises trailing slash
* does not duplicate existing Apps

### Import operation

* selected NEW candidate creates App
* unselected candidate does not
* EXISTS candidate does not duplicate
* Area relationship created
* App action created
* provenance recorded

Tests should use temporary directories/test databases.

Do not add test records to the normal LifePIM database.

---

# 38. Version 1 Acceptance Criteria

The feature is complete when the user can:

### Dev Folders

1. Open Apps > Import.
2. Select Dev Folders.
3. Choose a development root.
4. Select a default Area.
5. Scan.
6. See immediate child folders.
7. Tick/untick candidates.
8. Change Area/Kind where necessary.
9. Import selected projects.
10. See them immediately in Apps.
11. Open an imported project folder using its default App action.

### Taskbar

1. Select Taskbar.
2. Scan pinned applications.
3. See discovered application shortcuts.
4. Existing Apps are identified.
5. Select Apps.
6. Assign Areas if desired.
7. Import.
8. Launch imported Apps normally.

### Desktop

1. Select Desktop.
2. Scan user/public Desktop shortcuts.
3. See `.lnk` / `.url` application candidates.
4. Ignore unrelated Desktop files.
5. Select and import Apps.
6. Launch imported Apps normally.

At no point should merely scanning a source insert records into the LifePIM database.

---

# 39. Explicitly Out of Scope for Version 1

Do not implement:

* full Windows installed-application inventory
* registry scanning for all installed software
* Start Menu scanning
* recursive whole-drive scans
* automatic importing
* continuous background discovery
* source-code indexing
* Git operations
* IDE integration
* automatic build-command generation
* automatic Area inference
* automatic cleanup/removal of Apps
* persistent import staging tables
* software package management

These can be considered later.

---

# 40. Design Principle

The key rule for this feature is:

> **Scanning finds candidates. Importing creates Apps.**

LifePIM should never assume that because something exists on the computer it deserves to become part of the user's Apps catalogue.

The importer should make populating Apps fast while keeping the final Apps database deliberate, clean and understandable.

The first three importers deliberately target high-value curated sources:

```text
Dev Folders
    → software projects the user maintains

Taskbar
    → applications the user uses frequently

Desktop
    → applications the user has explicitly placed for easy access
```

Together these should provide a useful initial Apps catalogue without requiring hard-coded seed data or filling LifePIM with every executable installed on the system.
