
# LifePIM Desktop — Simpler Data Tab

## Intent

Simplify the LifePIM **Data** tab so that it answers a straightforward question:

> **What structured data do I have, where is it, and what uses it?**

The current Data area has accumulated functionality for databases, files, processes, SQL, process runs and tasks. Much of this now overlaps with the newer LifePIM design:

* **Apps** describe executable programs/processes.
* **Tasks** describe work that needs to be performed.
* **HOWTOs** contain documentation and operating instructions.
* **Data** should describe and expose the actual data.

The Data tab should therefore become primarily a **data catalogue and lightweight data browser**.

It must not become a full database administration tool or SQL IDE.

---

# 1. New Top-Level Data Navigation

Replace the existing Data subtabs:

* Overview
* Databases
* File Sources
* Processes
* Objects
* Saved SQL
* Process Runs
* Tasks

with only:

* **Databases**
* **Tables**

The default `/data/` route should open or redirect to **Databases**.

Suggested routes:

```text
/data/
/data/databases
/data/databases/<id>
/data/tables
/data/tables/<id>
```

Existing routes may redirect appropriately where useful, but should no longer appear in the Data navigation.

---

# 2. Core Design Concept

Although the UI uses the friendly term **Database**, internally this concept should represent a generic **data source/container**.

A Data source can therefore be:

* SQLite database
* DuckDB database
* SQL Server database
* other supported relational database
* folder containing CSV files
* Excel workbook
* folder containing Parquet files
* other future structured-data containers

The internal implementation should therefore avoid assuming that every database is a conventional SQL database.

For example:

```text
Tax Database
Type: SQLite
Path: D:\Finance\tax.db

Tables:
    bank_transactions
    categorised_transactions
```

and:

```text
Bank Statements
Type: CSV Folder
Path: D:\Finance\BankStatements

Tables:
    transactions_2025.csv
    transactions_2026.csv
```

and:

```text
Tax Workbooks
Type: Excel
Path: D:\Finance\tax.xlsx

Tables:
    Transactions
    Categories
    Summary
```

All three should appear through substantially the same Data UI.

---

# 3. Database/Data Source Model

Retain existing useful database/source tables where practical rather than unnecessarily replacing them.

However, ensure the parent data-source record can support at least:

```text
id
name
source_type
location
description
area/project links if already supported
enabled
last_scanned_at
created_at
updated_at
```

`source_type` should support values such as:

```text
sqlite
duckdb
sqlserver
csv_folder
excel
parquet_folder
```

The implementation should be extensible so additional source adapters can be added later.

Do not design the database schema around only SQLite.

---

# 4. Source Adapters

Use a small adapter/service abstraction for discovering objects inside each source.

Conceptually:

```python
get_source_tables(source)
get_table_columns(source, table)
get_table_preview(source, table, limit=100)
get_table_metadata(source, table)
```

The UI should not need to care whether a table originated from SQLite, CSV or Excel.

Initial support should concentrate on formats LifePIM already understands or can support simply.

### SQLite

Discover tables/views from SQLite metadata.

### CSV Folder

Each CSV file in the configured folder is treated as a table.

Example:

```text
D:\Tax\
    bank_2025.csv
    bank_2026.csv
```

becomes:

```text
bank_2025.csv
bank_2026.csv
```

### Excel Workbook

Each worksheet is treated as a table.

Example:

```text
tax.xlsx
    Transactions
    Categories
    Summary
```

becomes three Data tables.

The architecture should make Parquet/DuckDB/etc. easy to add without changing the Data UI.

---

# 5. Databases Screen

The **Databases** screen is the catalogue of registered data sources.

Display a clean list/grid containing useful information such as:

```text
Name
Type
Location
Tables
Last Scanned
Description
```

Avoid presenting this as a large data-entry form.

Provide normal actions such as:

* Add Database
* Edit
* Remove
* Refresh/Scan

Where sensible, display friendly icons/type indicators for SQLite, CSV Folder, Excel, etc.

Clicking a database opens its Database Detail page.

---

# 6. Database Detail Page

The database detail page should primarily answer:

> What is this source and what tables/data objects are inside it?

Suggested structure:

## Header

Show:

```text
Name
Type
Location
Description
Last scanned
Table count
```

Provide:

