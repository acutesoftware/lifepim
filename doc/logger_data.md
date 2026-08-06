# LifePIM Logger Data

This document describes how LifePIM Desktop handles raw Logger files, how the files are loaded into SQLite, and which logger JSON files are not imported yet.

## Overview

LifePIM Logger data has two stages:

1. Raw file sync and storage.
2. Desktop-side processing into typed logger tables.

Raw files remain the source of truth. The processing database can be rebuilt from those files.

The Admin page entry point is:

```text
Admin > Logger > Load JSON to database
```

That button scans the configured raw source folders, hashes candidate files, imports new or changed files into `lifepim_logger.db`, updates app names, and rebuilds derived activity sessions only when imported data changed.

## Databases

### Main LifePIM database

The main `lifepim.db` stores Logger sync metadata only. It does not store the high-frequency usage samples.

Main DB tables used by the mobile sync API:

| Table | Purpose |
| --- | --- |
| `lp_logger_device` | Known logger devices and their safe local folder names. |
| `lp_logger_sync_run` | One row per mobile sync run. |
| `lp_logger_sync_file` | One row per uploaded raw file. Includes relative path, log type, destination path, size, and status. |

These tables are maintained by `src/modules/logger_api/routes.py`.

### Logger processing database

Parsed logger data is stored in a separate SQLite database:

```text
lifepim_logger.db
```

Default location: the same folder as the actual open main `lifepim.db` connection.

The Admin Logger page displays both:

```text
Main LifePIM DB
Processing DB
```

If the main DB still shows a `SAMPLE_DATA` path, that is the current app configuration for `lifepim.db`; the logger database follows that actual open DB path unless `logger_database_path` is explicitly set.

Logger processing DB tables:

| Table | Purpose |
| --- | --- |
| `logger_schema_version` | Logger DB schema version, independent of the main DB. |
| `ingest_file` | One row per discovered source file, including hash, size, status, record count, first/last timestamp, and error message. |
| `processing_run` | One row per load/rebuild action. |
| `application_catalog` | Friendly app names and stable app identifiers. |
| `mobile_app_usage_sample` | Parsed mobile app usage and screen events. |
| `desktop_window_sample` | Parsed Aggie desktop window/application observations. |
| `activity_session` | Derived sessions built from mobile and desktop samples. |

## Configuration

Settings are stored through the existing LifePIM settings system.

| Setting | Meaning |
| --- | --- |
| `logger_database_path` | Optional override for `lifepim_logger.db`. Blank means place it beside the actual main `lifepim.db`. |
| `logger_mobile_source_path` | Optional raw mobile Logger source folder. Blank means use the Logger raw-data root. |
| `logger_aggie_source_path` | Optional Aggie desktop logger folder. |
| `logger_session_gap_seconds` | Maximum gap between samples before starting a new session. Default: `60`. |
| `logger_minimum_session_seconds` | Drop sessions shorter than this. Default: `3`. |

The raw sync API also has settings for raw-data root, upload token, upload size, and sync logging.

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

The processing scan is recursive. Device ID is currently inferred from the first folder below the configured source root, for example `samsung-sm-a226b`.

Supported file extensions for discovery:

```text
.json
.jsonl
.csv
.tsv
.txt
```

Only some discovered files are parsed in Version 1. Unsupported raw files remain on disk and may still have main-DB sync metadata.

## File Discovery Rules

Discovery is implemented in:

```text
src/logger/ingest/file_discovery.py
```

Current source-type mapping:

| Path/name pattern | Source type | Importer |
| --- | --- | --- |
| `app_catalog`, `inventory`, `installed` | `mobile_app_inventory` | `MobileAppInventoryImporter` |
| `phone_usage`, `app_usage`, filename containing `usage` or `application` | `mobile_app_usage` | `MobileAppUsageImporter` |
| Aggie source root, `aggie`, or `window` | `aggie_window_usage` | `AggieImporter` |

Files outside these patterns are not loaded into `lifepim_logger.db` yet.

## Load JSON To Database

Admin action:

```text
Load JSON to database
```

Code path:

```text
src/modules/admin/routes.py
    -> LoggerService.refresh()
       -> discover_logger_files()
       -> hash each file
       -> importer for each source_type
       -> rebuild_application_catalog()
       -> rebuild_activity_sessions() when data changed
```

Import behavior:

