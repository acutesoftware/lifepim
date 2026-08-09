# LifePIM Data Locations and Backup

LifePIM sits on top of your data. It stores metadata, indexes, links, settings,
and launch information in SQLite, but most of your real files remain where they
already live.

In this setup there are two main storage locations:

- A fast local drive for SQLite databases and local generated files.
- A permanent NAS location for notes, lists, projects, raw LifePIM content, and
  long-term backup.

This is deliberate. SQLite is much faster and more reliable for interactive UI
work when it is on a local disk. Notes and other long-lived user files belong on
the NAS because that is the permanent source of truth.

## Current Example Paths

These are the effective paths in this setup.

| Purpose | Path |
| --- | --- |
| Local LifePIM root | `D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data` |
| Main metadata database | `D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\lifepim.db` |
| Main SQLite WAL files | `D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\lifepim.db-wal` and `lifepim.db-shm` |
| Current logger database | `D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\logger.sqlite` |
| Older logger database location | `D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA\logger\logger.sqlite` |
| Local data folder | `D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA` |
| Materialised App icons | `D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA\Media\imported\icons` |
| Local admin/logger raw area | `D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\admin\logged_data` |
| Local temporary imports | `D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\tmp_imports` |
| NAS LifePIM root | `N:\duncan\LifePIM_Data` |
| Main NAS data root | `N:\duncan\LifePIM_Data\DATA` |
| Notes root | `N:\duncan\LifePIM_Data\DATA\notes` |
| Lists root | `N:\duncan\LifePIM_Data\DATA\lists` |
| Projects / Areas root | `N:\duncan\LifePIM_Data\DATA\projects` |
| Logger raw source | `N:\duncan\LifePIM_Data\DATA\notes\logged_data\raw` |
| LAN user roots | `N:\duncan\LifePIM_Data\DATA\lan_users` |
| Suggested local-backup destination | `N:\duncan\LifePIM_Data\DATA\SQL\LifePIM_LOCAL_BACKUP` |

The important split is:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data
```

contains the fast local LifePIM databases and generated local support files.

```text
N:\duncan\LifePIM_Data
```

contains the durable user data and the backup target.

## What the Main Database Contains

The main database is:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\lifepim.db
```

It contains LifePIM metadata such as:

- notes table rows and note metadata
- Apps records, actions, Areas, import metadata, and icon references
- Calendar index tables
- Media index rows
- Audio index rows
- Data catalogue rows
- links, collections, settings, users, security metadata, and UI state

It does not contain the body of your markdown notes. Notes remain `.md` files on
the NAS.

SQLite can also create companion files:

```text
lifepim.db-wal
lifepim.db-shm
```

When LifePIM is running, these files are part of the live database state. A file
copy backup should include them, or LifePIM should be stopped before copying.

## What the Logger Database Contains

The current logger-processing database resolves to:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\logger.sqlite
```

It is separate from `lifepim.db` because logger records can be large and are
processed independently.

If an old screen or file shows:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA\logger\logger.sqlite
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\lifepim_logger.db
```

those are older/legacy logger database locations. In this setup, the current
default is beside the main `lifepim.db`.

The setting `logger_database_path` currently contains:

```text
N:\duncan\LifePIM_Data\DATA\notes\logged_data
```

That is a folder, not a SQLite file path. LifePIM ignores it for the logger
database location and falls back to:

```text
<LIFEPIM_DB_DIR>\logger.sqlite
```

which resolves to:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\logger.sqlite
```

The raw logger source files are separate and live on the NAS:

```text
N:\duncan\LifePIM_Data\DATA\notes\logged_data\raw
```

## What the NAS Contains

The NAS is the permanent store for user-authored LifePIM content.

For the main user `duncan`, the configured roots are:

| Content | Path |
| --- | --- |
| File root | `N:\duncan\LifePIM_Data\DATA` |
| Notes | `N:\duncan\LifePIM_Data\DATA\notes` |
| Projects / Areas | `N:\duncan\LifePIM_Data\DATA\projects` |
| Lists | `N:\duncan\LifePIM_Data\DATA\lists` |

Other LAN users use subfolders under:

```text
N:\duncan\LifePIM_Data\DATA\lan_users
```

For example:

```text
N:\duncan\LifePIM_Data\DATA\lan_users\marita\notes
N:\duncan\LifePIM_Data\DATA\lan_users\support\notes
```

When LifePIM imports or syncs Notes, it records metadata in `lifepim.db`, but
the markdown files stay in the NAS notes folder. Editing a note updates the
markdown file on the NAS and refreshes the database metadata.

## Materialised Media and Icons

LifePIM generally indexes media by path. It does not normally copy your photo or
video library into the local database.

One important exception is generated/imported support media, such as imported
App icons. Those are small files created by LifePIM so the UI can display them
reliably.

In this setup, imported executable icons are materialised here:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA\Media\imported\icons
```

