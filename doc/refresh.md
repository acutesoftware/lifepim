# LifePIM Data Refresh Notes

Short operator notes for refreshing LifePIM Desktop data.

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
5. Run folder mapping ETL.
6. Rebuild derived media events if media changed.
7. Start or restart LifePIM Desktop.

Current full bootstrap command:

```bat
cd src
..\.venv\Scripts\python.exe init_database.py
```

This is destructive. It deletes and recreates the configured `DB_FILE`, then runs the loaders and mapping ETL.

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

## Folder Mapping

Run this after refreshing folder lists or changing mapping rules:

```bat
cd src
ETL_MAP_FOLDERS.BAT
```

Inputs currently configured in `src/common/config.py`:

- `E:\BK_fangorn\user\duncan\LifePIM_Data\configuration\all_folders.csv`
- `E:\BK_fangorn\user\duncan\LifePIM_Data\configuration\map_project_folder.csv`

Tables updated:

- `dim_folder`
- `map_folder_project`
- `map_project_folder`
- `folder_id` on supported file-backed tables

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
| Files | `lp_files`, folder mapping tables | `E:\BK_fangorn\user\duncan\LifePIM_Data` and index CSVs | Refresh folder/file metadata, then run folder mapping ETL. |
| Media | `lp_media`, `lp_media_meta`, `lp_events`, `lp_event_items` | `P:\photo` staged to `E:\BK_fangorn\photo` | Robocopy first, scan `E:\BK_fangorn\photo`, then rebuild Media events. |
| Audio | `lp_audio` | NAS music staged to `E:\BK_fangorn\music\Music` | Robocopy first, then scan local audio files. |
| 3D | `lp_3d` | `E:\BK_fangorn\user\duncan\C\user\docs\designs\blender` | Scan `.blend` files and update metadata. |
| Money | `lp_money_plans` | App-local SQLite data | No external refresh yet. Future CSV/API imports should use importer jobs. |
| People | `lp_contacts`, contact fact tables | CSV/source DB via importer | Use importer v1. Dry-run first, then merge/snapshot into contacts. |
| Places | `lp_places` | App-local or future CSV | No external refresh currently documented. |
| Apps | `lp_apps` | `C:\apps` | Scan `.exe` files and update app metadata. |
| Admin | `sys_settings`, mapping tables | App settings and mapping CSVs | Settings are app-local. Mapping refresh uses `ETL_MAP_FOLDERS.BAT`. |
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