| Case | Behavior |
| --- | --- |
| Same path, same hash, already imported | Skip. |
| Same path, changed hash | Delete prior typed rows through `ingest_file` cascade, then re-import. |
| Different path, same hash as imported file | Record a `superseded` diagnostic row and skip duplicate content. |
| Malformed file | Keep a failed `ingest_file` row with the error message. Other files continue importing. |
| No data changes | No duplicate samples or sessions are created. |

The Admin page shows failed files in the `Failed Source Files` table.

## Raw JSON Types Currently Loaded

### Mobile app catalog

Typical raw records:

```json
{"type":"app_catalog_started","capturedAt":"2026-08-05T04:21:00.183Z"}
{"type":"installed_app","capturedAt":"2026-08-05T04:21:00.183Z","packageName":"ai.perplexity.app.android","appName":"Perplexity"}
{"type":"app_catalog_finished","capturedAt":"2026-08-05T04:21:01.183Z"}
```

Importer:

```text
src/logger/ingest/mobile_app_inventory_importer.py
```

Target table:

```text
application_catalog
```

Field mapping:

| Raw field | Target column |
| --- | --- |
| `packageName`, `package_name`, `package`, `application_identifier` | `application_identifier`, `package_name` |
| `appName`, `application_name`, `app_name`, `label`, `name` | `application_name` |
| `capturedAt`, `capturedAtMillis`, timestamp variants | `first_seen_at_utc`, `last_seen_at_utc` |
| Complete app record | `metadata_json` |

Records without a package name, such as `app_catalog_started` and `app_catalog_finished`, are skipped rather than treated as failures.

### Mobile phone/app usage

Typical raw records:

```json
{"type":"phone_usage_event","capturedAt":"2026-08-06T00:00:51.829Z","event":"screen_off"}
{"type":"app_usage_event","capturedAt":"2026-08-06T00:29:10.479Z","eventTimeMillis":1785976141269,"eventType":"activity_resumed","packageName":"com.sec.android.app.launcher","appName":"One UI Home","className":"Launcher"}
{"type":"phone_usage_snapshot","capturedAt":"2026-08-06T00:29:10.494Z","apps":[{"packageName":"com.example.app","appName":"Example","lastTimeUsedMillis":1785976142269}]}
```

Importer:

```text
src/logger/ingest/mobile_app_usage_importer.py
```

Target table:

```text
mobile_app_usage_sample
```

Field mapping:

| Raw field | Target column |
| --- | --- |
| source folder, `device_id`, `device` | `device_id` |
| `eventTimeMillis`, `lastTimeUsedMillis`, `capturedAt`, `capturedAtMillis`, timestamp variants | `observed_at_utc` |
| `packageName`, `package_name`, `package`, `app` | `package_name` |
| `appName`, `application_name`, `app_name`, `label`, `name` | `application_name` |
| `className`, `activity_name`, `activity` | `activity_name` |
| `eventType`, `event`, `type` | `event_type` |
| `screen_state`, `screenState` | `screen_state` |
| Unmapped fields | `extra_json` |

`phone_usage_snapshot` records with an `apps` array are expanded so each app becomes a row in `mobile_app_usage_sample`.

Screen-off style records are kept even when they do not have a package name, because they terminate mobile sessions.

### Aggie desktop window usage

Typical raw row:

```text
observed_at_utc,device_id,process_name,application_name,window_title,is_idle
2026-08-05T01:00:00Z,desktop-1,Code.exe,Visual Studio Code,LifePIM,0
```

Importer:

```text
src/logger/ingest/aggie_importer.py
```

Target table:

```text
desktop_window_sample
```

Field mapping:

| Raw field | Target column |
| --- | --- |
| source folder, `device_id`, `device` | `device_id` |
| `observed_at_utc`, `timestamp_utc`, `observed_at`, `timestamp`, `datetime`, `time`, `date`, `ts` | `observed_at_utc` |
| `process_name`, `processName`, `process`, `exe` | `process_name` |
| `application_name`, `app_name`, `application` | `application_name` |
| `executable_path`, `path` | `executable_path` |
| `window_title`, `title` | `window_title` |
| `is_idle`, `idle` | `is_idle` |
| Unmapped fields | `extra_json` |

## Derived Tables

### Application catalog

`application_catalog` is built from inventory rows, mobile usage rows, and desktop rows.

Stable identifiers:

| Platform | Identifier rule |
| --- | --- |
| Android | Package name. |
| Windows | Normalized executable path, then process name, then supplied application name. |

Friendly names are resolved from app inventory first where possible, then from usage/window records.