The Apps table stores the icon reference as:

```text
/media/file/<media_id>
```

The matching `lp_media` row points at the actual `.ico` file in
`DATA\Media\imported\icons`.

That is why these files must be included in the local backup. Without them, the
Apps metadata may still exist, but the icon files would be missing.

## Why Data Is Split

The design is:

```text
Local disk:
    fast databases, indexes, generated support files

NAS:
    durable user-authored documents, notes, lists, projects, raw inputs,
    and backups of the local databases
```

The local database is a catalogue and working index. It makes the UI fast.

The NAS content is the permanent source of truth for files you care about long
term. LifePIM references those files; it should not casually move, rewrite, or
hide them.

For example:

- A Note row in SQLite points to a markdown file on `N:`.
- A Media row points to an image/video/audio file path.
- An App row points to an executable, project folder, command, or URL.
- A materialised App icon is a small generated file under local `DATA\Media`.

## Backup Requirements

To protect this setup, back up both sides:

1. NAS data should already be protected by the NAS backup process.
2. Local LifePIM data on `D:` must be copied to the NAS regularly.

The local backup must include:

- `lifepim.db`
- `lifepim.db-wal`
- `lifepim.db-shm`
- `logger.sqlite`
- any logger SQLite WAL/SHM files
- `DATA\Media\imported\icons`
- `DATA\logger` legacy/current support files
- `admin\logged_data` if used
- any other local generated files under the local LifePIM root

For a clean file-copy backup, stop LifePIM first. If LifePIM is running, copy
the `-wal` and `-shm` files as well as the `.db`/`.sqlite` files.

## Robocopy Backup Script

This script backs up the local LifePIM root to the NAS in a folder outside the
Notes tree:

```text
N:\duncan\LifePIM_Data\DATA\SQL\LifePIM_LOCAL_BACKUP
```

Create a file such as:

```text
D:\DATA_LLM\dev\lifepim-desktop\src\BACKUP_LOCAL_LIFEPIM_TO_NAS.bat
```

with:

```bat
@echo off
setlocal

set SRC=D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data
set DEST=N:\duncan\LifePIM_Data\DATA\SQL\LifePIM_LOCAL_BACKUP
set LOGDIR=%DEST%\logs

if not exist "%DEST%" mkdir "%DEST%"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo Backing up local LifePIM data
echo Source:      %SRC%
echo Destination: %DEST%
echo.
echo For the cleanest SQLite backup, stop LifePIM before running this script.
echo.

robocopy "%SRC%" "%DEST%\lifepim_desktop_data" /E /XJ /COPY:DAT /DCOPY:DAT /R:3 /W:5 /NP /TEE /LOG+:"%LOGDIR%\backup_local_lifepim.log"

set RC=%ERRORLEVEL%
echo.
echo Robocopy exit code: %RC%

if %RC% GEQ 8 (
  echo Backup failed. See %LOGDIR%\backup_local_lifepim.log
  exit /b %RC%
)

echo Backup complete.
exit /b 0
```

This creates a mirror-like copy under:

```text
N:\duncan\LifePIM_Data\DATA\SQL\LifePIM_LOCAL_BACKUP\lifepim_desktop_data
```

The script uses `/E` instead of `/MIR`. That means it copies all subfolders but
does not delete files from the backup destination if they disappear locally.
This is safer for a manual backup guide. Use `/MIR` only if you deliberately
want the destination to exactly match the source and are comfortable with
deletions.

## Optional Production Logs Backup

If running the packaged production app from:

```text
C:\apps\LifePIM_Prod
```

also back up its logs:

```bat
robocopy "C:\apps\LifePIM_Prod\logs" "N:\duncan\LifePIM_Data\DATA\SQL\LifePIM_LOCAL_BACKUP\prod_logs" /E /XJ /COPY:DAT /DCOPY:DAT /R:3 /W:5 /NP /TEE /LOG+:"N:\duncan\LifePIM_Data\DATA\SQL\LifePIM_LOCAL_BACKUP\logs\backup_prod_logs.log"
```

