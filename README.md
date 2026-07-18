# LifePIM Desktop

LifePIM Desktop is a local-first personal information manager for notes, tasks,
calendar events, files, media, audio, places, contacts, money records, and
related project data.

The current desktop app is a Flask web application that runs on your PC and
uses a local SQLite database. The current entry point is `src/app.py`; on
Windows the expected launcher is `src/RUN_DESKTOP.BAT`.

LifePIM Desktop is a standalone tool. It does not require the mobile app,
cloud sync, or LifePIM.com to run. When you want phone access, LifePIM Pocket
can be paired as a mobile companion over the local network using the Pocket API
served by Desktop through Caddy HTTPS.

## Current Status

This is active v3 desktop development. The web UI is usable for local browsing
and editing across the main LifePIM areas, but the data/bootstrap path is still
developer-oriented and machine-specific in places.

Working at a high level:

- Local Flask app served at `http://127.0.0.1:9741`
- Optional LAN companion sync for LifePIM Pocket through
  `https://192.168.1.99` via Caddy, with Waitress kept loopback-only
- Overview dashboard with recent notes, tasks, and calendar context
- Top-level modules for Calendar, Goals, Tasks, How, Notes, Data, Files, Media,
  Audio, 3D, Money, People, Places, Apps, Admin, Links, and Projects
- SQLite-backed data access for the current desktop database
- Notes, calendar, media, audio, files, contacts, money, links, projects, and
  settings routes/templates are present
- Search across LifePIM areas, with optional note-content search
- Media browsing and event clustering, audio playlist/player views, calendar
  views, notes list/view/edit screens, and admin/settings screens
- Importer v1 framework for declarative imports into contacts/files/media and
  raw/mapped table loaders

Known rough edges:

- `src/init_database.py` is destructive and recreates the configured database.
- Some source paths in config/load scripts are still local-machine paths.
- Runtime configuration is mostly still driven by `src/common/config.py`.
- Incremental refresh jobs are not yet clean production sync jobs.

## Screenshots

Latest v3 screenshots are in `doc/`:

- [Audio player](doc/lifepim_ui_tab_layout_03_audio_player.png)
- [Calendar image view by date](doc/lifepim_ui_tab_layout_03_cal_image_view_by_date.png)
- [Media browse events](doc/lifepim_ui_tab_layout_03_media_browse_events.png)
- [Note view](doc/lifepim_ui_tab_layout_03_note_view.png)
- [Notes list](doc/lifepim_ui_tab_layout_03_notes_list.png)
- [Calendar](doc/lifepim_ui_tab_layout_03_calendar.png)

Older layout references are also kept in `doc/`.

## Setup

From the repository root:

```bat
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The Windows launcher expects the virtual environment at:

```text
<repo root>\.venv\Scripts\python.exe
```

`INSTALL.BAT` is only a minimal legacy helper. Prefer `requirements.txt` for a
repeatable environment.

## Configuration

Main configuration currently lives in:

```text
src\common\config.py
```

Important values include:

- `user_folder`
- `DB_FILE` / `db_name`
- `base_url`
- `port_num`
- `PATH_ALIASES`
- `etl_folders_csv`
- `etl_rules_csv`

The current default app URL is:

```text
http://127.0.0.1:9741
```

The current default sample database path in `src/common/config.py` points at:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\lifepim.db
```

Change the config before bootstrapping a different machine or data profile.

## Run

Recommended Windows launcher from the repository root:

```bat
src\RUN_DESKTOP.BAT
```

This starts `src/app.py` with `.venv\Scripts\python.exe`, waits briefly, and
opens the browser at `http://127.0.0.1:9741`.

Manual run from the repository root:

```bat
.\.venv\Scripts\python.exe src\app.py
```

Manual run from `src`:

```bat
cd src
..\.venv\Scripts\python.exe app.py
```

The old instruction `python web_server.py` is obsolete.

## Database Bootstrap

Only run this when you want to rebuild the configured SQLite database from
scratch:

```bat
cd src
..\.venv\Scripts\python.exe init_database.py
```

`init_database.py` deletes the configured `DB_FILE` if it exists, recreates the
base schema, applies module schemas, runs the current test/sample loaders, and
refreshes folder/project mapping data. Do not run it against a database you want
to preserve.

More operational detail is in [doc/deploy.md](doc/deploy.md).

## Mobile Companion

LifePIM Desktop remains the standalone desktop application and source of the
local SQLite-backed data. LifePIM Pocket is optional and should be treated as a
LAN companion, not as a required service or public cloud client.

The companion setup requires:

- Desktop running Waitress on `127.0.0.1:9741`.
- Caddy listening on the Desktop LAN IP, currently `192.168.1.99`, and reverse
  proxying HTTPS traffic to Waitress.
- Pocket configured with `https://192.168.1.99`; HTTP Pocket API access is not
  supported for normal use.
