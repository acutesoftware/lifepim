# Notes Source Deployment

Short operator notes for pointing LifePIM Desktop at a markdown notes source.

## Two Different Actions

Use the right action for the job:

- Add another notes folder: use `Notes tab -> Import Folder`.
- Replace the current notes source: use `Settings -> Notes -> Migrate notes source`.

Do not use `tests/LOAD_TESTING.py` as the normal notes deployment/import path. It was a bulk test loader and should be phased out of deployment.

## Add Notes Folder

Use this when adding extra notes without deleting existing note records.

1. Start LifePIM Desktop.
2. Open the Notes tab.
3. Click `Import Folder`.
4. Enter the notes folder root, for example:

   ```text
   N:\duncan\LifePIM_Data\DATA\notes
   ```

5. Click `Import Folder`.
6. Confirm the imported count is sensible.

This is append-only. It does not delete old notes, does not deduplicate by path, and does not touch links.

## Migrate Notes Source

Use this when changing from one root source to another, for example from `E:\BK_fangorn\...` to the live NAS folder.

1. Back up the SQLite database.

2. Start LifePIM Desktop.

3. Open:

   ```text
   Settings -> Notes
   ```

4. In `Migrate notes to new source`, enter the new notes root, for example:

   ```text
   N:\duncan\LifePIM_Data\DATA\notes
   ```

5. Leave `Project` blank unless you intentionally want every imported note to get the same explicit `project` value.

6. Tick:

   ```text
   Delete existing notes and note links before importing this folder
   ```

7. Click:

   ```text
   Migrate notes source
   ```

The migration pre-scans the selected folder before deleting anything. If the folder does not exist or contains no markdown files, it stops without clearing existing notes.

## What Migration Deletes

The migration route is:

```text
src/modules/notes/routes.py -> migrate_notes_source_route()
```

It deletes:

- all rows in `lp_notes`
- links where `lp_links.src_type` is `note` or `notes`
- links where `lp_links.dst_type` is `note` or `notes`

It also updates project/folder mapping paths for the notes source:

- rewrites matching `lp_project_folders.path_prefix` values from the old notes root to the new notes root
- rewrites matching `map_folder_project.path_prefix` values from the old notes root to the new notes root
- rebuilds `map_project_folder`

This is what moves project/sidebar filtering away from old mirror paths such as:

```text
E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes
```

to the selected live notes root, for example:

```text
N:\duncan\LifePIM_Data\DATA\notes
```

It does not delete markdown files on disk.

It does not delete old `dim_folder` rows. Old folder rows may remain in the folder cache, but migrated notes are assigned to folder IDs for the selected source path. This avoids accidentally removing folders that other tables may still use.

## What Import Stores

Both `Import Folder` and `Migrate notes source` use the same notes import helper.

They:

1. Walk the selected folder recursively.
2. Import `.md` files only.
3. Insert one row per markdown file into `lp_notes`.
4. Store metadata only:
   - `file_name`
   - `path`
   - `size`
   - `date_modified`
   - `project`
5. Leave the note body in the markdown file on disk.
6. Use `common.data.add_record()`, which also sets:
   - `user_name`
   - `rec_extract_date`
   - `folder_id`

Because `folder_id` is populated during `add_record()`, no separate folder-id backfill is needed for notes.

For notes, the import keeps the selected source path as the note path. It does not use the global mirror alias to rewrite `N:\...` back to `E:\BK_fangorn\...`.

## Links And Notes

Links are ID-based:

```text
lp_links.src_type / lp_links.src_id
lp_links.dst_type / lp_links.dst_id
```

For notes, those IDs are `lp_notes.id` values. When the notes source is replaced, imported notes get new IDs, so old note links cannot safely be reused. The migration deletes note-touching links so they can be recreated against the new note records.

Practical rule:

- Fresh DB plus `Import Folder`: no link reset needed.
- Adding an extra folder with `Import Folder`: existing links are preserved.
- Replacing the notes root: use `Migrate notes source`, which clears note links and notes before importing.

## Config To Check

Primary config file:

```text
src/common/config.py
```

Check the configured app data folder and database:

```python
user_folder = r"D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data"
db_name = os.path.join(user_folder, 'lifepim.db')
DB_FILE = db_name
```

The UI import and migration forms do not read `FOLDER_NOTES` from `tests/LOAD_TESTING.py`. The folder is supplied by the UI form.

If project/sidebar mapping should work for the new NAS folder, check that project folder mappings include the NAS path prefixes. These mappings are managed through the folder/project mapping tables and CSVs, not by the notes import itself.

Relevant config values:

```python
etl_folders_csv = r"E:\BK_fangorn\user\duncan\LifePIM_Data\configuration\all_folders.csv"
etl_rules_csv = r"E:\BK_fangorn\user\duncan\LifePIM_Data\configuration\map_project_folder.csv"
PATH_ALIASES = [
    (r"N:\duncan", r"E:\BK_fangorn\user\duncan"),
    (r"N:\\", r"E:\BK_fangorn\user"),
]
```

If the mapping CSVs are still based on `E:\BK_fangorn` but imported notes are stored as `N:\...`, mapping may not match unless aliases/mapping rules account for both forms.

The migration flow rewrites the currently loaded mapping rows in the SQLite database. If you later reload mapping CSVs from disk and those CSVs still contain `E:\BK_fangorn`, the old paths can come back. Update the CSVs too if the NAS path is now the permanent source of truth.

Run folder mapping only if you changed project/folder mapping CSVs or need to refresh sidebar/project classification:

```bat
cd src
ETL_MAP_FOLDERS.BAT
```

## What Is Not Needed For Notes Import

For notes only, you do not need to run these after using the UI import or migration:

- `tests/LOAD_TESTING.py`
- `load_notes()` from `tests/LOAD_TESTING.py`
- a full data reload
- a separate folder-id backfill
- a separate note-body import

## Current Refactor Target

`tests/LOAD_TESTING.py` should stop being part of deployment. The next cleanup should split database schema initialization from data loading so the deploy flow can be:

1. Initialize schema.
2. Start app.
3. Import or migrate notes through the UI.
4. Import other data sources through their own explicit import flows.
