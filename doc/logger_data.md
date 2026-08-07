# LifePIM Logger Data

This document describes how LifePIM Desktop handles raw Logger files from the mobile app, and how to load those files into the logger SQLite database after the Data tab process changes.

## Current Workflow

Logger data has three stages:

1. Sync raw files from the phone to Desktop.
2. Run the saved Data process that imports those raw files into `logger.sqlite`.
3. Browse the imported raw logger tables from the Data tab.

Raw files remain the source of truth. The logger SQLite database can be rebuilt from those files.

## Quick Steps

1. Open `Admin > Logs > Logger`.
2. Check `Recent Sync Activity` and `Raw Files` to confirm the phone files have arrived.
3. Check the Logger raw-data root. It should point at the folder that contains the per-device folders.
4. Click `Preview Import`.
5. If the preview finds files, click `Run Import`.
6. Open the latest run from `Latest Data Process Runs` if you need file-level details.
7. Click `Open Data Process` or go to `Data > Processes` for the canonical process screen.
8. Click `View Logger Tables` from `Data > Processes` to register and scan the logger SQLite database in the Data catalogue.

The same import can also be started from `Data > Overview > Run Logger Import` or from `Data > Processes > Run`.

## What Each Page Does

### Admin > Logs > Logger

Use this page for day-to-day checks:

| Area | Purpose |
| --- | --- |
| Logger Summary | Shows whether sync is enabled, where raw files are stored, device count, and recent sync totals. |
| Logger Processing | Shows processing shortcuts and older activity-session status. |
| Latest Data Process Runs | Shows the runs created by the top-level Data process. |
| Recent Sync Activity | Shows phone-to-desktop sync runs. |
| Raw Files | Lists the synced files currently on disk. |

Important: `Raw Files` only proves that files arrived from the phone. It does not mean they have been imported into the logger database yet.

### Data > Processes

This is the canonical place to configure and run logger import.

The default process is:

```text
Import LifePIM Logger JSON
```

It imports raw JSON and JSONL files into the separate logger SQLite database. The process tracks run history, per-file results, warnings, and errors in the main LifePIM database.

### Data > Process Runs

Use this page to inspect historical process runs. Open a run to see:

| Section | Purpose |
| --- | --- |
| Run summary | Overall status and counts. |
| File results | Which files were imported, skipped, or failed. |
| Messages | User-facing diagnostics from the handler. |

## Configuration

The logger import process uses these key settings:

| Setting | Meaning |
| --- | --- |
| Source folder | Folder that contains the synced raw logger files. Usually the Logger raw-data root from Admin settings. |
| File pattern | File matcher. Use `*.json;*.jsonl` for mobile Logger data. |
| Include subfolders | Must be enabled for normal phone sync folders. |
| Logger database path | Target SQLite database. Default is `<LIFEPIM_DATA>\logger\logger.sqlite`. |
| Duplicate detection | Default is metadata and content hash. |
| Unknown record types | Keep unknown records and warn rather than failing the whole run. |

If the default logger process has a blank source folder, LifePIM fills it from Logger settings when the process is opened or run:

1. `logger_mobile_source_path`, if set.
2. Otherwise `logger_raw_data_root`.

The import process leaves source files in place by default.

On this app configuration, `<LIFEPIM_DATA>` means the configured LifePIM data folder, not the source-code repository. For example, with:

```text
user_folder = D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data
data_folder = D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA
```

the logger database path resolves to:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA\logger\logger.sqlite
```

If an older page shows `D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\lifepim_logger.db`, that is the previous logger-processing database location. The top-level Data process uses `DATA\logger\logger.sqlite`.

The optional `logger_database_path` setting must be a SQLite file path ending in `.db`, `.sqlite`, or `.sqlite3`. If it contains a folder path, LifePIM ignores it and uses the default `DATA\logger\logger.sqlite` location.

## Raw File Layout

The raw file root normally looks like:

```text
<raw root>/
    <device-folder>/
        phone_usage/
            2026-08-05.jsonl
            2026-08-06.jsonl
        app_catalog/
            app_catalog_2026_08_05.json
        movement/
            ...
        device/
            ...
        service/
            ...