### Activity sessions

`activity_session` is derived from `mobile_app_usage_sample` and `desktop_window_sample`.

Session rules:

| Rule | Behavior |
| --- | --- |
| Same device and same app within `logger_session_gap_seconds` | Continue the current session. |
| App changes | Close the previous session and start a new one. |
| Gap exceeds threshold | Start a new session. |
| Mobile screen-off/locked/stop/inactive event | Terminate the current mobile session. |
| Desktop idle sample | Terminate the current desktop session. |
| Duration below `logger_minimum_session_seconds` | Discard the session. |

For one-second style samples, the end time is the last sample time plus one second, capped by the configured session gap.

The deterministic session hash is based on:

```text
platform
device_id
source_type
application_identifier
start_at_utc
end_at_utc
```

It deliberately excludes database IDs, generated timestamp, friendly app name, and activity title.

## Timestamps

All timestamps stored in `lifepim_logger.db` are UTC strings in canonical form:

```text
YYYY-MM-DDTHH:MM:SS.sssZ
```

The UI/reporting layer converts UTC values to local display time. The database does not store Adelaide-local timestamps.

Supported timestamp inputs include:

| Format | Example |
| --- | --- |
| ISO UTC | `2026-08-06T00:29:10.479Z` |
| ISO with offset | `2026-08-06T09:59:10+09:30` |
| Epoch milliseconds | `1785976150479` |
| Epoch seconds | `1785976150` |

## Rebuild Buttons

### Load JSON to database

Safe normal operation. Scans source folders, imports new/changed files, skips unchanged files, and rebuilds sessions only when imported data changed.

### Rebuild Activity Sessions

Keeps imported samples and recalculates `activity_session`.

Use this after changing session thresholds or session-building rules.

### Rebuild Logger Database

Recreates the full `lifepim_logger.db` from raw source files using a temporary database, validates it, then swaps it into place. The previous database is retained as a timestamped backup.

Raw source files are not modified.

Use this if:

| Situation | Why rebuild |
| --- | --- |
| Importer rules changed significantly | Existing parsed rows may not reflect new rules. |
| Logger schema changed | Full derived DB should be regenerated. |
| Existing processing DB is suspected corrupt | Raw files remain the source of truth. |

## Raw JSON Files Not Loaded Yet

The mobile sync API accepts these log types:

```text
movement
phone_usage
device
service
app_catalog
```

Version 1 processing only loads app catalog, phone/app usage, and Aggie desktop window usage.

The following raw JSON categories are not yet imported into typed logger tables:

| Raw category | Current status | Future target |
| --- | --- | --- |
| `movement` JSON | Stored as raw files and sync metadata only. Not parsed. | `location_sample`, `walking_session`, `place_visit`, or similar derived tables. |
| Device state JSON | Stored as raw files and sync metadata only. Not parsed. | `device_state_sample`, charging sessions, screen/battery summaries. |
| Service/diagnostic JSON | Stored as raw files and sync metadata only. Not parsed. | Processing diagnostics or operational health tables. |
| Sensor JSON such as barometer, pressure, temperature, light, accelerometer, gyroscope, magnetometer | Stored as raw files if synced, but ignored by discovery/import. | `environment_sample`, `motion_sample`, sensor time-series tables, or aggregated summaries. |
| Notification JSON | Not imported. | `notification_event` if/when notification analysis is added. |
| Network JSON | Not imported. | `network_sample` or network activity summaries. |

These files should remain raw until there is a clear target schema and derived use case. Continuous sensor readings should normally stay as time-series data or aggregates; they should not automatically become calendar events.

## Adding A New Logger Source

To add another raw logger source:

1. Add a typed table to `src/logger/schema.py`.
2. Add source discovery logic in `src/logger/ingest/file_discovery.py`.
3. Add an importer under `src/logger/ingest/`.
4. Register the importer in `LoggerService`.
5. Add repository/status counts if the Admin UI should show them.
6. Add tests using temporary raw files and a temporary `lifepim_logger.db`.

For sensor data, start by deciding whether the target is:

| Target shape | Use when |
| --- | --- |
| Time-series sample table | Every observation matters, such as barometer or temperature readings. |
| Aggregated summary table | The calendar/report only needs daily/hourly min/max/average/count. |
| Derived interval table | The source describes a human activity interval, such as walking or charging. |

Calendar integration should later consume derived interval or summary tables, not raw JSON files directly.
