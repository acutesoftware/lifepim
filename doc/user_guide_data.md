# Data Tab User Guide

The Data tab is LifePIM's catalogue for external and internal data. It is not meant to replace the original application that owns the data. Its job is to help you register data sources, scan what is inside them, check that LifePIM can see the right tables/files, and then use those objects for reference, preview, saved SQL, or later processing.

## Goals And Intent

Use the Data tab when you want to:

| Goal | What the Data tab gives you |
| --- | --- |
| Find what data exists | A searchable catalogue of databases, files, tables, views, CSV files, Excel sheets, and process outputs. |
| Check a source is readable | Scan results, row counts, columns, task status, and a read-only preview for supported objects. |
| Add meaning | Area, tags, purpose, notes, favourite/hidden flags, and catalogue level. |
| Keep repeatable imports visible | Processes, process runs, file-level results, and messages. |
| Reuse useful queries | Saved SQL records linked back to the source tables they use. |

The common pattern is:

1. Load or register the source.
2. Scan or run the process.
3. Check the discovered objects and row counts.
4. Preview or inspect the data.
5. Add metadata so the data is useful later.
6. Use it from Objects, Saved SQL, or process run history.

## Scenario 1: Import Mobile Logger Data

### Intent

Use this when Logger files have synced from your phone and you want them loaded into the logger SQLite database for inspection and later processing.

The raw phone files remain the source of truth. The logger database can be rebuilt from those files.

### Load

1. Open `Admin > Logs > Logger`.
2. In `Recent Sync Activity`, confirm the phone sync completed.
3. In `Raw Files`, confirm files such as `phone_usage/*.jsonl` or `app_catalog/*.json` are visible.
4. Open `Data > Processes`.
5. Select `Import LifePIM Logger JSON`.
6. Check:
   - `Source folder` points at the raw logger root.
   - `File pattern` is `*.json;*.jsonl`.
   - `Target database` resolves beside the active `lifepim.db`, normally `<LIFEPIM_DB_DIR>\logger.sqlite`.
7. Click `Preview`.
8. If the preview finds the expected files, click `Run`.

To start over from raw files, use `Rebuild` instead of deleting process history manually.

### Check

1. Open `Data > Process Runs`.
2. Open the latest `Import LifePIM Logger JSON` run.
3. Check:
   - `Files found`
   - `Files processed`
   - `Files skipped`
   - `Files failed`
   - `Records written`
4. Review `File Results` for failed or skipped files.
5. Review `Messages` for warnings such as unknown record types.

### Use

1. Return to `Data > Processes`.
2. Click `View Logger Tables`.
3. LifePIM registers and scans the logger database as a Data database source.
4. Open `Data > Objects`.
5. Search for raw logger tables such as:
   - `raw_logger_record`
   - `raw_mobile_app_usage`
   - `raw_installed_application`
   - `raw_device_state`
   - `raw_unknown_record`
6. Open an object and click `View data` to preview up to 200 rows.
7. Add tags, area, notes, and purpose where useful.

## Scenario 2: Catalogue A SQLite Database

### Intent

Use this when you already have a SQLite database and want LifePIM to know what tables and views it contains.

Examples:

```text
C:\data\finance.sqlite
D:\research\places.db
<LIFEPIM_DB_DIR>\logger.sqlite
```

### Load

1. Open `Data > Databases`.
2. Click `Add database`.
3. Choose `SQLITE`.
4. In `File path`, browse to the SQLite file.
5. Optionally set:
   - `Connection name`
   - `Environment`
   - `Area`
   - `Tags`
6. Click `Save and scan`.

For several SQLite files at once:

1. Open `Data > Databases`.
2. Click `Import SQLite DBs`.
3. Paste one file path per line, or enter a folder path.
4. Choose an area if the databases belong together.
5. Click `Import Databases` or `Import Folder`.

### Check

1. Open `Data > Databases`.
2. Find the source row.
3. Check:
   - `Objects`
   - `Last scanned`
   - `Status`
4. Open the source detail page.
5. Confirm the expected tables and views are listed.
6. If the database changed, click `Scan`.

### Use

1. Open `Data > Objects`.
2. Filter by the source or search for a table name.
3. Open a table object.
4. Click `View data` for a read-only preview.
5. Promote important tables:
   - `Discovered`: seen by LifePIM.
   - `Registered`: known and useful.
   - `Managed`: important enough to maintain deliberately.
6. Add:
   - Display name.
   - Area.
   - Tags.
   - Purpose.
   - Notes.
7. If you often query the table, create a saved SQL record and link it to the object.

## Scenario 3: Inspect A CSV Or Excel File

### Intent