- Pocket built with the public Caddy local root certificate for this Desktop
  installation. The private Caddy CA key stays on the Desktop machine and must
  not be copied into the mobile project or committed.
- A logged-in Desktop user creating a one-time Pocket pairing code under
  Trusted devices. Pocket registration uses that code plus the device identity,
  then sends `Authorization: Bearer <device_token>` and
  `X-LifePIM-Device-ID: <device_id>` on API calls.

Pocket currently syncs with Desktop through explicit directions:

- `Sync Mobile to LAN Server` uploads local Pocket changes to Desktop through
  `/api/pocket/v1/sync/push`.
- `Sync from LAN Server` reads Desktop's manifest from
  `/api/pocket/v1/sync/manifest` and downloads item content from
  `/api/pocket/v1/items/<item_id>`.

Desktop rejects unauthenticated or revoked devices, scopes manifest and item
access to the paired user, limits sync payload size, and returns conflicts when
Desktop and Pocket have both changed a note and Desktop cannot safely accept the
mobile overwrite. More detail is in [doc/network.md](doc/network.md).

## Per-User File Roots

Notes are user-owned in the database and new note files are also separated by
user on disk. Existing `duncan` note and project-folder settings are preserved
so the production desktop login continues using the current folders.

New users get a default root under:

```text
N:\duncan\LifePIM_Data\DATA\lan_users\<username>
```

LifePIM creates these subfolders for new users:

```text
notes
projects
lists
```

Only the `duncan` account uses the full legacy project list and project-folder
mapping by default. Other users start with an editable `Home`, `Work`, `Family`,
and `Fun` project list, and new notes go into that user's `notes` root unless a
project folder mapping is explicitly added. Media and audio remain global.

## Tests

Run the unit tests from the `tests` folder:

```bat
cd tests
..\.venv\Scripts\python.exe run_tests.py
```

For a quick app import check from the repository root:

```bat
.\.venv\Scripts\python.exe -m py_compile src\app.py
```

## Repository Layout

```text
src\app.py                  Flask app entry point
src\RUN_DESKTOP.BAT         Windows launcher
src\common\                 shared config, data, search, settings, helpers
src\modules\                feature modules and Flask blueprints
src\templates\              shared templates
src\static\                 CSS and JavaScript
src\lifepim\importer\       importer framework
src\lifepim\targets\        importer-backed targets
data\                       CSV seed/config data
tests\                      unit tests and current sample/bootstrap loaders
doc\                        notes, deployment docs, and screenshots
scripts\                    development and migration utilities
```

## Importer v1

Intent: keep import scripts tiny and declarative. Your script specifies what to
import, from where, how to map it, and the stable key. LifePIM core handles IDs,
upserts, tombstones, and logging.

Steps:

1. Pick the target domain: `contacts`, `files`, `media`, or a raw table.
2. Define a mapping: target field to source column or transform.
3. Choose a stable key: `source_uid` or `sha256`.
4. Pick mode: `snapshot`, `authoritative`, or `merge`.
5. Dry-run first.

What gets overwritten:

- Importer targets: fields written by the writer are overwritten on upsert.
  `source_system`, `source_uid`, and `imported_*` fields are also updated each
  run.
- `snapshot` mode: previously imported rows for the same `source_system` are
  marked `is_deleted=1`.
- `authoritative` plus tombstone: rows missing from the current feed are marked
  `is_deleted=1`.
- `merge` mode: only provided fields are updated; no deletes or tombstones.

Be careful:

- A wrong key can overwrite unrelated entities. Use a stable key and prefer
  `sha256` for files.
- `snapshot` and `authoritative` can mark many rows deleted if the feed is
  incomplete.
- `load_tbl` is a raw insert with no de-duplication or stable IDs. Use it only
  for simple append-only tables.

Python usage examples:

```python
import common.import_tools as mod_tool

# CSV -> contacts (importer-backed)
mod_tool.load_csv(
    tbl="lp_contacts",
    fname="contacts.csv",
    map={
        "source_uid": "ContactID",
        "display_name": "Name",
        "email": "Email",
        "phone": "Phone",
    },
    key="source_uid",
    mode="snapshot",
    source_system="contacts_csv",
    dry_run=True,
)

# SQLite -> audio (raw copy)
mod_tool.load_tbl(
    tbl="lp_audio",
    src_db="filelist.db",
    src_tbl="tbl_files",
    cols_to_insert=["file_name", "size"],
    select_named="select metadata_filename, metadata_file",
)

# SQLite -> files (mapped copy with transforms)
mod_tool.load_tbl_mapped(
    tbl="lp_files",
    src_db="filelist.db",
    src_tbl="tbl_files",
    map={
        "path": "path",
        "size": ("size", "to_int"),
        "mtime_utc": ("mtime", "parse_dt_utc"),
        "file_type": "type",
    },
)
```
