# LifePIM Desktop Tech Notes

Short implementation notes for programmers. Keep this file direct: where data lives, which routes/templates matter, and any non-obvious behavior.

## App Layout

- Entry point: `src/app.py`.
- Main layout template: `src/templates/layout.html`.
- Top tabs come from `TABS` in `src/common/config.py`.
- Most simple CRUD tabs are backed by `table_def` in `src/common/config.py`.
- Standard `table_def` tables include `id`, listed columns, `user_name`, and `rec_extract_date`.
- Settings are stored in `sys_settings`, managed by `src/common/settings.py`.
- Settings UI route: `/admin/settings`, implemented in `src/modules/admin/routes.py`.

## Media Tab

- Blueprint/routes: `src/modules/media/routes.py`.
- Main template: `src/modules/media/templates/media_explorer.html`.
- Main route: `/media/`, function `media_explorer_route`.
- Media records come from `lp_media`, joined to:
  - `lp_media_meta` for taken date, dimensions, duration, camera metadata.
  - `lp_media_tags` and `lp_tags` for tags.
  - `lp_album_items` / `lp_albums` for albums.
  - `lp_event_items` / `lp_events` for media event clusters.
- Pagination uses `IMAGES_PER_PAGE` from `src/common/config.py`.

### Media Files and Thumbnails

- The database stores file metadata and paths, not thumbnail image blobs.
- Thumbnail grids use the real media file through `GET /media/file/<media_id>`.
- `media_file_route()` resolves the path and returns `send_file(full_path)`.
- Browser thumbnails are normal `<img>` or `<video>` elements styled with CSS (`object-fit: cover` or `contain`).
- If an image is missing on disk, `/media/file/<media_id>` returns `404`.

Example thumbnail HTML:

```html
<img src="/media/file/123" alt="photo.jpg" loading="lazy">
```

### Media Path Resolution

- `_build_media_path(item)` handles both styles:
  - `path` already points to an existing file.
  - `path` is a folder and `filename` is joined to it.
- `Open folder` uses `/media/folder/<media_id>`, which opens the containing folder on the host OS.

### Media Events

- `Rebuild events` writes only Media event tables:
  - `lp_events`
  - `lp_event_items`
- It does not create Calendar events in `lp_calendar_events`.
- Media event clustering groups media by capture/modified time gaps.

## Top Tab Data Map

These are the main data tables for each top tab. Some tabs also use helper tables noted below.

### Overview

- Route: `/`
- No primary table.
- Aggregates recent data from Notes, Tasks, and Calendar.

### Calendar

- Table: `lp_calendar_events`
- Columns: `id`, `title`, `content`, `event_date`, `remind_date`, `area`, `user_name`, `rec_extract_date`
- Routes/templates: `src/modules/calendar/routes.py`, `src/modules/calendar/templates/`
- Calendar view settings are stored in `sys_settings`:
  - `calendar.view.events`
  - `calendar.view.files`
  - `calendar.view.usage`
- Calendar file/image overlays read:
  - normal files from `lp_files.mtime_utc`
  - images from `lp_media` using `lp_media_meta.taken_utc` when available, otherwise `lp_media.mtime_utc`

### Goals

- Table: `lp_goals`
- Columns: `id`, `parent_goal_id`, `title`, `description`, `goal_date`, `remind_date`, `area`, `user_name`, `rec_extract_date`

### Tasks

- Table: `lp_tasks`
- Columns: `id`, `title`, `content`, `area`, `start_date`, `due_date`, `user_name`, `rec_extract_date`

### How

- Table: `lp_how`
- Columns: `id`, `parent_how_id`, `title`, `description`, `area`, `user_name`, `rec_extract_date`

### Notes

- Table: `lp_notes`
- Columns: `id`, `file_name`, `path`, `folder_id`, `size`, `date_modified`, `area`, `user_name`, `rec_extract_date`
- Notes can also use area folder tables for default write locations.

### Data

- Table: `lp_data`
- Columns: `id`, `name`, `description`, `tbl_name`, `col_list`, `area`, `user_name`, `rec_extract_date`

### Files

- Table: `lp_files`
- Base columns: `id`, `filelist_name`, `path`, `folder_id`, `file_type`, `area`, `user_name`, `rec_extract_date`
- Importer-added columns may include: `entity_id`, `size`, `mtime_utc`, `sha256`, `source_system`, `source_uid`, `imported_run_id`, `imported_utc`, `is_deleted`, `deleted_utc`