Logs are usually not authoritative user data, but they are useful for debugging
after a failure.

## Restore

To restore the main LifePIM metadata database:

1. Stop LifePIM.
2. Copy `lifepim.db` from the NAS backup back to:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\lifepim.db
```

3. If restoring from a live backup that includes WAL files, restore the matching
   `lifepim.db-wal` and `lifepim.db-shm` files from the same backup time.
4. Restart LifePIM.

To restore materialised App icons, copy:

```text
DATA\Media\imported\icons
```

back under:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA\Media\imported\icons
```

To restore Notes, restore the NAS notes folder from NAS backup:

```text
N:\duncan\LifePIM_Data\DATA\notes
```

Then run the Notes sync/materialisation tools if database metadata needs to
catch up.

## Quick Check Commands

Show the current configured main paths:

```powershell
cd D:\DATA_LLM\dev\lifepim-desktop
python -c "import sys; sys.path.insert(0, 'src'); from common import config as c; print(c.DB_FILE); print(c.data_folder); print(c.user_folder)"
```

Show the current logger database path:

```powershell
cd D:\DATA_LLM\dev\lifepim-desktop
@'
import sqlite3, sys
sys.path.insert(0, 'src')
from common import config as cfg
from logger.config import load_logger_config
conn = sqlite3.connect(cfg.DB_FILE)
conn.row_factory = sqlite3.Row
try:
    print(load_logger_config(conn=conn).database_path)
finally:
    conn.close()
'@ | python -
```

Open the materialised App icons folder:

```powershell
explorer "D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA\Media\imported\icons"
```

Open the suggested NAS backup destination:

```powershell
explorer "N:\duncan\LifePIM_Data\DATA\SQL\LifePIM_LOCAL_BACKUP"
```

## Summary

Think of the system this way:

```text
N:\duncan\LifePIM_Data
    Permanent user data and NAS backup area.

D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data
    Fast local LifePIM databases, indexes, generated support files,
    and local working metadata.
```

Back up the local `D:` LifePIM root to the NAS regularly. Keep the NAS data
backed up through the normal NAS backup process. Together, those two backups
cover both the durable source files and the fast LifePIM metadata/index layer.

## TODO From Path Audit

The current code/config/database audit found no other primary LifePIM metadata
database outside the documented local root, but it did find several confusing
or easy-to-miss locations. These should be cleaned up or explicitly included in
backup policy.

### Rename or Reconfigure `SAMPLE_DATA`

Current active config:

```text
user_folder = D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data
DB_FILE     = D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\lifepim.db
```

This is not just disposable sample data. It is the active local LifePIM data
root in this setup. The folder name is misleading and should be fixed.

TODO:

- Rename the local root to something less alarming, for example:

```text
D:\DATA_LLM\lifepim_desktop_data
```

- Or keep the folder but document clearly in Settings/Admin that this is the
  active local data root.
- Update `src/common/config.py`, `src/ETL_MAP_FOLDERS.BAT`,
  `src/BACKUP_PROD_to_NAS.bat`, docs, and any saved `config.DB_FILE`,
  `config.db_name`, `config.user_folder`, or `config.data_folder` overrides if
  the path is renamed.

### Consolidate Logger SQLite Paths

Current effective logger database:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\logger.sqlite
```

Other logger database files also exist:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA\logger\logger.sqlite
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\lifepim_logger.db
```

The Data catalogue currently has a `Logger SQLite` source pointing at the older
`DATA\logger\logger.sqlite` path.

TODO:

- Decide whether `DATA\logger\logger.sqlite` and `lifepim_logger.db` are
  archival backups or stale working files.
- Update the Data catalogue `Logger SQLite` source to point at the current:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\logger.sqlite
```

- Remove or archive old logger DB files after confirming they are no longer
  used.
- Fix the `logger_database_path` setting so it is either blank or a real SQLite
  file path. It currently contains a folder path:

```text
N:\duncan\LifePIM_Data\DATA\notes\logged_data
```

LifePIM ignores that as a database path and falls back to
`<LIFEPIM_DB_DIR>\logger.sqlite`.

### Back Up Local Temporary Uploads or Clean Them

CSV uploads through generic import helpers are saved under:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\tmp_imports
```

These are temporary import files, not authoritative records, but they can
contain private CSV data.

TODO:

- Include `tmp_imports` in the local backup until there is an automatic cleanup
  policy.
