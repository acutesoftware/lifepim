# Data Tab

This document records how the Data tab works today. It is a baseline for future changes, not a proposed design.

## Purpose

The Data tab is a simple registry of data sources. At present it mainly supports manually entered records and SQLite `.db` files. When a registered record points to a valid SQLite database file, the detail page can list that database's tables and preview the first 10 rows from a selected table.

## Storage

The tab is backed by the generic table definition in `src/common/config.py`:

```python
{'name':'lp_data', 'route':'data', 'display_name':'Data', 'col_list':['name','description', 'tbl_name', 'col_list', 'project']}
```

`lp_data` records use these fields:

- `name`: display name for the data source.
- `description`: free text description.
- `tbl_name`: currently used as either a table/source identifier or a SQLite database file path.
- `col_list`: free text column-list metadata.
- `project`: project/category value used for project filtering.

Like the other generic LifePIM tables, rows also have standard metadata columns added by database initialization, including `id`, `user_name`, and `rec_extract_date`.

## Main List

Route: `/data/`

Handler: `list_data_route()` in `src/modules/data/routes.py`

The list page:

- Loads the `lp_data` table definition through `get_table_def("data")`.
- Displays all configured columns from `col_list`.
- Supports project filtering when `proj` is present and the table has a `project` column.
- Treats `any`, `All`, `all`, `ALL`, and `spacer` as no project filter.
- Sorts in memory after loading rows from SQLite.
- Defaults to sorting by `name` ascending.
- Allows column-header sorting with `sort` and `dir` query parameters.
- Paginates with `cfg.RECS_PER_PAGE`.

Template: `src/modules/data/templates/data_list.html`

The page provides links for:

- Add Data
- Import Databases
- View
- Edit
- Delete

## Add and Edit

Routes:

- `/data/add`
- `/data/edit/<item_id>`

Handlers:

- `add_data_route()`
- `edit_data_route()`

The add/edit form is generated from the configured `lp_data` column list using `build_form_fields()`.

Current form behavior:

- Fields containing `date` use an HTML date input.
- `description`, `content`, `col_list`, and `path` are rendered as textareas.
- Other fields are rendered as text inputs.
- On add, `project` defaults to the current `proj` query value, or `General`.
- On edit, all configured field values are read from the submitted form and written back to `lp_data`.

Template: `src/modules/data/templates/data_edit.html`

## Delete

Route: `/data/delete/<item_id>`

Handler: `delete_data_route()`

Delete calls the shared `db.delete_record()` helper for the `lp_data` row, then redirects back to the list page.

The delete link uses a browser confirmation prompt.

## Detail View

Route: `/data/view/<item_id>`

Handler: `view_data_route()`

The detail page shows all configured `lp_data` columns in a simple table.

If the row's `tbl_name` value is a path to an existing SQLite database, the page also shows a SQLite browser area:

- The left column lists SQLite tables from `sqlite_master`.
- Selecting a table reloads the same view route with `?table=<name>`.
- The right column previews the selected table.
- The preview uses `SELECT * FROM "<table>" LIMIT 10`.

Template: `src/modules/data/templates/data_view.html`

SQLite detection is intentionally simple:

- The file path must exist.
- `sqlite3.connect(path)` must succeed.
- `SELECT name FROM sqlite_master LIMIT 1` must succeed.

## Database Import

Routes:

- `/data/import-db`
- `/data/import-db-folder`

Handlers:

- `import_data_db_route()`
- `import_data_db_folder_route()`

Template: `src/modules/data/templates/data_import_db.html`

The import page supports two paths:

1. Paste one SQLite database path per line.
2. Provide a folder path and recursively scan for `.db` files.

For each imported `.db` file, the code creates one `lp_data` record:

- `name`: filename without extension.
- `description`: `SQLite database`.
- `tbl_name`: full file path.
- `col_list`: blank.
- `project`: current project value, or blank.

The importer only checks the file extension. It does not validate that each imported path is a readable SQLite database at import time. Validation happens later on the detail page.

## Search Integration

Global search includes `lp_data` via `common.search.search_all()`.

Searchable columns are:

- `name`
- `description`
- `tbl_name`
- `col_list`

Search results link to `data.view_data_route`.

Unlike Audio and Media, the Data tab does not currently have a specialized search-results layout. Data search matches are shown in the generic search results table.

## Project Behavior

The Data tab uses the `project` text column directly. It does not use folder mapping or `dim_folder`.

On the list page, if a project is selected, rows are filtered with:

```sql
lower(project) = lower(?)
```

On add/import, the current project is stored into the new record when available.

## Current Limitations

- The tab is a registry, not a general-purpose data explorer.
- `tbl_name` is overloaded: it can describe a table/source name, but for SQLite imports it stores a database file path.
- SQLite previews are read-only.
- SQLite preview always shows only the first 10 rows.
- SQLite preview has no filtering, sorting, schema detail beyond column names, or export.
- Imported `.db` paths are not validated during import.
- List sorting is done in Python after loading all matching rows, then pagination is applied.
- There is no deduplication when importing the same database path multiple times.
- There is no specialized Data search page yet.