### Media

- Table: `lp_media`
- Base columns: `media_id`, `path`, `filename`, `ext`, `media_type`, `size_bytes`, `mtime_utc`, `ctime_utc`, `hash`
- Importer-added columns may include: `entity_id`, `sha256`, `labels_json`, `faces`, `dominant_colors`, `source_system`, `source_uid`, `imported_run_id`, `imported_utc`, `is_deleted`, `deleted_utc`
- Helper tables:
  - `lp_media_meta`: `media_id`, `taken_utc`, `width`, `height`, `duration_sec`, `fps`, `codec`, `camera_make`, `camera_model`, `gps_lat`, `gps_lon`
  - `lp_tags`: `tag_id`, `tag`
  - `lp_media_tags`: `media_id`, `tag_id`, `created_utc`, `created_by`
  - `lp_albums`: `album_id`, `title`, `description`, `cover_media_id`, `album_type`, `created_utc`, `updated_utc`
  - `lp_album_items`: `album_id`, `media_id`, `sort_order`, `added_utc`, `added_by`
  - `lp_events`: `event_id`, `title`, `start_utc`, `end_utc`, `location_label`, `event_source`, `created_utc`
  - `lp_event_items`: `event_id`, `media_id`, `confidence`
  - `lp_smart_views`: `smart_view_id`, `title`, `description`, `filter_json`, `sort_json`, `created_utc`, `updated_utc`

### Audio

- Table: `lp_audio`
- Columns: `id`, `file_name`, `path`, `folder_id`, `file_type`, `size`, `date_modified`, `artist`, `album`, `song`, `area`, `user_name`, `rec_extract_date`
- Helper tables:
  - `lp_audio_playlists`
  - `lp_audio_playlist_items`

### 3D

- Table: `lp_3d`
- Columns: `id`, `file_name`, `path`, `folder_id`, `size`, `date_modified`, `area`, `user_name`, `rec_extract_date`

### Money

- Main table: `lp_money_plans`
- Typical columns: `plan_id`, `title`, `domain`, `description`, `estimated_cost`, `priority`, `status`, `target_date`, `created_at`, `updated_at`
- See `src/modules/money/dao.py` for exact query/write behavior.

### Contacts

- Main tables:
  - `lp_contacts`
  - `lp_contact_facts`
- `lp_contacts` is used for person identity.
- `lp_contact_facts` stores email, phone, notes, and other contact facts.
- See `src/modules/contacts/dao.py`.

### Places

- Table: `lp_places`
- Columns: `id`, `name`, `desc`, `address_street`, `suburb`, `postcode`, `state`, `country`, `gps_lat`, `gps_long`, `user_name`, `rec_extract_date`

### Apps

- Table: `lp_apps`
- Columns: `id`, `file_path`, `folder_id`, `title`, `icon`, `area`, `user_name`, `rec_extract_date`

### Admin

- Main route: `/admin/`
- Folder cache table: `dim_folder`
- Note area-folder rules are stored in `lp_area_folders` and managed from Notes.
- User history table: `sys_user_log`
- Settings table: `sys_settings`

### Agent

- Top tab exists in config.
- No primary data table is currently defined in `table_def`.

## Importer Tables

- Import run tracking: `lp_import_runs`
- Importer schema helper: `src/lifepim/importer/schema.py`
- Import writer targets:
  - contacts: `src/lifepim/targets/contacts.py`
  - files: `src/lifepim/targets/files.py`
  - media: `src/lifepim/targets/media.py`

## Link System

- Link table: `lp_links`
- Schema: `src/schema_links.sql`
- Runtime helpers: `src/common/links.py`
- UI scripts/templates: `src/static/links.js`, `src/templates/widgets/links_*`

# Systems

This section covers infrastructure used behind several UI modules rather than one
particular LifePIM tab.

## Database

### Main Database and Startup

The main application database is SQLite. `src/common/data.py` resolves its path in
this order:

1. `LIFEPIM_DB_FILE`, when the environment variable is set.
2. `common.config.DB_FILE`.
3. The legacy `common.config.db_name` value.
4. `lifepim.db` as a final fallback.

A relative path is resolved relative to `src/common`. Configuration loading has a
separate bootstrap step in `src/common/config.py`: it may briefly open the default
database to read `sys_settings` overrides, discover an overridden active database,
and then read overrides from that database. Those bootstrap connections are closed
immediately and are not the application's shared runtime connection.

