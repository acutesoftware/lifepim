# LifePIM Desktop
https://www.lifepim.com lets you quickly manage and find everything - all lists, ideas, and notes, tasks, calendar events, logs, ETL jobs, images, music, videos, programs, etc.

This repository contains scripts and an upcoming Desktop version you can run
on your local PC (to keep sensitive data local).  You can still interface with
the live site but you get to choose which data gets uploaded to your lifepim
account.

## Status
working on web interface

Under development - nothing significant works yet!

2025 - restarting. Old code moved to N:\duncan\C\user\dev\src\python\z_bk_python\LifePIM_public_2024

## Quick Start
This github repository [https://github.com/acutesoftware/lifepim](https://github.com/acutesoftware/lifepim) contains the latest code, but the current public release is available via

`pip install lifepim`

This application is used to collect local metadata for indexing and allow for
automatic uploading to https://www.lifepim.com

To run the local web server, use
`python web_server.py`

## Importer (v1)
Intent: keep import scripts tiny and declarative. Your script specifies WHAT to import, FROM WHERE, HOW to map, and the stable key. LifePIM core handles IDs, upserts, tombstones, and logging.

Steps:
1) Pick the target domain (contacts/files/media) or a raw table.
2) Define a mapping (target field -> source column/transform).
3) Choose a stable key (source_uid or sha256).
4) Pick mode (snapshot/authoritative/merge) and dry-run first.

What gets overwritten:
- Importer targets: fields written by the writer are overwritten on upsert (display_name/email/phone for contacts, path/size/mtime_utc/sha256 for files, labels_json/etc for media). source_system/source_uid/imported_* are also updated each run.
- snapshot mode: previously imported rows for the same source_system are marked is_deleted=1 (soft delete).
- authoritative + tombstone: rows missing from the current feed are marked is_deleted=1.
- merge mode: only provided fields are updated; no deletes or tombstones.

Be careful:
- A wrong key can overwrite unrelated entities. Use a stable key and prefer sha256 for files.
- snapshot/authoritative can mark lots of rows deleted if the feed is incomplete.
- load_tbl is a raw insert (no de-dupe, no stable IDs). Use only for simple append-only tables.

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



