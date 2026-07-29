# Notes

LifePIM Notes are markdown files on disk with metadata stored in SQLite.

## Overview

The Notes tab lists markdown files that have been imported into the `lp_notes` table. The database stores metadata only:

- `file_name`
- `path`
- `folder_id`
- `size`
- `date_modified`
- `area`

The note body remains in the `.md` file on disk. Viewing or editing a note reads/writes the markdown file directly.

### View Notes

Open the Notes tab from the top navigation.

Use the left area/sidebar tabs to filter notes by saved area metadata. Use the Folders section inside the Notes view to drill into subfolders under the current notes root or current area folder.

The top header of the Notes page is defined below
BOLD TITLE : Notes ([area]) - if note area selected it just says 'Notes"
CONTROLS: (series of buttons and dropdowns as per below)
  LABEL : "View as : " 
  DROP DOWN LIST : [ List | Table | Grid | Preview | Names only ]
  LABEL : "Sort by : "
  DROP DOWN LIST : [ Title | size | Color | Area | Date Created | Date Modified | Folder]
  DROP DOWN LIST : [ Asc | Desc]
  
  BUTTON : New Note
  LABEL : shows count of notes and num selected, eg "68 Notes  0 selected"
  DROP DOWN LIST: disabled until ANY note selected then: 
        - Link Selected Note to ..  (popup to Links)
        - Delete Selected notes
        - Move selected notes to Area (popup list of areas)
        - Set color of selected notes to ... (popup list of colors)

  DROP DOWN LIST : [...]  shows a triple dot popup menu for other options
    - option 1 = "Import Folder"



For the View as list:
- List : List of notes with circle of color at the start 
= Table : notes with following columns
          - Filename
          - Color
          - Area
          - Size
          - Date Created
          - Date Modified
          - Controls (Links) - Edit / Del


FOLDERS PANEL
Have a folders panel, hidden by default showing the list of actual folders when expanded.
By default we only see a line " Folders [+]"

When expanded - it shows the list of folders that are mapped to this area

MAIN BODY
The main body shows the notes list as selected - may be a table, list or grid depending on settings.
List of notes is paginated.

PAGINATION
If the number of notes to list is too high, pagination occurs and the navigation appears at the end



### View a Single Note

Once the user clicks on a note the Note View screen is shown : 

The top header has the following controls:
BOLD TITLE :  FileName.md  
BREADCRUMB FOLDER NAVIGATION : root folder > subfolder > current folder
CONTROLS : (series of buttons / drop down lists as per below)
  LABEL : "View as :"
  DROP DOWN LIST : [ Text | Markdown | Hex | Metadata ]
  BUTTON : "Edit"
  BUTTON : "Open Folder"
  LABEL : Circle of colour (just a colored cicle)
  DROP DOWN LIST : [List of Colors] - changing this changes the notes color
  BUTTON : "Rename" (pops up dialog with current file asking for new name)
  LABEL : "Area :"
  DROP DOWN LIST : [List of Areas]
  BUTTON : "Move" (moves Area to currently selected area)
  BUTTON : Delete this file (asks for congirmation first then moves the file to the trash folder)
  BUTTON : Convert to HOWTO
  

