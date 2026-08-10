# LifePIM File Inventory

The File Inventory scanner lives in `src/apps/files`. It replaces the legacy
FileLister CSV batch script with a persistent SQLite inventory of filesystem
metadata.

The scanner records only inexpensive filesystem state:

- full filename
- containing path
- extension
- filename
- modified, created, and accessed timestamps
- file size

It does not read file contents, calculate hashes, extract EXIF/audio metadata,
create thumbnails, or parse documents. Those are downstream Apps that consume
the inventory change log.

## Database

The inventory uses its own SQLite database. The default is configured by
`common.config.FILE_INVENTORY_DB`, currently `files.db` under the LifePIM user
folder.

Tables:

- `lp_file_source`: configured roots with `source_id`, `name`, `root_path`, and
  `enabled`.
- `lp_file`: master inventory keyed by `source_id` and normalized relative path.
- `lp_file_scan`: one row per scan, including status and summary counts.
- `lp_file_change`: `NEW`, `CHANGED`, `DELETED`, and `REACTIVATED` rows emitted
  by each scan.

The identity rule is `source_id + normalized_relative_path`, not the absolute
drive letter. This allows a source root to move later without redefining every
file.

## Scan Modes

`AUTO` chooses a full baseline when no successful scan exists. After a baseline,
the scanner is structured to use a fast provider when available.

`FULL` recursively reconciles the whole source.

`SCOPED` reconciles only a subtree under the source root. Missing-file detection
is limited to that subtree.

`INCREMENTAL` attempts reliable incremental detection. In this V1 build, the
NTFS USN provider is isolated behind `providers/ntfs_usn.py` but not active, so
incremental requests safely fall back to filesystem reconciliation and record
`full_scan` as the provider.

## Soft Deletion

Missing files are never physically removed from `lp_file`. A successful
reconciliation marks them with `is_deleted = 1` and `deleted_at`.

If the same source-relative path reappears, the same `file_id` is reactivated:
`is_deleted = 0`, `deleted_at = NULL`, and a `REACTIVATED` change is emitted.

If the source root is unavailable, the scan fails and no existing files are
marked deleted.

## Running

Normal use is from the Apps tab:

```text
Apps -> LifePIM File Inventory Scanner -> Open -> choose Root folder -> Run
```

The scanner creates or refreshes the source record internally. You do not need
to name a source or remember a `source_id` for normal use.

For direct testing, scan a folder:

```text
cd src
python -m apps.files.scan "D:\Photos" --mode FULL --json
```

Advanced source listing exists in the CLI, but it is not part of the normal
workflow.

The Apps tab is seeded with `LifePIM File Inventory Scanner`, a normal App
action with parameters:

- `root_path`
- `mode`

The legacy `scripts/prod/filelister.py` now delegates to the new scanner.

## Downstream Consumption

Other Apps process only files changed in a scan:

```sql
SELECT f.*
FROM lp_file_change c
JOIN lp_file f
  ON f.file_id = c.file_id
WHERE c.scan_id = ?
  AND c.change_type IN ('NEW', 'CHANGED', 'REACTIVATED')
  AND f.is_deleted = 0;
```

Image or audio processors can add extension filters such as:

```sql
AND f.xtn IN ('jpg', 'jpeg', 'png', 'heic')
```

or:

```sql
AND f.xtn IN ('mp3', 'flac', 'm4a')
```
