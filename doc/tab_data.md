# Data Tab

The Data tab is the catalogue for database sources, file-backed data sources, discovered data objects, saved SQL, and scan tasks.

## Main Areas

- Overview: counts, quick actions, recent activity, and failed/stale items.
- Databases: registered database-like sources such as SQLite, CSV, Excel, DuckDB, SQL Server, Oracle, Fabric SQL, and ODBC.
- File Sources: registered folders or file collections for data files.
- Objects: discovered tables, views, sheets, CSV tables, and files.
- Saved SQL: reusable SQL text and object relationships.
- Tasks: connection tests, scans, and profiling/run placeholders.

The old generic `lp_data` legacy tab has been removed from the Data navigation and route code. Data catalogue records now live in the `d_data_*` tables managed by `src/modules/data/catalogue.py`.

## Projects

Data sources and data objects both have a `project` metadata field.

Project values are selected from the same project/sidebar list used by the left-hand main menu. The stored value is the project id, such as `health`, `fun/games`, or `proj/dev/lifepim`.

Project selection is available on:

- Add/edit database source.
- Add/edit file source.
- SQLite database import.
- Object metadata.
- Object search/filter.
- Saved SQL add/edit.
- Saved SQL search/filter.

The left-hand project sidebar filters the current Data subtab instead of resetting to the Data overview. For example, if the current page is Saved SQL and `family` is selected from the sidebar, the URL remains on Saved SQL and adds `?proj=family`.

Project filtering applies to:

- database source lists.
- file source lists.
- object lists.
- saved SQL lists.
- task lists where a task is linked to a source, object, or saved SQL with that project.
- overview counts and recent activity.

When a source is scanned, new objects inherit the source project. Existing objects keep their manually selected project; if an existing object has no project, a later scan can fill it from the source.

## Source Lists

Database and file source lists show:

- Name
- Type
- Host or path
- Database
- Project
- Environment
- Object count
- Last scanned
- Status
- Tags
- Actions

Source detail pages also show Project in the summary.

## Object Lists

Object lists show Project immediately after Schema/folder. Level is shown after Last seen.

The standard object list columns are:

- Favourite
- Object name
- Type
- Source
- Schema/folder
- Project
- Rows
- Columns
- Size
- Last seen
- Level
- Profile
- Quality
- Tags
- Actions

The same ordering is used for source-detail object lists and Saved SQL related-object lists where those fields are available.

## Saved SQL

Saved SQL records have a `project` metadata field stored on `d_data_saved_sql`.

When a Saved SQL row is linked to a source and no project is selected, the source project is used as the default. Otherwise, choose the project explicitly from the Saved SQL form.

The Saved SQL list shows Project immediately after Name so SQL snippets can be scanned by project before target source, purpose, tags, and run status.

## Row Counts

SQLite scans now collect row counts for tables automatically. Views still show a blank row count because counting arbitrary views can be expensive or fail.

CSV scans count data rows by counting file lines minus the header row. Excel scans currently store the number of sampled rows read for schema discovery, capped by the scanner sample size.

Unknown counts are displayed as blank in the UI instead of `None`.

## Object Preview

Preview is available for:

- SQLite tables/views
- CSV table objects
- Excel sheet objects

The preview route is:

- `/data/object/<object_id>/data`

Preview is read-only and shows up to 200 rows.

## Scanning

Source scan behavior:

- SQLite: reads tables/views from `sqlite_master`, columns from `PRAGMA table_info`, and table row counts with `COUNT(1)`.
- CSV: reads a sample for schema inference and stores one `CSV_TABLE` object.
- Excel: reads worksheets and stores one `EXCEL_SHEET` object per sheet.
- File Source: recursively scans matching files unless recursive scan is disabled.

Scan activity is stored in `d_data_task`, and source scan status fields are updated on completion or failure.