Importing `src/app.py` opens the runtime connection by calling
`common.data._get_conn()` and then ensures the Areas, Projects, Collections,
Settings, Notes, How, and Content Catalogue schemas. This means `data.conn` is
normally populated before the blueprints are imported, although `_get_conn()` is
also lazy so command-line tools and tests can use the data layer without importing
the Flask application.

### Shared Connection Lifecycle

`src/common/data.py` owns a module-level variable named `conn`. It starts as `None`.
The first call to `_get_conn()` creates one `sqlite3.Connection`, stores it in
`data.conn`, and returns that same object on every later call in the process.

The connection is configured with:

- `sqlite3.Row` as `row_factory`, allowing both index and column-name access.
- `check_same_thread=False`, allowing the Python object to be called from a thread
  other than the one that created it.
- `PRAGMA foreign_keys = ON`.
- `PRAGMA busy_timeout = 5000`, so SQLite waits up to five seconds for a database
  lock instead of failing immediately.
- `PRAGMA journal_mode = WAL` where the database supports it, allowing readers and
  a writer to overlap more effectively than with the rollback journal.

The Flask request teardown handler logs exceptions but does not close, replace,
commit, or roll back the database connection. The connection therefore lives for
the lifetime of the server process. Restarting LifePIM closes it as part of process
shutdown and the next process creates a new one.

### Why the Connection Is Shared

The current design comes from LifePIM's desktop, single-database architecture. It
provides several practical benefits:

- all tabs use the same configured database and the same SQLite settings;
- schema checks and migrations can pass one connection through several helpers;
- a multi-step operation can deliberately share a transaction across service calls;
- callers do not repeatedly open SQLite files during one page request;
- tests can replace `common.data.conn` with an in-memory connection; and
- most service functions accept an optional `conn`, making the same code usable
  with the shared connection in production and an injected connection in tests or
  batch operations.

This is a process-wide connection, not a Flask request-local connection and not a
connection pool.

### Shared-Connection Audit

The following production files directly call `data._get_conn()` (or its `db` /
`main_data` alias), directly use `data.conn`, or provide a thin wrapper which falls
back to it. This list was audited from the current source tree.

Application and cross-cutting infrastructure:

- `src/app.py` — startup schema checks, overview queries, help/path reporting, and
  common template context.
- `src/core/security.py` — users, sessions, login attempts, trusted devices,
  permissions, and record-visibility checks.
- `src/data/processes/process_repository.py` — process definitions and run state in
  the main database unless a connection is injected.

Shared domain and utility layers:

- `src/common/areas.py`
- `src/common/collections.py`
- `src/common/content_catalog.py`
- `src/common/links_records.py`
- `src/common/media_migration.py` for the migration target
- `src/common/note_search_index.py`
- `src/common/projects.py`
- `src/common/search.py`
- `src/common/settings.py`
- `src/common/utils.py`, principally `sys_user_log`

Feature schemas, services, and data-access layers:

- `src/modules/apps/schema.py`
- `src/modules/apps/importers/icon_media.py`
- `src/modules/calendar/services/calendar_index.py`
- `src/modules/contacts/dao.py`
- `src/modules/data/catalogue.py`
- `src/modules/how/service.py`
- `src/modules/money/dao.py`
- `src/modules/tasks/schema.py`

Routes which query the shared connection directly or pass it to their service
layer:

- `src/modules/admin/routes.py`
- `src/modules/auth/routes.py`
- `src/modules/audio/routes.py`
- `src/modules/calendar/routes.py`
- `src/modules/collections/routes.py`
- `src/modules/contacts/routes.py`
- `src/modules/files/routes.py`
- `src/modules/goals/routes.py`
- `src/modules/links/routes.py`
- `src/modules/logger_api/routes.py`
- `src/modules/media/routes.py`
- `src/modules/notes/routes.py`
- `src/modules/notes/web_clip_routes.py`
- `src/modules/places/routes.py`
- `src/modules/pocket_api/routes.py`
- `src/modules/projects/routes.py`
- `src/modules/public/routes.py`
- `src/modules/three_d/routes.py`

`src/utils/importer.py` is the remaining legacy-style consumer: it passes
`data.conn` to the generic CRUD helpers. Those helpers accept `None` and resolve the
shared connection lazily, but new code should prefer `_get_conn()` or an explicitly
passed `conn` rather than depending on startup order.

### Connection-Passing Patterns

