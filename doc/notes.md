# Notes

LifePIM Notes are markdown files on disk with metadata stored in SQLite.

## Overview

The Notes tab lists markdown files that have been imported into the `lp_notes` table. The database stores metadata only:

- `file_name`
- `path`
- `folder_id`
- `size`
- `date_modified`
- `project`

The note body remains in the `.md` file on disk. Viewing or editing a note reads/writes the markdown file directly.

### View Notes

Open the Notes tab from the top navigation.

Use the left project/sidebar tabs to filter notes by mapped project folders. Use the Folders section inside the Notes view to drill into subfolders under the current notes root or current project folder.

### Add Notes

New notes can be created from the Notes UI. The app writes a new `.md` file into the selected project's default notes folder and inserts a matching row into `lp_notes`.

The project must have a default folder configured before new-note creation can write to the correct place.

### Edit Notes

Open a note and click `Edit`.

Saving a note updates the markdown file on disk. The app also updates the note metadata in `lp_notes`, including:

- `size`
- `date_modified`
- `rec_extract_date`

This means edits made through LifePIM keep the database metadata current.

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
4. Leave `Project` blank unless every imported note should get one explicit project value.
5. Tick `Delete existing notes and note links before importing this folder`.
6. Click `Migrate notes source`.

Migration pre-scans the target folder before deleting anything. If the folder does not exist or contains no markdown files, migration stops.

Migration deletes:

- all rows in `lp_notes`
- links where `lp_links.src_type` is `note` or `notes`
- links where `lp_links.dst_type` is `note` or `notes`

Migration does not delete markdown files on disk.

Migration also updates project/folder mapping paths for the notes source:

- rewrites matching `lp_project_folders.path_prefix` values from the old notes root to the new notes root
- rewrites matching `map_folder_project.path_prefix` values from the old notes root to the new notes root
- rebuilds `map_project_folder`

This moves project/sidebar filtering away from old mirror paths such as:

```text
E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes
```

to the selected source, for example:

```text
N:\duncan\LifePIM_Data\DATA\notes
```

Links are ID-based. For notes, links point at `lp_notes.id`, so replacing the notes table creates new note IDs. Note links must be recreated after migration.

## Folders

Folders are how Notes connect markdown files to projects and the left-hand project/sidebar tabs.

There are three related concepts:

- `lp_notes.path`
  - The real folder containing the markdown file.
- `dim_folder`
  - A normalized folder cache. Each imported note gets a `folder_id` pointing here.
- `lp_project_folders`
  - Project folder rules. These decide which folders belong to which project/sidebar tab.

When a note is imported or created, LifePIM stores the actual selected notes path and assigns `folder_id`. For notes, the import keeps the selected source path. It does not rewrite `N:\...` back to `E:\BK_fangorn\...`.

Project filtering works by matching a note folder against enabled `lp_project_folders.path_prefix` values. More specific folder prefixes should win over broad parent folders.

Example:

```text
N:\duncan\LifePIM_Data\DATA\notes\10-Pers\13-Family
```

should map more specifically than:

```text
N:\duncan\LifePIM_Data\DATA\notes\10-Pers
```

The Folders section in Notes is a navigation aid. It shows subfolders for the current notes/project filter so you can drill into the markdown tree.

If folder/project mapping looks wrong after changing source, run `Migrate notes source` rather than plain `Import Folder`, because migration rewrites the mapping prefixes from the old root to the new root.

## Projects

Notes currently have two project concepts:

- `lp_notes.project`
  - A stored text column on the note row.
  - It is set when a new note is created from a selected project, or when folder import is run with a selected `proj`.
  - It is often blank for migrated/imported notes, because migration normally imports with `Project` blank and relies on folder mapping instead.
  - It is displayed in the Notes table as `Project`.
- derived project
  - A runtime value calculated from the note folder.
  - It is displayed in the Notes table and note view as `Derived` / `Derived Project`.
  - It is the value that usually explains why sidebar filtering works even when `lp_notes.project` is empty.

The derived project is calculated by joining:

```text
lp_notes.folder_id -> dim_folder.folder_id -> dim_folder.folder_path
```

then finding the enabled `lp_project_folders` row whose `path_prefix` is the best prefix match for that folder:

```sql
SELECT pf.project_id
FROM lp_project_folders pf
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

lp_project_folders:
project_id        path_prefix
proj/dev          N:\duncan\LifePIM_Data\DATA\notes\40-Dev
proj/dev/lifepim  N:\duncan\LifePIM_Data\DATA\notes\40-Dev\42-HOWTO

derived_project:
proj/dev/lifepim
```

The more specific path wins because the query sorts by longest `path_prefix` first.

### Sidebar Filtering

The left sidebar is defined in `src/common/config.py` as `SIDE_TABS`. Each entry has an `id`, for example:

```python
{ 'id': 'proj/dev/lifepim', 'label': 'LifePIM' }
```

The layout turns the selected sidebar entry into a URL query parameter:

```text
/notes?proj=proj/dev/lifepim
```

For Notes, that `proj` value is used as a folder-scope filter. The Notes list does not primarily filter by `lp_notes.project`; it checks whether the note's `dim_folder.folder_path` matches an enabled `lp_project_folders.path_prefix` for that `project_id`.

Parent sidebar entries such as `fun` expand to the active projects in that group, such as `fun/games` and `fun/food`. Leaf entries filter by each note's single derived project, so a broad placeholder folder on `fun/sport` does not make Sport show every note under the shared `50-Fun` root.