Use this when you receive a data file and want to quickly understand its columns and sample rows without importing it into a LifePIM feature table.

Typical examples:

```text
bank_transactions_2026.csv
health_export.xlsx
reading_list.csv
```

### Load

1. Open `Data > Databases`.
2. Click `Add database`.
3. Choose `CSV` or `EXCEL`.
4. Browse to the file.
5. Set `Connection name`, `Area`, and `Tags` if helpful.
6. Click `Save and scan`.

For CSV, LifePIM creates one `CSV_TABLE` object.

For Excel, LifePIM creates one `EXCEL_SHEET` object per worksheet.

### Check

1. Open the source detail page after scanning.
2. Check that the CSV table or expected Excel sheets appear.
3. Open each important object.
4. Review:
   - Column list.
   - Row count, if available.
   - Source path.
   - Last scanned timestamp.
5. If a sheet or file is missing, confirm the selected file is the intended one and rescan.

### Use

1. Click `View data` from the object page.
2. Review the first 200 rows.
3. Mark useful objects as `Registered`.
4. Assign an area such as `health`, `money`, `work`, or a project area.
5. Add notes explaining what the file contains and whether it is a one-off export or a recurring source.
6. Create saved SQL only when the source type supports useful SQL access for your workflow.

## Scenario 4: Catalogue A Folder Of Data Files

### Intent

Use this when the useful thing is a folder or collection of files rather than one database. This is for tracking where data lives and what files are present.

Examples:

```text
N:\duncan\LifePIM_Data\DATA\exports
D:\projects\research\data
C:\Users\you\Downloads\reports
```

### Load

1. Open `Data > File Sources`.
2. Click `Add file source`.
3. Enter:
   - `Source name`
   - `Source type`
   - `Root path`
   - `Environment`
   - `Area`
   - `Tags`
4. Leave `Recursive scan` enabled if subfolders matter.
5. Use include/exclude patterns if the folder is large.
6. Click `Save`.
7. On the source list, click `Scan`.

### Check

1. Open `Data > File Sources`.
2. Check the source row for:
   - Object count.
   - Last scanned.
   - Status.
3. Open the source detail page.
4. Confirm the expected files or file-like objects were discovered.
5. If too much noise appears, edit the source and add ignore or exclude patterns, then scan again.

### Use

1. Open `Data > Objects`.
2. Filter by source, area, or object type.
3. Mark important objects as favourites.
4. Hide noise that should not show up in normal browsing.
5. Add tags such as `export`, `archive`, `finance`, `research`, or `reference`.
6. Use the object metadata as a lightweight index of where important data files live.

## Checking Data Health

Use `Data > Overview` as the quick health check.

Look at:

| Panel | What to check |
| --- | --- |
| Database sources | How many database sources are registered. |
| File sources | How many folder/file sources are registered. |
| Discovered objects | Newly scanned objects that may need review. |
| Registered objects | Objects you have accepted as useful. |
| Managed objects | Important objects that should stay maintained. |
| Open or failed tasks | Scans or placeholders needing attention. |
| Processes | Whether repeatable processes, such as Logger import, have run successfully. |
| Attention Required | Failed scans or failed tasks. |

If something looks wrong, open the relevant source, process run, or task detail before editing metadata.

## Choosing Catalogue Levels

Use catalogue levels consistently:

| Level | Meaning |
| --- | --- |
| `DISCOVERED` | LifePIM found it, but you have not reviewed it yet. |
| `REGISTERED` | You know what it is and expect to use it again. |
| `MANAGED` | It is important and should be maintained deliberately. |

Do not promote everything. Let `DISCOVERED` absorb noise, and promote the objects that are actually useful.

## Saved SQL

Saved SQL is for documenting useful queries and linking them to the objects they use.

### Load

1. Open `Data > Saved SQL`.
2. Click `Add saved SQL`.
3. Enter:
   - Name.
   - Target source.
   - Area.
   - SQL text.
   - Purpose.
   - Tags.
4. Select related objects.
5. Click `Save`.

### Check

1. Open the saved SQL detail page.
2. Confirm the target source and related objects are correct.
3. Use `Copy SQL` or `Download .sql` if you want to run it externally.

### Use

Saved SQL is currently most useful as a catalogue and documentation layer. The `Submit as runner task` action creates a placeholder task; general SQL execution is not yet implemented in this version.

## Practical Rules

- Register sources before trying to use objects from them.
- Scan after adding or changing a source.
- Use `View data` to confirm the source is readable before adding lots of metadata.
- Use areas and tags early; they make the Data tab much easier to filter.
- Use `Registered` and `Managed` sparingly so important data stands out.
- For repeatable imports, prefer `Processes` and `Process Runs` over ad hoc manual steps.