```text
Refresh
Edit
Open Location
```

where applicable.

## Tables

Below the source information, show all discovered tables/objects.

Example:

```text
Table                       Rows        Type
------------------------------------------------
bank_transactions           23,456      Table
categorised_transactions    23,456      Table
tax_categories                  32      Table
```

Clicking a table opens the standard Table Detail page.

The same interface should work for CSV/Excel sources.

Example:

```text
Table                       Rows        Type
------------------------------------------------
transactions_2025.csv       12,034      CSV
transactions_2026.csv        8,442      CSV
```

---

# 7. Tables Screen

The **Tables** tab provides a cross-source catalogue of all known tables.

This is essentially the replacement for the current generic **Objects** concept.

Suggested columns:

```text
Table
Database
Type
Rows
Modified / Last Scanned
Description
```

Provide simple search/filtering by:

* table name
* database/source
* source type

The purpose is quick discovery.

For example, searching:

```text
transaction
```

might display:

```text
bank_transactions           Tax Database
categorised_transactions    Tax Database
transactions_2025.csv       Bank Statements
transactions_2026.csv       Bank Statements
```

Clicking any result opens Table Detail.

---

# 8. Table Detail Page

This should be one of the most useful Data screens.

Suggested tabs:

```text
Preview | Columns | Links | Details
```

---

## 8.1 Preview

Show the first **100 rows**.

This should be a simple readable grid.

Provide lightweight conveniences such as:

* horizontal scrolling
* sticky column headers if easy
* sensible NULL display
* row number
* basic table width handling

Do not attempt to build a full SQL/database editor.

Read-only is sufficient for the initial implementation.

For SQL databases, use something equivalent to:

```sql
SELECT *
FROM table
LIMIT 100
```

using the correct syntax for the source.

For CSV/Excel sources, load only enough data to display the preview where practical.

---

## 8.2 Columns

Show discovered column metadata.

Suggested fields:

```text
Column
Data Type
Nullable
Primary Key
Other metadata
```

Only show metadata actually supported by the source.

For CSV files where strong types are unavailable, inferred types are acceptable.

For Excel, inferred column names/types are acceptable.

---

## 8.3 Links

This tab connects Data back into the wider LifePIM system.

A table may be linked to things such as:

### Apps

Programs/processes that:

* read the table
* write the table
* rebuild it
* transform it
* analyse it

Example:

```text
Apps

Load Bank CSV
Categorise Transactions
Generate Tax Summary
```

### Tasks

Example:

```text
Tasks

Prepare 2026 Tax Return
Refresh Logger Database
```

### HOWTOs

Example:

```text
HOWTO

Import CSV into SQLite
Categorise Bank Transactions
Logger Processing Design
```

### Projects / Areas

Use existing generic LifePIM linking/collection mechanisms where possible rather than inventing a Data-specific relationship system.

The UI does not need sophisticated lineage in Version 1.

A simple list of related LifePIM objects is sufficient.

---

# 9. Links Between Apps and Data

The recent Apps redesign means executable data processing belongs under **Apps**, not Data > Processes.

Example:

```text
Data:
    logger.db
        location_samples
        app_usage
        device_events

Apps:
    Load Logger JSON
    Aggregate Logger Events

Tasks:
    Refresh Logger Database

HOWTO:
    LifePIM Logger Processing
```

The Data table may show:

```text
Used by Apps:
    Load Logger JSON
    Aggregate Logger Events
```

but running/configuring those applications belongs in the Apps tab.

Data therefore describes the **input/output resource**, not the execution procedure.

---

# 10. Remove Data > Processes

Remove **Processes** from the Data navigation.

Do not delete useful existing process/application information blindly.

Where existing Data processes correspond to executable programs, prepare the UI/data model so they can be represented or linked through the Apps system instead.

The important conceptual distinction is:

```text
DATA = what exists

APP = executable capability

TASK = something that needs doing

HOWTO = knowledge/documentation
```

Do not maintain a second independent process/application framework under Data.

---

# 11. Remove Data > Process Runs

Remove **Process Runs** from the top-level Data navigation.

Execution history belongs with the relevant executable App.

A table's Links/Details page may eventually show information such as:

```text
Last updated by:
    Load Logger JSON

Last run:
    2026-08-09 18:42
```