- Add cleanup for old import CSV files once imported records are safely stored.
- Add upload size and extension validation for CSV imports if not already
  enforced by the route.

### Network Log Location

`common.network_log` writes to:

```text
%LIFEPIM_NETWORK_LOG%
```

if set, otherwise:

```text
<current working directory>\lp_network.log
```

Depending on how LifePIM is launched, that can land in the repo root, `src`, or
the production folder.

TODO:

- Set `LIFEPIM_NETWORK_LOG` explicitly to a known backed-up location, for
  example:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\logs\lp_network.log
```

- Or include the relevant production/repo log folders in the backup script.

### Production App Logs and Caddy Config

Production deployment uses:

```text
C:\apps\LifePIM_Prod
C:\apps\LifePIM_Prod\logs
C:\apps\caddy\Caddyfile
```

The backup guide already includes optional production log backup. The Caddyfile
is not LifePIM user data, but it is operational configuration.

TODO:

- Back up `C:\apps\LifePIM_Prod\logs` if production troubleshooting history
  matters.
- Back up `C:\apps\caddy\Caddyfile` or keep it reproducible from
  `scripts/prod/update_caddy_lan_hosts.py`.

### Pocket Mobile File Backups

Pocket/mobile file sync writes mobile files under the configured user's file
root plus:

```text
pocket_mobile
```

Current database rows show:

```text
N:\duncan\LifePIM_Data\DATA\pocket_mobile
```

That is on the NAS and is covered by the NAS backup.

TODO:

- Fill missing user path roots for users that still have blank
  `file_root_path`, `notes_root_path`, `areas_root_path`, or `lists_root_path`.
- This avoids fallback behavior where mobile backups could be written beside
  the local database if no NAS user root can be resolved.

### Local Generated HOW Files

The HOW service default save folder falls back to:

```text
<data_folder>\how
```

In this setup that is:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA\how
```

TODO:

- Decide whether generated HOW markdown should be local generated data or
  stored under the NAS notes/HOW area.
- If it remains local, the local root backup covers it.
- If it should be permanent user-authored content, configure HOW save folders
  through Area defaults on `N:\duncan\LifePIM_Data\DATA\notes`.

### Media, Audio, Files, and 3D Referenced Paths

The current database contains many indexed paths on external or mirror drives,
including examples like:

```text
E:\BK_fangorn\music\...
E:\BK_willow\Movies\...
E:\BK_fangorn\user\duncan\LifePIM_Data\...
E:\BK_fangorn\user\duncan\C\user\docs\designs\blender
```

These are referenced by `lp_media`, `lp_audio`, `lp_files`, `lp_3d`, and
`dim_folder`. LifePIM does not copy those files into `lifepim.db`.

TODO:

- Decide which `E:` locations are authoritative and which are mirrors.
- If any `E:` location is authoritative, add it to the backup plan.
- If `E:` is only a working mirror of NAS/media drives, document the upstream
  source and mirror job.
- Consider adding a Settings/Admin report listing indexed root prefixes so
  backup coverage can be checked from the UI.

### Data Catalogue External Sources

The Data catalogue references external files by path. Current examples include:

```text
D:/DATA_LLM/SAMPLE_DATA/lifepim_desktop_data/lifepim.db
C:/apps/aggie/aggie.db
N:/duncan/C/user/docs/orders-Jul-2001.xls
N:/duncan/C/user/docs/build22_info.csv
N:/duncan/C/user/docs/Contacts_phone_2015.csv
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\DATA\logger\logger.sqlite
```

For CSV and Excel Data sources, LifePIM scans the file in place. It stores
schema/sample metadata in `lifepim.db`, but it does not copy the source
spreadsheet or CSV into LifePIM storage.

TODO:

- Audit `d_data_source.root_path` regularly.
- Move any important local-only sources such as `C:/apps/aggie/aggie.db` into a
  backed-up folder or add them to the backup script.
- Update the stale `Logger SQLite` Data source to the current logger database
  path.
- Treat external CSV/Excel files as source data that must be backed up at their
  own location.

### Configured CSV Import Sources

Current config and legacy ETL code reference CSV files from several places:

```text
E:\BK_fangorn\user\duncan\LifePIM_Data\configuration\all_folders.csv
E:\BK_fangorn\user\duncan\LifePIM_Data\configuration\area_folders.csv
N:\duncan\LifePIM_Data\configuration\r_map_xtn.csv
N:\duncan\LifePIM_Data\configuration\r_xtn_filetype.csv
N:\duncan\LifePIM_Data\configuration\r_map_fav_folders.csv
N:\duncan\LifePIM_Data\configuration\ontology.csv
N:\duncan\LifePIM_Data\index\raw_oak_*.csv
```