```

The import process scans recursively when `Include subfolders` is enabled.

## Databases

### Main LifePIM Database

The main `lifepim.db` stores operational metadata:

| Table | Purpose |
| --- | --- |
| `lp_logger_device` | Known logger devices and their local folder names. |
| `lp_logger_sync_run` | Phone-to-desktop sync runs. |
| `lp_logger_sync_file` | Uploaded raw file metadata. |
| `lp_process` | Saved Data process definitions. |
| `lp_process_run` | One row per preview, incremental run, or rebuild. |
| `lp_process_file` | Durable file-level processing state. |
| `lp_process_run_file` | Per-run file results. |
| `lp_process_run_message` | User-facing process messages. |

The main database does not store the high-frequency raw logger payloads.

### Logger SQLite Database

The Data process writes raw records to:

```text
<LIFEPIM_DATA>\logger\logger.sqlite
```

Main raw tables:

| Table | Purpose |
| --- | --- |
| `raw_logger_record` | One preserved source JSON record per imported record. |
| `raw_mobile_app_usage` | App usage and phone usage events. |
| `raw_installed_application` | App catalogue / installed app records. |
| `raw_location_sample` | Location-like records, when present. |
| `raw_device_state` | Device state, screen, battery, and network-like records. |
| `raw_unknown_record` | Records retained because no known route matched. |

The schema also still contains older derived tables such as `ingest_file`, `mobile_app_usage_sample`, `desktop_window_sample`, `application_catalog`, and `activity_session`. The current top-level Data process imports into the raw tables first. Normalisation and activity-session generation should be handled by later processing steps.

## Preview, Run, And Rebuild

### Preview Import

Preview scans matching files and records a preview run. It does not create or modify the logger SQLite database and does not move source files.

Use preview when checking whether the source folder and file pattern are correct.

### Run Import

Run Import executes the saved Data process in incremental mode:

1. Scans `Source folder` recursively.
2. Matches `*.json;*.jsonl` files.
3. Hashes files for duplicate detection.
4. Creates the logger SQLite database and raw tables if needed.
5. Imports new files.
6. Skips already imported files.
7. Keeps failed-file diagnostics in the process run.

Successful import creates rows in `raw_logger_record` and one or more routed raw tables.

### Rebuild Logger Database

Rebuild imports all matching source files into a temporary database, then swaps it into place if the rebuild succeeds. The previous database is retained by the database replacement helper.

Use rebuild when the raw logger schema or routing logic has changed and the database should be regenerated from source files.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Raw files show in Admin but import finds no files | Confirm the Data process `Source folder` points at the raw root and `Include subfolders` is enabled. |
| Data tab shows `<LIFEPIM_DATA>\logger\logger.sqlite` | This is a placeholder. The resolved path is shown on `Data > Processes` as `Target database`; normally it is `<user_folder>\DATA\logger\logger.sqlite`. |
| `.jsonl` files are not imported | Use `*.json;*.jsonl` as the file pattern. |
| Run button fails with missing source folder | Open `Data > Processes > Edit Configuration` and set `Source folder` to the Logger raw-data root. |
| Database exists but activity sessions stay at zero | The Data process imports raw tables only. Activity-session derivation is separate legacy/future processing. |
| `View Logger Tables` shows no objects | Run Import first, then click `View Logger Tables` so the Data catalogue scans `logger.sqlite`. |
| Re-running creates no new rows | This is expected when duplicate detection finds the same file metadata or content hash. |

## Supported Record Routing

The Data process detects record types from explicit fields, key names, and file paths.

| Input shape | Target table |
| --- | --- |
| App usage events, phone usage snapshots, package usage rows | `raw_mobile_app_usage` |
| Installed app / app catalogue records | `raw_installed_application` |
| Location-like records with latitude and longitude | `raw_location_sample` |
| Device state, screen, battery, or network-like records | `raw_device_state` |
| Anything else | `raw_unknown_record` |

Unknown records are retained so the raw database can be reprocessed later when new routes are added.