but this is linked metadata rather than a top-level Data workflow.

Existing process-run data should not be deleted merely as part of this UI cleanup.

---

# 12. Remove Data > Tasks

Remove **Tasks** from the Data navigation.

Tasks should use the central LifePIM Tasks system.

Data records/tables may link to Tasks through the standard relationship mechanism.

Do not maintain Data-specific Tasks.

---

# 13. Remove File Sources as a Separate Tab

Remove **File Sources** from the Data navigation.

File-backed structured data should appear as Databases/Data Sources.

Examples:

```text
Bank Statements
Type: CSV Folder

Tax Workbook
Type: Excel

Logger Raw Data
Type: JSON/Folder   [future if useful]
```

The source adapter determines how the contents are represented as tables.

This provides one consistent mental model:

```text
Database/Data Source
    -> contains Tables
```

rather than:

```text
Database
File Source
Object
```

being three separate concepts.

---

# 14. Saved SQL

Remove **Saved SQL** from the main Data tab navigation.

Do not necessarily delete existing Saved SQL functionality or data.

For this cleanup it may remain dormant/accessible via legacy route if needed.

Later it can be reconsidered as:

* a utility associated with a database/table,
* an App action,
* a HOWTO/code snippet,
* or a separate developer/admin feature.

Do not expand Saved SQL functionality as part of this work.

---

# 15. Overview

Remove the dedicated **Overview** subtab.

The Databases screen itself should provide enough overview information.

A small summary header is fine, for example:

```text
8 Databases
146 Tables
Last scanned: Today
```

but do not create another dashboard that duplicates the catalogue.

---

# 16. Existing Data Preservation

This work is primarily a **UI/conceptual simplification**, not an instruction to destructively remove existing database tables.

Important:

* Preserve existing process records.
* Preserve run history.
* Preserve saved SQL.
* Preserve existing data-source metadata.
* Avoid destructive database migrations unless clearly necessary.

Hide/deprecate old UI functionality first.

Where routes are removed, either:

* redirect to the appropriate new page, or
* leave the route available but remove it from primary navigation.

The objective is to simplify LifePIM without making rollback/data migration difficult.

---

# 17. Suggested Internal Terminology

Use:

```text
Data Source
Data Table
```

internally.

Use:

```text
Databases
Tables
```

in the UI.

This keeps implementation terminology accurate while retaining familiar user-facing terminology.

For example:

```python
DataSource
DataTable
DataSourceAdapter
```

rather than assuming every source is literally a SQL database.

---

# 18. Refresh / Discovery

Each Data Source should support a refresh operation.

Refresh should:

1. Inspect the configured source.
2. Discover current tables/files/sheets.
3. Update the LifePIM data catalogue.
4. Update metadata such as:

   * row count where reasonably inexpensive
   * columns
   * modified timestamp
   * source/table type
5. Mark the source's `last_scanned_at`.

Do not perform expensive full scans merely to show the screen.

If exact row counts are expensive, cached/unknown counts are acceptable.

---

# 19. Source Failure Handling

A missing/unavailable source should not break the Data page.

For example:

```text
Tax Database
D:\Finance\tax.db
Status: Unavailable
```

Likewise, a disconnected network drive or invalid workbook should show a useful status/error.

Keep the source registered so the user can fix its location rather than automatically deleting it.

---

# 20. UI Style

The Data area should feel like a **browser/catalogue**, not an admin configuration screen.

Prefer:

* compact lists
* searchable tables
* clear source names
* breadcrumbs
* small metadata summaries
* easy click-through

Avoid:

* giant edit forms
* excessive buttons
* showing implementation metadata by default
* duplicating functionality from Apps/Tasks/HOW

Typical navigation should feel like:

```text
Data
  > Databases
      > Tax Database
          > bank_transactions
              > Preview
              > Columns
              > Links
              > Details
```

---

# 21. Example — Tax Time

This is a useful reference use case for validating the design.

### Data Sources

```text
Bank Statements
Type: CSV Folder
Location: D:\Finance\Tax\Statements

Tax Database
Type: SQLite
Location: D:\Finance\Tax\tax.db
```

### Tables

Bank Statements contains:

```text
bank_2025.csv
bank_2026.csv
```

Tax Database contains:

```text
bank_transactions
categorised_transactions
tax_categories
```