`init_database.py` currently uses:

- `etl_folders_csv` for folder cache import.
- `area_mappings_csv` for Area and Area-folder import.

The old `common.table_definitions` CSV jobs are legacy ETL definitions. They
may still matter if `common.if_sqlite` / `INIT_ALL_DATA.py` is run manually.

TODO:

- Move `etl_folders_csv` and `area_mappings_csv` defaults away from
  `E:\BK_fangorn...` if the NAS `N:\...` copy is now the permanent source.
- Or document that `E:\BK_fangorn...` is the required working mirror before
  rebuilding the database.
- Review legacy CSV jobs in `src/common/table_definitions.py` and mark them
  current, deprecated, or remove them from normal workflows.
- Make all required CSV source paths visible in Settings/Admin so they are not
  hidden in Python constants.

### FileLister Database Source

Media/audio migration reads from:

```text
D:\TRANSFER_NAS\filelister\filelist_master.db
```

This database is not inside the LifePIM local root and is not copied by the
backup script above.

TODO:

- Decide whether `filelist_master.db` is reproducible from source drives or is
  authoritative.
- If authoritative, back up `D:\TRANSFER_NAS\filelister`.
- If reproducible, document the rebuild command and source drives.

### Legacy and Development Scripts

Several scripts under `scripts/dev`, `scripts/prod`, and `src/common` contain
hard-coded paths such as:

```text
\\FANGORN\user\duncan\LifePIM_Data\index
N:\duncan\LifePIM_Data\DATA\SQL\lifepim_etl.db
C:\DATA\LifePIM_cache\lifepim_etl.db
C:\DATA\filelist_master.db
D:\dev\src\lifepim\...
```

Some are documentation/examples, some are old ETL tools, and some write real
CSV or SQLite outputs when run manually.

TODO:

- Mark each script as current, deprecated, or example-only.
- Move current script paths into `common.config`, environment variables, or
  Settings.
- Add comments to deprecated scripts warning that they are not part of the
  normal backup-supported workflow.

### Config Defaults Should Be Safer

The app still contains personal/machine-specific defaults in
`src/common/config.py`.

TODO:

- Move local machine paths out of committed defaults.
- Prefer environment variables or a local ignored config file for:
  - `user_folder`
  - `DB_FILE`
  - `data_folder`
  - `LAN_USER_ROOT_BASE`
  - `etl_folders_csv`
  - `area_mappings_csv`
  - `FILELIST_DB`
- Add an Admin page that shows "All configured storage roots" and whether each
  one is covered by the backup guide.

### Moving to PROD

The current production deployment copies source from:

```text
D:\DATA_LLM\dev\lifepim-desktop\src
```

to:

```text
C:\apps\LifePIM_Prod\src
```

using `src\DEPLOY_PROD.BAT`.

That deploy script currently mirrors the whole `src` folder:

```bat
robocopy "%ROOT_DIR%\src" "%PROD_DIR%\src" /MIR ...
```

It excludes database/log/cache files, but it does not exclude:

```text
src\common\config.py
```