`Unmapped` is special. It shows notes whose folder does not match any enabled project folder prefix.

### Mapping Sources

There are two related mapping layers.

The current Notes list/create flow uses:

- `lp_projects`
  - Project metadata: `project_id`, `tab`, `group_name`, `project_name`, status, tags.
- `lp_project_folders`
  - The project-to-folder rules used by Notes filtering, derived project, and new-note default folders.
  - These can be adjusted in the Notes UI when a selected sidebar project has an `lp_projects` row. The `Folders` panel can add, remove, enable/disable, and set default folders.

The older folder-mapping ETL uses:

- `map_folder_project`
  - Raw mapping rules imported from the external CSV configured by `etl_rules_csv`.
- `map_project_folder`
  - Rebuilt cache that maps `dim_folder.folder_id` to the best matching raw mapping rule.

The external CSV location is configured in `src/common/config.py`:

```python
etl_rules_csv = r"E:\BK_fangorn\user\duncan\LifePIM_Data\configuration\map_project_folder.csv"
```

That CSV expects at least:

```text
path_prefix, tab, grp
```

and can also contain:

```text
project, tags, confidence, priority, is_primary, is_enabled, notes
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

`init_database.py` also imports project/folder rows into `lp_projects` and `lp_project_folders` from the configured rules CSV through `common.projects.import_project_mappings_csv()`.

The Admin mapping page can display `map_folder_project`, `map_project_folder`, and `dim_folder`, and can rebuild the old mapping cache. It is not currently an editor for the CSV or for `lp_project_folders`.

### Why the Project Column Can Be Empty

The `Project` column in the Notes table is the stored `lp_notes.project` value. It is not the derived folder mapping. For imported or migrated notes this can be blank by design, because the import path usually leaves explicit project blank and lets folder mapping derive the project.

Editing a note currently edits the markdown body and updates metadata such as size and modified time. It does not provide a project editor. Also, changing only `lp_notes.project` would not change sidebar filtering for Notes, because sidebar filtering is based on `lp_project_folders` and `dim_folder.folder_path`.

### Best Way Forward

Treat folder-derived project as the authoritative project for file-backed Notes.

Recommended fix:

1. Rename the Notes table columns so the UI is explicit:
   - show derived/effective project as `Project`
   - keep `lp_notes.project` visible as `Stored Project` because new-note creation populates it and it is useful diagnostic metadata
2. Add an `effective_project` value in the Notes query:
   - `COALESCE(NULLIF(t.project, ''), derived_project)` if stored project should act as an override
   - or just `derived_project` if folder location must remain authoritative
3. Update note view/edit to select and display `derived_project` consistently. The edit route currently fetches the note through `_get_note_record()`, which does not include the derived project query used by list/view.
4. Add a project/folder editor, not just a text field:
   - For changing a note's actual project, move the markdown file to the selected project's default folder, then update `lp_notes.path`, `folder_id`, and optionally `lp_notes.project`.
   - For changing how a whole folder maps, edit `lp_project_folders` or the external `map_project_folder.csv` rule and rebuild/import mappings.
5. Backfill existing rows only if the stored column is still useful:
   - set `lp_notes.project = derived_project` for rows where it is blank
   - keep this as a maintenance operation, because future folder mapping changes can make the stored value stale.

Do not make the current `Project` cell a simple editable text box as the main fix. That would make the displayed stored value look correct while leaving sidebar filters, derived project, and new-note folder behavior unchanged.

### Notes Path Aliases

New notes can be created in the correct `N:\...` folder and have `lp_notes.project` populated, while still showing no derived project if the note's `folder_id` points at an alias path. One observed example:

```text
lp_notes.path:       N:\duncan\LifePIM_Data\DATA\notes\10-Pers\12-Health
lp_notes.project:    pers/health
dim_folder row:      E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes\10-Pers\12-Health
lp_project_folders:  N:\duncan\LifePIM_Data\DATA\notes\10-Pers\12-Health
derived_project:     None
```

This happens when folder-id backfill applies `PATH_ALIASES` to Notes and stores the alias path in `dim_folder`, while the project folder rules use the live `N:\...` path. Derived-project matching then compares `E:\...` to `N:\...` and fails.

For Notes, `folder_id` now preserves the same live path stored in `lp_notes.path`, and Notes project filtering/derived-project lookup prefers `lp_notes.path` before falling back to `dim_folder.folder_path`. This lets existing stale rows still match the correct project while future note updates stop rewriting the folder to the alias path.

## Operational Notes

Do not use `tests/LOAD_TESTING.py` as the normal Notes deployment/import path. It was a bulk test loader and should be phased out of deployment.

The UI import and migration forms do not read `FOLDER_NOTES` from `tests/LOAD_TESTING.py`. The folder is supplied by the UI form.

If you later reload mapping CSVs from disk and those CSVs still contain old paths such as `E:\BK_fangorn`, the old paths can come back. Update the CSVs too if the NAS path is now the permanent source of truth.

## TODO

- Add a refresh/sync job for notes. Current gap: if new `.md` files are added directly to the notes folder outside LifePIM, they are not automatically added to `lp_notes`. Today you must use `Import Folder`, but that is append-only and can create duplicates.
- Replace `tests/LOAD_TESTING.py` with explicit import/sync flows for each data source.
- Add idempotent note import keyed by full file path so repeated imports update existing rows instead of duplicating them.