### Apps

Elsewhere in LifePIM:

```text
Load CSV to SQLite

Input:
    Bank Statements/*.csv

Output:
    Tax Database.bank_transactions
```

and:

```text
Categorise Bank Transactions

Input:
    Tax Database.bank_transactions

Output:
    Tax Database.categorised_transactions
```

### HOWTO

Contains the explanatory documentation about:

* CSV layout
* how the import works
* categorisation rules
* troubleshooting
* background information

### Tasks

Contains actual work such as:

```text
Download 2026 bank statement
Run transaction import
Review uncategorised transactions
Submit tax return
```

Data itself does not own any of those procedures.

---

# 22. Example — LifePIM Logger

Another validation case:

```text
Logger Database
Type: SQLite
Location: <LifePIM logger database path>
```

Tables might include:

```text
location_samples
app_usage
screen_events
battery_samples
sensor_samples
sync_events
```

Clicking `app_usage` should show:

```text
Preview
Columns
Links
Details
```

Links may include:

```text
Apps:
    Load Logger JSON
    Aggregate Logger Activity

HOWTO:
    Logger Data Processing

Tasks:
    Refresh Logger Database
```

The actual **Load Logger JSON** operation should not require a Data > Processes screen.

---

# 23. Non-Goals

Do not turn this work into:

* a database administration suite
* a replacement for DBeaver/SSMS
* a full ETL framework
* a SQL IDE
* a data lineage platform
* an editable spreadsheet
* a task scheduler
* a duplicate Apps framework

Keep Version 1 deliberately small.

The primary capability is:

```text
REGISTER SOURCE
    ↓
DISCOVER TABLES
    ↓
BROWSE TABLE
    ↓
SEE WHAT IT LINKS TO
```

---

# 24. Implementation Order

## Phase 1 — Navigation Cleanup

* Change Data navigation to Databases / Tables.
* Make Databases the default.
* Remove old tabs from navigation.
* Preserve existing data/routes.

## Phase 2 — Unified Sources

* Treat database and file-backed structured sources consistently.
* Implement/refactor source adapter layer.
* Add CSV-folder and Excel concepts if not already supported.

## Phase 3 — Database Detail

* Show source metadata.
* Discover/list contained tables.
* Link through to Table Detail.

## Phase 4 — Tables Catalogue

* Create cross-source Tables list.
* Add search/filter.
* Link to Table Detail.

## Phase 5 — Table Detail

Implement:

```text
Preview
Columns
Links
Details
```

with a 100-row read-only preview.

## Phase 6 — LifePIM Links

Use existing LifePIM relationships where practical to surface:

* Apps
* Tasks
* HOWTOs
* Areas
* Projects

Do not create duplicate domain-specific relationship machinery unless required.

---

# 25. Acceptance Criteria

The work is complete when:

1. Data navigation contains only **Databases** and **Tables**.
2. `/data/` opens the Databases view.
3. Existing SQLite databases can be listed.
4. Clicking a database shows the tables contained in it.
5. File-backed structured sources can fit the same Database/Data Source concept.
6. A folder of CSV files can conceptually expose each CSV as a table.
7. An Excel workbook can conceptually expose each worksheet as a table.
8. Tables from all configured sources can be browsed from one Tables screen.
9. Clicking a table opens a detail page.
10. Table Preview displays up to 100 records.
11. Columns displays available schema information.
12. Links can display related Apps/Tasks/HOWTO/etc.
13. Details displays physical/source metadata.
14. Data > Processes is no longer part of primary navigation.
15. Data > Process Runs is no longer part of primary navigation.
16. Data > Tasks is no longer part of primary navigation.
17. File Sources is no longer a separate primary concept.
18. Existing legacy data is not destructively deleted.
19. The UI is noticeably simpler than the current Data Workbench.
20. Data now has one clear responsibility: **cataloguing and viewing LifePIM's structured data resources.**

## Design Principle

When deciding whether new functionality belongs in Data, use this test:

> **Does this describe the data itself, or does it describe something that happens to the data?**

If it describes the data itself, it probably belongs in **Data**.

If it performs an operation, it probably belongs in **Apps**.

If it describes something that must be done, it belongs in **Tasks**.

If it explains how or why something works, it belongs in **HOWTO**.

