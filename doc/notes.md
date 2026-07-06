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

## Operational Notes

Do not use `tests/LOAD_TESTING.py` as the normal Notes deployment/import path. It was a bulk test loader and should be phased out of deployment.

The UI import and migration forms do not read `FOLDER_NOTES` from `tests/LOAD_TESTING.py`. The folder is supplied by the UI form.

If you later reload mapping CSVs from disk and those CSVs still contain old paths such as `E:\BK_fangorn`, the old paths can come back. Update the CSVs too if the NAS path is now the permanent source of truth.

## TODO

- Add a refresh/sync job for notes. Current gap: if new `.md` files are added directly to the notes folder outside LifePIM, they are not automatically added to `lp_notes`. Today you must use `Import Folder`, but that is append-only and can create duplicates.
- Replace `tests/LOAD_TESTING.py` with explicit import/sync flows for each data source.
- Add idempotent note import keyed by full file path so repeated imports update existing rows instead of duplicating them.