So if the dev `config.py` points at:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data
```

then deploying to `C:\apps\LifePIM_Prod` can overwrite the production config
with that dev path. That is probably why the production app still appears to be
using `SAMPLE_DATA`.

#### Target PROD Layout

Use a production local data root that is not named `SAMPLE_DATA`, for example:

```text
C:\apps\LifePIM_Data
```

or, if the database should stay on the fast `D:` drive:

```text
D:\DATA_LLM\lifepim_desktop_data
```

Then production should resolve roughly as:

```text
user_folder = C:\apps\LifePIM_Data
data_folder = C:\apps\LifePIM_Data\DATA
DB_FILE     = C:\apps\LifePIM_Data\lifepim.db
logger DB   = C:\apps\LifePIM_Data\logger.sqlite
```

or the same shape under the chosen `D:` production root.

Do not put the production database under `C:\apps\LifePIM_Prod\src`. The deploy
script mirrors source code there and should be free to replace it.

#### One-Time PROD Move

1. Stop LifePIM production.

```bat
C:\apps\LifePIM_Prod\STOP_DESKTOP.BAT
```

2. Create the production data root.

```bat
mkdir C:\apps\LifePIM_Data
```

3. Copy the current local data root into the production data root.

For a conservative first move:

```bat
robocopy "D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data" "C:\apps\LifePIM_Data" /E /XJ /COPY:DAT /DCOPY:DAT /R:3 /W:5 /NP /TEE /LOG:"C:\apps\LifePIM_Data\move_from_sample_data.log"
```

This copies:

- `lifepim.db`
- `lifepim.db-wal` / `lifepim.db-shm` if present
- `logger.sqlite`
- `DATA\Media\imported\icons`
- `DATA\how`
- `tmp_imports`
- local admin/logger folders

4. Edit the production config file:

```text
C:\apps\LifePIM_Prod\src\common\config.py
```

Set at least:

```python
user_folder = r"C:\apps\LifePIM_Data"
data_folder = os.path.join(user_folder, "DATA")
db_name = os.path.join(user_folder, "lifepim.db")
DB_FILE = db_name
```

Keep the NAS roots pointing at `N:`:

```python
LAN_USER_ROOT_BASE = r"N:\duncan\LifePIM_Data\DATA\lan_users"
```

5. Start production.

```bat
C:\apps\LifePIM_Prod\RUN_DESKTOP.BAT
```

6. Verify the active paths from the deployed production source tree:

```bat
cd /d C:\apps\LifePIM_Prod\src
..\.venv\Scripts\python.exe -c "from common import config as c; print(c.user_folder); print(c.data_folder); print(c.DB_FILE)"
```

Expected output should not contain:

```text
SAMPLE_DATA
```

7. Open Admin/Settings and confirm the displayed database/user/data folders
match the production root.

#### Runtime Override Caution

LifePIM supports saved config overrides in `sys_settings` with keys such as:

```text
config.DB_FILE
config.db_name
config.user_folder
config.data_folder
```

However, these bootstrap overrides are read from the database path provided by
the copied `config.py` defaults first. If `config.py` points at the wrong
`SAMPLE_DATA` database, production may read overrides from the wrong database.

For the first production move, update the deployed production `config.py`
directly, then use Settings/Admin overrides only after production is booting
from the correct database.

#### DEPLOY_PROD.BAT Must Not Clobber PROD Config

After manually editing:

```text
C:\apps\LifePIM_Prod\src\common\config.py
```

the next deploy can overwrite it again.

TODO:

- Change `src\DEPLOY_PROD.BAT` so it does not overwrite production-local
  config.

Minimum deploy-script change:

```bat
robocopy "%ROOT_DIR%\src" "%PROD_DIR%\src" /MIR /FFT /R:2 /W:2 ^
  /XD "__pycache__" ".pytest_cache" "_codex_backup_*" ^
  /XF "config.py" "*.db" "*.sqlite" "*.sqlite3" "*.duckdb" "*.db-shm" "*.db-wal" "*.sqlite-shm" "*.sqlite-wal" "*.log" "*.pyc" "*.pyo"
```

That avoids copying any file named `config.py`, including:

```text
src\common\config.py
```

For a fresh production install, create `C:\apps\LifePIM_Prod\src\common\config.py`
once before using that exclusion. Also keep a copy outside the mirrored `src`
tree:

```text
C:\apps\LifePIM_Prod\config\config.py.backup
```

Better long-term fix:

- Keep committed defaults generic.
- Add a production-local ignored file such as:

```text
C:\apps\LifePIM_Prod\local_config.py
```

or:

```text
C:\apps\LifePIM_Prod\config\lifepim.local.json
```

- Load machine-specific paths from that file or from environment variables.
- Let `DEPLOY_PROD.BAT` freely replace application source without replacing
  data/config.

#### Suggested PROD Backup Script Update

Once production uses:

```text
C:\apps\LifePIM_Data
```

the backup source should change from:

```text
D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data
```

to:

```text
C:\apps\LifePIM_Data
```

Example:

```bat
set SRC=C:\apps\LifePIM_Data
set DEST=N:\duncan\LifePIM_Data\DATA\SQL\LifePIM_LOCAL_BACKUP

robocopy "%SRC%" "%DEST%\LifePIM_Data" /E /XJ /COPY:DAT /DCOPY:DAT /R:3 /W:5 /NP /TEE /LOG+:"%DEST%\logs\backup_prod_lifepim_data.log"
```

Back up production code separately only if needed. The critical state is the
production data root, the NAS content roots, Caddy config/cert state, and any
production logs you care about.