For the View as list:
- Text mode : views the text as simple text file
- Markdown : views as markdown with addition [img] tags rendered
- Hex : view hex mode
- Sample : Show the top 'nn' lines of the file and last 'nn' lines of the file ('nn = number of sample lines that can be set in the Settings > Note section)
- Markdown : shows the full file metadata and file front matter


MAIN BODY
If the user is choosing to view metadata , then only the metadata and front matter is shown

 Otherwise the content of the note is shown


### Add Notes

New notes can be created from the Notes UI. The app writes a new `.md` file into the selected area's default notes folder and inserts a matching row into `lp_notes`.

The area must have a default folder configured before new-note creation can write to the correct place.

### Edit Notes

Open a note and click `Edit`.

Saving a note updates the markdown file on disk. The app also updates the note metadata in `lp_notes`, including:

- `size`
- `date_modified`
- `rec_extract_date`

This means edits made through LifePIM keep the database metadata current.

### Converting Notes to HOWTOs

Open a note and click `Convert to HOWTO`.

The app asks for confirmation before converting. If confirmed, LifePIM:

- reads the note's markdown file from disk
- creates a new row in `lp_howto`
- uses the note filename without `.md` as the HOWTO title
- copies the note's saved `lp_notes.area` into `lp_howto.area_id`
- stores the original note markdown in `lp_howto.markdown_full_content`
- stores the original note file path in `lp_howto.source_filepath`
- removes the note row from `lp_notes`
- opens the new HOWTO view

The conversion does not immediately parse the note into HOWTO parts, tools, steps, or linked child HOWTOs. The new HOWTO is created with:

```text
parse_status = NOT_PARSED
parse_message = Converted from Note. Open and Preview to parse.
```

This is deliberate. Notes are free-form markdown, while HOWTOs are structured blueprints. Automatically parsing an arbitrary note during conversion could create incorrect catalog records or fail on content that was never written as a blueprint.

After conversion, open the HOWTO editor, click `Preview`, review the parsed summary/outcome/parts/tools/steps and diagnostics, then click `Save and Apply` when the markdown is ready to become structured HOW data.

Conversion is a reclassification, not a file delete. The markdown content is preserved in the HOWTO record, and the source file path is retained for traceability.

### Import Folder

Use:

```text
Notes tab -> Import Folder
```

Use this when adding another notes folder without deleting existing notes.

`Import Folder` is append-only:

- imports `.md` files recursively
- creates rows in `lp_notes`
- leaves existing notes alone
- leaves existing links alone
- does not deduplicate by path

Do not import the same folder twice unless duplicate rows are acceptable.

## Sync Notes

Use sync when markdown files were added or edited outside LifePIM and the database metadata needs to catch up.

Full notes sync:

```text
Settings -> Notes -> Sync notes
```

Area/folder sync:

```text
Notes -> select area -> Folders panel -> Sync
```

Sync is idempotent:

- scans `.md` files recursively
- inserts new files into `lp_notes`
- updates existing rows by full file path
- refreshes `size`, `date_modified`, and `folder_id`
- preserves existing `lp_notes.area`
- fills blank `lp_notes.area` from the deepest matching enabled area folder mapping
- counts missing-on-disk rows but does not delete them
- ignores duplicate database rows after the first matching full path

Use `Import Folder` only when append-only import behavior is acceptable. Use `Sync notes` for normal ongoing refresh.

## Migrate

Use migration when changing the notes source to an existing notes folder, such as moving from a local mirror to the live NAS folder.

Example live notes root:

```text
N:\duncan\LifePIM_Data\DATA\notes
```

Run:

```text
Settings -> Notes -> Migrate notes source
```

Steps:

1. Back up the SQLite database.
2. Open `Settings -> Notes`.
3. Enter the new notes root.
4. Leave `Area` blank unless every imported note should get one explicit area value.
5. Tick `Delete existing notes and note links before importing this folder`.
6. Click `Migrate notes source`.

Migration pre-scans the target folder before deleting anything. If the folder does not exist or contains no markdown files, migration stops.

Migration deletes:

- all rows in `lp_notes`
- links where `lp_links.src_type` is `note` or `notes`
- links where `lp_links.dst_type` is `note` or `notes`

Migration does not delete markdown files on disk.

Migration also updates area/folder mapping paths for the notes source:

- rewrites matching `lp_area_folders.path_prefix` values from the old notes root to the new notes root
- rewrites matching `map_folder_area.path_prefix` values from the old notes root to the new notes root
- rebuilds `map_area_folder`

This moves area/sidebar filtering away from old mirror paths such as:

```text
E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes
```

to the selected source, for example:

```text
N:\duncan\LifePIM_Data\DATA\notes
```

Links are ID-based. For notes, links point at `lp_notes.id`, so replacing the notes table creates new note IDs. Note links must be recreated after migration.

## Folders

Folders are how Notes connect markdown files to areas and the left-hand area/sidebar tabs.

There are three related concepts:

- `lp_notes.path`
  - The real folder containing the markdown file.
- `dim_folder`
  - A normalized folder cache. Each imported note gets a `folder_id` pointing here.
- `lp_area_folders`
  - Area folder rules. These decide which folders belong to which area/sidebar tab.

When a note is imported or created, LifePIM stores the actual selected notes path and assigns `folder_id`. For notes, the import keeps the selected source path. It does not rewrite `N:\...` back to `E:\BK_fangorn\...`.

Area filtering works by matching a note folder against enabled `lp_area_folders.path_prefix` values. More specific folder prefixes should win over broad parent folders.

Example:

```text
N:\duncan\LifePIM_Data\DATA\notes\10-Pers\13-Family
```

should map more specifically than:

```text
N:\duncan\LifePIM_Data\DATA\notes\10-Pers
```

The Folders section in Notes is a navigation aid. It shows subfolders for the current notes/area filter so you can drill into the markdown tree.

If folder/area mapping looks wrong after changing source, run `Migrate notes source` rather than plain `Import Folder`, because migration rewrites the mapping prefixes from the old root to the new root.

## Areas

Notes currently have two area concepts:

- `lp_notes.area`
  - A stored text column on the note row.
  - It is set when a new note is created from a selected area, when folder import/sync has a selected `area`, or when note area materialization fills a blank value from folder mappings.
  - It can still be blank for old migrated/imported notes until materialization or sync has run.
  - It is displayed in the Notes table as `Area`.
- derived area
  - A runtime value calculated from the note folder.
  - It is useful as diagnostic information and as an input to materialization.
  - It is not the normal list/sidebar filter path because calculating it for every row on every click is too slow.

The derived area can be calculated by joining:

```text
lp_notes.folder_id -> dim_folder.folder_id -> dim_folder.folder_path
```

then finding the enabled `lp_area_folders` row whose `path_prefix` is the best prefix match for that folder:

```sql
SELECT pf.area_id
FROM lp_area_folders pf
WHERE pf.is_enabled = 1
  AND pf.folder_role IN ('default','include','archive','output')
  AND lower(dim_folder.folder_path) LIKE lower(pf.path_prefix) || '%'
ORDER BY
  LENGTH(pf.path_prefix) DESC,
  CASE pf.folder_role
    WHEN 'default' THEN 0
    WHEN 'include' THEN 1
    WHEN 'output' THEN 2
    WHEN 'archive' THEN 3
    ELSE 9
  END,
  pf.sort_order,
  pf.path_prefix
LIMIT 1;
```

Example:

```text
lp_notes.path:
N:\duncan\LifePIM_Data\DATA\notes\40-Dev\42-HOWTO

dim_folder.folder_path:
N:\duncan\LifePIM_Data\DATA\notes\40-Dev\42-HOWTO

lp_area_folders:
area_id        path_prefix
area/dev          N:\duncan\LifePIM_Data\DATA\notes\40-Dev
area/dev/lifepim  N:\duncan\LifePIM_Data\DATA\notes\40-Dev\42-HOWTO

derived_area:
area/dev/lifepim
```

The more specific path wins because the mapping is sorted by longest `path_prefix` first. This calculation should happen during sync/materialization, not during every list browse.

### Sidebar Filtering

The left sidebar is defined in `src/common/config.py` as `SIDE_TABS`. Each entry has an `id`, for example:

```python
{ 'id': 'area/dev/lifepim', 'label': 'LifePIM' }
```

The layout turns the selected sidebar entry into a URL query parameter:

```text
/notes?area=area/dev/lifepim
```

For Notes, that `area` value is used as a metadata filter. The Notes list filters by `lp_notes.area`, not by deriving folder mappings for every row during browsing.

This is deliberate. The older folder-derived query was correct but too slow for interactive list/table/card browsing. Area folder mappings are now materialized into `lp_notes.area` during sync and by the note area materialization maintenance action.

Parent sidebar entries such as `fun` expand to the active areas in that group, such as `fun/games` and `fun/food`. Leaf entries filter by each note's saved area value, so a broad placeholder folder on `fun/sport` does not make Sport show every note under the shared `50-Fun` root after materialization.

`Unmapped` is special. It shows notes whose saved `lp_notes.area` is blank.

### Mapping Sources

There are two related mapping layers.

The current Notes list/create flow uses:

- `lp_areas`
  - Area metadata: `area_id`, `tab`, `group_name`, `area_name`, status, tags.
- `lp_area_folders`
  - The area-to-folder rules used by note area materialization, derived area display, sync fallback metadata, and new-note default folders.
  - These can be adjusted in the Notes UI when a selected sidebar area has an `lp_areas` row. The `Folders` panel can add, remove, enable/disable, and set default folders.

The older folder-mapping ETL uses:

- `map_folder_area`
  - Raw mapping rules imported from the external CSV configured by `etl_rules_csv`.
- `map_area_folder`
  - Rebuilt cache that maps `dim_folder.folder_id` to the best matching raw mapping rule.

The external CSV location is configured in `src/common/config.py`:

```python
etl_rules_csv = r"E:\BK_fangorn\user\duncan\LifePIM_Data\configuration\map_area_folder.csv"
```

That CSV expects at least:

```text
path_prefix, tab, grp
```

and can also contain:

```text
area, tags, confidence, priority, is_primary, is_enabled, notes
```

Run this after changing the CSV:

```bat
cd src
ETL_MAP_FOLDERS.BAT
```

or rebuild from scratch with:

```bat
cd src
..\.venv\Scripts\python.exe init_database.py
```

`init_database.py` also imports area/folder rows into `lp_areas` and `lp_area_folders` from the configured rules CSV through `common.areas.import_area_mappings_csv()`.

The Admin mapping page can display `map_folder_area`, `map_area_folder`, and `dim_folder`, and can rebuild the old mapping cache. It is not currently an editor for the CSV or for `lp_area_folders`.

### Why the Area Column Can Be Empty

The `Area` column in the Notes table is the stored `lp_notes.area` value. For old imported or migrated notes this can be blank because the old import path often relied on folder-derived filtering.

Blank areas should be fixed by materializing folder mappings into `lp_notes.area`, not by restoring expensive per-request folder joins.

### Materialized Area Metadata

Treat folder-derived area as a sync/materialization input for file-backed Notes.

The fast browsing design is:

1. Store area membership on the note row in `lp_notes.area`.
2. Use `lp_area_folders.path_prefix` to fill blank note area values during sync/materialization.
3. Filter List/Table/Grid/Preview by indexed `lp_notes.area`.
4. Read note files only during sync/indexing or when opening one note.

Settings > Notes includes `Materialize note areas`. This fills blank note area metadata from saved area-folder mappings without reading note files.

On Notes access, LifePIM also runs this materialization once per database connection/user so a deploy can repair older blank-area rows without waiting for a full disk sync.

### Materialized Note Color Metadata

Note color is stored on each row in `lp_notes.color`. List, Table, Grid, and Preview views use that saved value; they do not read the markdown file while filtering or paging.

Blank or unrecognized colors display as the default yellow. This is expected for old imported rows where the markdown file has `color:` or `colour:` front matter but the database row was never backfilled.

Settings > Notes includes `Refresh note colors`. This is a gentle maintenance action: it reads markdown front matter once for blank-color note rows, validates the color with the same display parser, and updates only `lp_notes.color`. Existing non-blank colors are left alone by default.

### Notes Path Aliases

New notes can be created in the correct `N:\...` folder and have `lp_notes.area` populated, while still showing no derived area if the note's `folder_id` points at an alias path. One observed example:

```text
lp_notes.path:       N:\duncan\LifePIM_Data\DATA\notes\10-Pers\12-Health
lp_notes.area:    pers/health
dim_folder row:      E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes\10-Pers\12-Health
lp_area_folders:  N:\duncan\LifePIM_Data\DATA\notes\10-Pers\12-Health
derived_area:     None
```

This happens when folder-id backfill applies `PATH_ALIASES` to Notes and stores the alias path in `dim_folder`, while the area folder rules use the live `N:\...` path. Derived-area matching then compares `E:\...` to `N:\...` and fails.

For Notes, `folder_id` now preserves the same live path stored in `lp_notes.path`, and Notes area filtering/derived-area lookup prefers `lp_notes.path` before falling back to `dim_folder.folder_path`. This lets existing stale rows still match the correct area while future note updates stop rewriting the folder to the alias path.

## Operational Notes

Do not use `tests/LOAD_TESTING.py` as the normal Notes deployment/import path. It was a bulk test loader and should be phased out of deployment.

The UI import and migration forms do not read `FOLDER_NOTES` from `tests/LOAD_TESTING.py`. The folder is supplied by the UI form.

If you later reload mapping CSVs from disk and those CSVs still contain old paths such as `E:\BK_fangorn`, the old paths can come back. Update the CSVs too if the NAS path is now the permanent source of truth.


## Note Functions
Should be functions below on either the Note or the text selected (whichever works)

Right click a note, or selected text or pick from [...] menu:
Find in Note : search this note / text for a string
Find in LifePIM : search ALL notes for a string
Find in Wikipedia : search wikipedia for a string (search string with site:wikipedia.org)
Find in Google : search internet for a string

Extract URL's : opens a new text window with list of URLs from this note
Extract emails : opens a new text window with list of emails from this note

Jump to Line : jumps to line number (-1 means end of file)
Jump to Heading : opens a new  window with list of clickable Links to headings in this note
