# LifePIM Data Refresh Notes

Short operator notes for refreshing LifePIM Desktop data.



NOTE - there is a gap here, INIT_ALL_DATA.py in the src/common folder 
succesfully colledcts file metadata but into the lifepim_etl.db

not sure how lifepim_etl.db gets populated into the lifepim.db
There have been a LOT of changes recently - best method I think 
is to drop all old methods, and start again - have ONE program that 
manages the refresh, checks for sql folder list, updates slowly

Probably best via InfoLink



## Refresh Model

LifePIM should read large/slow sources from a local working copy where possible.

- Media source of truth: `P:\` on the NAS.
- Media working copy: `E:\BK_fangorn`.
- LifePIM media metadata should be collected from `E:\BK_fangorn`, not directly from `P:\`.
- Notes source/edit location: `N:\duncan\LifePIM_Data\DATA\notes`.
- Notes are low latency enough to edit in place on `N:\`; optionally mirror them to `E:\BK_fangorn` for backup/search indexing.

Current bootstrap loaders still use hard-coded paths in `tests/LOAD_TESTING.py`. Treat that file as the current source list, not as a production incremental sync.

## Standard Refresh Order

1. Back up the SQLite DB.
2. Robocopy NAS data into the local working copy.
3. Refresh file/folder metadata.
4. Refresh LifePIM tables from the working copy or live notes folders.
5. Refresh the folder cache if folder/file metadata changed.
6. Rebuild derived media events if media changed.
7. Start or restart LifePIM Desktop.

Current full bootstrap command:

```bat
cd src
..\.venv\Scripts\python.exe init_database.py
```

This is destructive. It deletes and recreates the configured `DB_FILE`, then runs the loaders, folder cache refresh, and area-folder import.

## Robocopy Staging

Use robocopy before metadata scans so LifePIM stores local working-copy paths.

Media:

```bat
robocopy P:\photo E:\BK_fangorn\photo /MIR /FFT /Z /XA:H /W:5 /R:2 /XD "$RECYCLE.BIN" "System Volume Information"
```

Audio:

```bat
robocopy P:\music E:\BK_fangorn\music /MIR /FFT /Z /XA:H /W:5 /R:2 /XD "$RECYCLE.BIN" "System Volume Information"
```

Important: `/MIR` deletes destination files that no longer exist in the source. Run without `/MIR` first if checking a new path.

## Filelist Collection

Legacy filelist collection lives in:

```text
scripts/prod/filelister.py
scripts/prod/run_filelist.bat
```

Run:

```bat
cd scripts\prod
run_filelist.bat
```

Current behavior:

- On host `treebeard`, `filelister.py` scans `P:`.
- On other hosts, it scans `D:` and `C:`.
- Output goes to `\\FANGORN\user\duncan\LifePIM_Data\index`.
- The script is self-contained and does not read `src/common/config.py`.

Proposed production behavior: scan `E:\BK_fangorn` after robocopy, so the app indexes the local working copy rather than the NAS.

## Folder Cache

Run this after refreshing folder lists:

```bat
cd src
ETL_MAP_FOLDERS.BAT
```

Input currently configured in `src/common/config.py`:

- `E:\BK_fangorn\user\duncan\LifePIM_Data\configuration\all_folders.csv`

Tables updated:

- `dim_folder`
- `folder_id` on supported file-backed tables

### How `etl_folder_mapping.py` Is Used

`src/etl_folder_mapping.py` is still needed, but only as folder cache maintenance.

Current callers:

- `src/init_database.py`
  - creates the `dim_folder` schema during destructive database rebuild
  - runs `etl_folder_mapping.py` against `etl_folders_csv` to load known folders and backfill `folder_id`
- `src/ETL_MAP_FOLDERS.BAT`
  - manual wrapper for refreshing `dim_folder` and backfilling `folder_id`
- `src/common/data.py`
  - reuses path normalization and `dim_folder` helpers when records are added or updated
- `src/common/media_migration.py`
  - ensures folder support exists when media/audio rows are migrated from FileLister
- Tests
  - use the `dim_folder` schema helpers for isolated database setup

The script is useful when:

- `all_folders.csv` was refreshed from a disk scan
- file-backed records were loaded before they had `folder_id`
- media/audio/file imports need the `dim_folder` cache to exist
- a test or new database needs the folder cache schema

It is not needed for normal Notes Area mapping. Running it does not assign Notes to Areas and does not change `lp_area_folders`.

### Original Mapping Intent

The original intent was broader: map hard-drive folders to the left-hand-side Areas so clicking an Area could show the correct files/notes. That job has already been carried forward into the current schema:

- `lp_areas` defines the Area/sidebar metadata.
- `lp_area_folders` stores real disk folder prefixes for each Area.
- `lp_notes.area` stores the materialized Area value used for fast Notes filtering.

So the future refresh path is:

- If folder IDs/cache are stale, run `ETL_MAP_FOLDERS.BAT`.
- If a note's `Area` value is blank but its folder is already mapped, use Settings > Notes > `Materialize note areas`.
- If an Area needs another folder, add it from the Notes folder panel for that Area.
- If rebuilding from the configured bulk Area-folder CSV is really needed, back up the DB and run `common.areas.import_area_mappings_csv()` against `area_mappings_csv`; this upserts `lp_areas` and `lp_area_folders` but does not delete mappings removed from the CSV.

Bulk Area-folder CSV re-import:

```bat
cd src
..\.venv\Scripts\python.exe -c "from common import areas, config; areas.import_area_mappings_csv(config.area_mappings_csv); areas.assign_defaults_if_missing()"
```

## Per-Tab Refresh Notes

| Tab | Main table(s) | Source | Proposed refresh |
| --- | --- | --- | --- |
| Overview | mixed | Other LifePIM tables | No direct refresh. It summarizes data already loaded for other tabs. |
| Cal | `lp_calendar_events` | `N:\duncan\LifePIM_Data\calendar` | Scan live calendar folder and upsert events. Calendar file/image overlays come from `lp_files` and `lp_media`. |
| Goals | `lp_goals` | `N:\duncan\LifePIM_Data\goals` | Scan live goals folder and upsert by file path/title. |
| Tasks | `lp_tasks` | `N:\...\DATA\notes\00-META\02-Tasks` or mirrored path | Scan task files and upsert by file path. |
| How | `lp_how` | `N:\...\DATA\notes\40-Dev\42-HOWTO` or mirrored path | Scan how-to files and upsert by file path/title. |
| Notes | `lp_notes` | `N:\duncan\LifePIM_Data\DATA\notes` | Edit on `N:\`; refresh metadata from files. Note body remains in markdown files. |
| Data | `lp_data` | `E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\SQL` | Scan `.db` files and update database metadata. |
| Files | `lp_files`, `dim_folder` | `E:\BK_fangorn\user\duncan\LifePIM_Data` and index CSVs | Refresh folder/file metadata, then refresh the folder cache. |
| Media | `lp_media`, `lp_media_meta`, `lp_events`, `lp_event_items` | `P:\photo` staged to `E:\BK_fangorn\photo` | Robocopy first, scan `E:\BK_fangorn\photo`, then rebuild Media events. |
| Audio | `lp_audio` | NAS music staged to `E:\BK_fangorn\music\Music` | Robocopy first, then scan local audio files. |
| 3D | `lp_3d` | `E:\BK_fangorn\user\duncan\C\user\docs\designs\blender` | Scan `.blend` files and update metadata. |
| Money | `lp_money_plans` | App-local SQLite data | No external refresh yet. Future CSV/API imports should use importer jobs. |
| People | `lp_contacts`, contact fact tables | CSV/source DB via importer | Use importer v1. Dry-run first, then merge/snapshot into contacts. |
| Places | `lp_places` | App-local or future CSV | No external refresh currently documented. |
| Apps | `lp_apps` | `C:\apps` | Scan `.exe` files and update app metadata. |
| Admin | `sys_settings` | App settings | Settings are app-local. Note area folder rules are managed from Notes. |
| Agent | none yet | Future agent logs/tasks | No refresh process yet. |

## Current Loader Paths

Current full-load paths are in `tests/LOAD_TESTING.py`.

```text
FOLDER_AUDIO = E:\BK_fangorn\music\Music
FOLDER_MEDIA = E:\BK_fangorn\photo
FOLDER_NOTES = E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes
FOLDER_TASKS = E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes\00-META\02-Tasks
FOLDER_EVENTS = N:\duncan\LifePIM_Data\calendar
FOLDER_GOALS = N:\duncan\LifePIM_Data\goals
FOLDER_HOW = E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes\40-Dev\42-HOWTO
FOLDER_DATA = E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\SQL
FOLDER_FILES = E:\BK_fangorn\user\duncan\LifePIM_Data
FOLDER_3D = E:\BK_fangorn\user\duncan\C\user\docs\designs\blender
FOLDER_APPS = C:\apps
```

If notes are edited live on `N:\`, update the notes/task/how loaders to use `N:\...` directly or keep the `E:\BK_fangorn` mirror current before running bootstrap.

## Media Refresh Detail

Current `load_media()` behavior:

- Recurses `FOLDER_MEDIA`.
- Inserts images and videos into `lp_media` with `INSERT OR IGNORE`.
- Stores the real path in `lp_media.path`.
- Does not create thumbnail files.
- Does not store thumbnail blobs in SQLite.
- UI thumbnails are served from the real media file through `/media/file/<media_id>`.

After media refresh, rebuild derived event clusters:

```text
Media tab -> Rebuild events
```

This updates:

- `lp_events`
- `lp_event_items`

These are Media timeline events. They are not calendar events and do not write to `lp_calendar_events`.

## Proposed Incremental Jobs

The current full bootstrap is useful for rebuilding a dev/sample DB, but it is not the desired production refresh.

Recommended next jobs:

- `refresh_media.py`: scan `E:\BK_fangorn\photo`, upsert `lp_media`, tombstone missing files, rebuild events on demand.
- `refresh_notes.py`: scan `N:\duncan\LifePIM_Data\DATA\notes`, upsert `lp_notes`, `lp_tasks`, and `lp_how`.
- `refresh_calendar.py`: scan `N:\duncan\LifePIM_Data\calendar`, upsert `lp_calendar_events`.
- `refresh_filelist.py`: scan `E:\BK_fangorn`, update `lp_files`, then run folder mapping.
- `refresh_audio.py`: scan `E:\BK_fangorn\music`, upsert `lp_audio`.

Each job should be idempotent: match records by stable source path or source UID, update changed metadata, and avoid duplicate rows.