There are three patterns in the codebase:

1. Route code calls `_get_conn()` and performs a short query or transaction.
2. A service function accepts `conn=None` and uses the shared connection only when
   the caller did not inject one. This is the preferred reusable/testable pattern.
3. Older routes pass `data.conn` into generic helpers such as `get_data()`,
   `add_record()`, `update_record()`, and `delete_record()`. Those helpers fall back
   to `_get_conn()` when the argument is `None`.

Schema ensure-functions also accept the active connection. Several cache their
completed state by `id(conn)`, which avoids repeating table/index inspection during
normal requests while still allowing a separate in-memory test connection to be
initialised.

### Transactions, Commits, and Concurrency

SQLite uses its normal deferred transaction mode. Most write helpers execute their
statements and commit before returning. Larger operations pass one connection down
the call chain and commit at a deliberate boundary. Error paths which manage an
explicit transaction must roll it back.

Because the connection persists across requests, code must not assume that it can
always issue a bare `BEGIN`; another helper may already have started a transaction.
Nested work should use a SQLite `SAVEPOINT`, or the outer operation should own the
complete transaction. `area_folder_set_default()` is an example: it uses a
savepoint so changing the default folder remains atomic even when the shared
connection already has pending work.

There is a concurrency limitation in the current architecture. The production
Waitress launcher uses eight request threads. `check_same_thread=False` prevents
Python's thread-affinity exception, but it does not make overlapping transactions
on one connection independent. A commit affects the connection's entire current
transaction, regardless of which helper or request began it. Consequently:

- transactions should be short;
- filesystem/network work should occur outside an open database transaction where
  practical;
- related statements should use one explicit transaction or savepoint;
- callers should not leave uncommitted work on return; and
- future high-concurrency work should prefer a request-local connection (or a
  serialised database worker) rather than adding more unsynchronised use of the
  process-wide object.

WAL and `busy_timeout` reduce file-lock contention with other SQLite connections;
they do not isolate concurrent users of this same Python connection object.

### Connections That Are Deliberately Separate

Not every `sqlite3.connect()` call uses the shared application connection:

- `src/common/config.py` uses short-lived bootstrap connections for configuration
  overrides.
- `src/logger/database.py` owns the separate logger database and its checkpoint
  connection.
- `src/apps/files/inventory_db.py` and `src/apps/files/scanner.py` own the file
  inventory database used by the scanner.
- `src/lifepim/importer/` opens the import target/source for the lifetime of an
  import run.
- `src/common/media_migration.py` opens source databases separately while writing
  into the main target connection.
- `src/modules/data/catalogue.py` can open a separate read-only SQLite source being
  catalogued.
- `src/etl_folder_mapping.py`, `src/init_database.py`, `src/common/import_tools.py`,
  `src/common/if_sqlite.py`, and `src/common/INIT_ALL_DATA.py` are standalone
  maintenance/import utilities and manage their own connections.

These connections are separate because they address another database, run before
the normal application exists, need read-only/source isolation, or are command-line
processes rather than Flask request handlers.

## Sync

The visible Sync buttons currently belong to Notes. They all end at the same note
reconciliation engine, but the button location determines which folders are placed
in scope and which Area is supplied as fallback metadata.

### Common Reconciliation Engine

`_sync_note_rows()` in `src/modules/notes/routes.py` performs the file-to-database
reconciliation. For each folder in scope it:

- normalises paths without rewriting NAS/mirror aliases;
- scans `.md` files recursively unless explicitly asked to refresh only one folder;
- skips `Deleted` trees;
- matches an existing row by normalised folder path plus filename;
- reads file size, modification time, and supported YAML front matter;
- inserts new `lp_notes` rows and updates changed rows;
- maintains `dim_folder`, `folder_id`, and the cached note-content search index;
- detects a simple rename when one file disappeared and one same-sized file
  appeared in the same folder;
- ignores duplicate database rows after the first path/filename match; and
- removes a database row only after a complete scan confirms the file is missing.

Source Markdown files are never deleted by sync. Before pruning missing database
rows, sync stats the root again so a disconnected network drive or failed scan is
not mistaken for mass deletion. Individual unreadable files are skipped and do not
authorise removal.

Area precedence during sync is:

1. explicit modern `area:` / `area_id:` front matter;
2. the Area supplied by the selected/configured folder;
3. legacy `folder:`, `sidebar_tab:`, or project metadata for a new unmapped row.

Legacy metadata does not overwrite the Area of an existing row. This preserves a
manual cleanup, including `Remove from Area`, on later full syncs.

### Notes Header: Full Sync

Location: the Notes list header while viewing All Areas with no folder filter.
The button label is `Full Sync` and it posts to `POST /notes/sync` without an Area
or folder.

`full_sync_note_folders()` builds its roots from the configured Notes root plus the
roots containing enabled `default`, `include`, `archive`, and `output` Area-folder
rules. Parent roots subsume child roots so the same tree is not scanned repeatedly.
Every valid root is walked recursively, the `lp_note_folders` tree is rebuilt, and
all Markdown notes below it are reconciled. Area-folder mappings are selected by
the most specific matching path when a file has no explicit modern Area.

### Notes Header: Area Sync

Location: the Notes list header while a specific Area is selected. The button label
is `Sync` and the form posts the current `area` to `POST /notes/sync`.

The scope contains:

- every enabled folder rule for that Area with role `default`, `include`,
  `archive`, or `output`; and
- detected folders already represented by notes in that Area.

Overlapping paths are collapsed so a selected parent folder is scanned once rather
than scanning each child again. The selected Area is passed as the fallback for the
scoped folders. The folder index and all Markdown rows in those paths are updated.

### Notes Header: Folder Sync

Location: the Notes list header after navigating into a folder. The button label is
`Sync`; the form posts both the current Area (when present) and the exact folder
filter to `POST /notes/sync`.

Only that known folder is selected as a root, but its descendants are scanned
recursively. A detected external folder is accepted only when it is already known
inside the current Notes/Area scope. The current Area, if any, is used as fallback
metadata.

### Folders Panel: Linked Folder Sync

Location: the `Sync` button on an explicit `lp_area_folders` row. It posts to
`POST /notes/sync-folder/<area_folder_id>`.

This calls `_sync_note_rows()` directly for that configured path, recursively, with
the folder rule's `area_id` as fallback. The response reports scanned, inserted,
updated, renamed, unchanged, missing, and duplicate counts. It reconciles note rows
and `dim_folder`; unlike the broader scoped/full operation, it does not rebuild the
whole `lp_note_folders` hierarchy first.

### Folders Panel: Detected Folder Sync

Location: the `Sync` button on a `Detected from notes` row. It posts the Area and
folder path to `POST /notes/sync`.

The route first proves that the detected path is known in the current scope, then
indexes its folder tree and recursively reconciles its Markdown files. The selected
Area is the fallback. This is why syncing a detected folder can materialise its
notes into that Area even though the folder is not yet an explicit folder rule.

### Settings > Notes: Sync Notes

Location: `Admin > Settings > Notes > Sync notes from disk`. The form posts the
entered `notes_folder` to `POST /notes/sync` without an Area.

The entered folder becomes the scoped root and is scanned recursively. Because no
Area is forced, each file uses the most specific enabled Area-folder mapping;
explicit modern front matter still has first priority. The operation updates the
folder index, note metadata, missing-note reconciliation, and search index. It is a
scoped sync of the entered root, not automatically a full sync of every configured
root.

### Template View Sync

When the header is in Templates mode, the form includes `templates=1`. That flag is
used to discover the relevant folder scope. Once a folder is selected, the
filesystem reconciliation still processes every Markdown file in that folder; it
does not ignore normal notes merely because the current list is showing templates.

### Automatic Folder Change Check

Opening a Notes list can invoke `_auto_check_visible_note_folders()` once per
request. For the current folder, or for the enabled folder rules of the current
Area, it compares filesystem folder modification times with `lp_note_folders`.
Unchanged folders are not rescanned. A dirty folder refreshes its immediate files,
new child directories are indexed recursively, and vanished child folders are
marked missing. This is an incremental background check associated with viewing
Notes, not a visible Sync button and not a replacement for Full Sync after broad
external changes.

### Scope and Failure Rules

- A folder must exist and be inside a recognised Notes root, except that an already
  known detected external folder may be explicitly scoped.
- Parent paths suppress redundant child paths in one operation.
- A missing configured path is skipped by the multi-folder coordinator.
- A scan error is reported in the redirect message.
- Missing rows are pruned only inside the successfully scanned scope.
- Database changes are committed through the shared main connection; source files
  remain untouched.
- Sync activity is written to `sys_user_log` as `notes_sync`,
  `notes_full_sync`, or `notes_folder_check` where applicable.
