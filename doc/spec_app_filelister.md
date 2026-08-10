# Codex Spec — LifePIM File Inventory Scanner

## 1. Intent

Build a new **LifePIM File Inventory subsystem** under:

```text
LifePIM/src/apps/files/
```

This replaces the existing FileLister-style batch process.

The purpose of this subsystem is to maintain a persistent, reliable database inventory of files known to LifePIM.

The scanner must support:

* initial creation of a completely blank file inventory database
* full recursive scans of configured folders
* fast incremental scans after the initial scan
* scoped scans of a single folder/subtree
* detecting new files
* detecting changed files
* detecting deleted/missing files
* preserving records for deleted files rather than physically deleting them
* safely recovering if a previously deleted file reappears
* recording scan history
* exposing exactly which files changed during a scan so later LifePIM Apps can process only those files
* being callable independently from the LifePIM UI, Tasks, Aggie, InfoLink or CLI

The scanner must **only inventory filesystem metadata**.

It must NOT extract image EXIF, audio metadata, thumbnails, PDF metadata, etc.

Those will be separate LifePIM Apps operating against the file inventory.

---

# 2. Architectural principle

The File Inventory is the authoritative LifePIM record of:

> What files exist, where they are, and when their filesystem attributes changed.

The overall future architecture is:

```text
Filesystem / Local Mirror
        |
        v
   File Scanner
        |
        v
+-----------------------+
| Master File Inventory |
+-----------------------+
        |
        +---- changed image files ---> Image Metadata App
        |
        +---- changed audio files ---> Audio Metadata App
        |
        +---- other files -----------> Other processors
```

Scanning and metadata processing must remain completely separate.

---

# 3. Code location

Create the subsystem beneath:

```text
src/apps/files/
```

Suggested structure:

```text
src/apps/files/
    __init__.py

    scan.py
    scanner.py
    inventory_db.py
    change_detector.py
    scan_models.py

    providers/
        __init__.py
        full_scan.py
        ntfs_usn.py
```

Exact module names may be adjusted to fit existing LifePIM conventions.

Keep filesystem/database logic separated enough that additional change-detection providers can be added later.

---

# 4. Database

The File Inventory must have its own SQLite database.

Follow the existing LifePIM conventions for configurable database/data locations.

Do not hard-code a developer machine path.

Suggested logical database name:

```text
files.db
```

or:

```text
lifepim_files.db
```

Use whichever naming convention fits the existing LifePIM Data subsystem.

If the database does not exist, the scanner must create it automatically.

If the database exists but required tables do not exist, create them safely.

An empty database must be a completely valid starting state.

Use SQLite transactions for all reconciliation operations.

Enable appropriate SQLite settings such as WAL mode if consistent with existing LifePIM database handling.

---

# 5. File source configuration

Do not make the scanner inherently dependent on a particular NAS or drive letter.

A scan operates against a configured source.

Create or reuse a source concept containing at minimum:

```text
source_id
name
root_path
enabled
```

Example:

```text
source_id = 1
name      = Local Photos Mirror
root_path = D:\Photos
enabled   = true
```

The scanner receives:

```text
source_id
scope
scan_mode
```

rather than embedding paths in scanner code.

The `scope` is relative to the configured source root.

Examples:

```text
scope = /
```

means entire source.

```text
scope = Family/2026/Birthday
```

means only that subtree.

---

# 6. Master file inventory table

Create a persistent master table.

Suggested name:

```text
lp_file
```

The scanner must capture the **complete filesystem metadata currently imported by the existing FileLister process**.

Required fields include:

```text
file_id
source_id

fullfilename
path
xtn
name

date_modified
date_created
date_accessed
size

is_deleted
deleted_at

first_seen_at
last_seen_at

first_seen_scan_id
last_seen_scan_id

created_at
updated_at
```

## Required imported metadata definitions

### fullfilename

Complete filename including path.

Example:

```text
D:\Photos\Family\2026\Birthday\IMG_1234.jpg
```

### path

Containing directory.

Example:

```text
D:\Photos\Family\2026\Birthday
```

### xtn

File extension.

Prefer normalised lowercase without changing the original filename.

Example:

```text
jpg
```

or use the same format as the existing imported FileLister data if compatibility requires `.jpg`.

Be consistent throughout LifePIM.

### name

Filename itself.

Example:

```text
IMG_1234.jpg
```

### date_modified

Filesystem modified timestamp.

### date_created

Filesystem creation timestamp.

### date_accessed

Filesystem accessed timestamp.

### size

File size in bytes.

---

# 7. Additional internal fields

The scanner may add internal fields needed for reliable operation.

Recommended:

```text
relative_path
parent_relative_path
normalized_path
scan_status
```

The most important is:

```text
relative_path
```

Example:

```text
Family/2026/Birthday/IMG_1234.jpg
```

Do not make LifePIM identity depend on the absolute drive letter.

A source may eventually move from:

```text
D:\Photos
```

to:

```text
E:\Photos
```

without conceptually creating millions of new files.

---

# 8. File identity

Use a stable LifePIM surrogate key:

```text
file_id
```

The logical filesystem identity should initially be based on:

```text
source_id + normalized relative path
```

Create an appropriate unique index.

For example:

```text
UNIQUE(source_id, normalized_relative_path)
```

Path comparison must follow appropriate platform rules.

On Windows, path matching should not incorrectly duplicate files because of case differences.

---

# 9. Soft deletion

Never physically delete a file record merely because the filesystem file disappears.

When a known file no longer exists:

```text
is_deleted = 1
deleted_at = current timestamp
updated_at = current timestamp
```

Keep all other known metadata.

This preserves historical knowledge that the file existed.

If the same path later reappears:

```text
is_deleted = 0
deleted_at = NULL
```

and update its filesystem metadata normally.

---

# 10. Updating changed files

If an existing file changes, update the existing `lp_file` row.

Do NOT create another master row merely because size/date metadata changed.

Update fields such as:

```text
date_modified
date_created
date_accessed
size
fullfilename
path
name
xtn
```

and:

```text
last_seen_at
last_seen_scan_id
updated_at
```

The master table represents the most recently known filesystem state.

Historical scan/change information is recorded separately.

---

# 11. Scan history

Create:

```text
lp_file_scan
```

Suggested fields:

```text
scan_id
source_id
scope_path
scan_mode

started_at
completed_at

status

files_seen
files_new
files_changed
files_unchanged
files_deleted
files_reactivated
errors

change_provider
provider_checkpoint_before
provider_checkpoint_after
```

Possible status values:

```text
RUNNING
SUCCESS
FAILED
CANCELLED
```

Possible scan modes:

```text
FULL
INCREMENTAL
SCOPED
```

Every scan must get its own `scan_id`.

---

# 12. File change log

Create:

```text
lp_file_change
```

This table records files affected by each successful scan.

Suggested fields:

```text
file_change_id
scan_id
file_id
change_type
detected_at
```

`change_type` should support:

```text
NEW
CHANGED
DELETED
REACTIVATED
```

Do not populate this table for ordinary unchanged files unless there is a strong diagnostic reason.

This table is critical because downstream Apps must be able to say:

> Give me the image files changed by scan 827.

For example:

```sql
SELECT f.*
FROM lp_file_change c
JOIN lp_file f
  ON f.file_id = c.file_id
WHERE c.scan_id = ?
  AND c.change_type IN ('NEW', 'CHANGED', 'REACTIVATED')
  AND f.xtn IN ('jpg', 'jpeg', 'png', 'heic');
```

This becomes the handoff from File Inventory to future Image/Audio Apps.

---

# 13. Initial full scan

A brand-new source requires a full scan.

Example:

```text
files.scan
source_id = 1
scope = /
mode = FULL
```

The scanner recursively walks the source and inserts the filesystem metadata into `lp_file`.

For an empty database:

```text
everything found = NEW
```

The scanner should be optimised for large inventories.

The existing complete scan currently takes approximately two hours. This is acceptable.

Correctness and robustness are more important than forcing the initial scan to be fast.

Use efficient directory enumeration such as `os.scandir()` rather than unnecessarily expensive per-file operations.

Do not open file contents.

Do not calculate hashes during the normal inventory scan.

Do not extract media metadata.

---

# 14. Full reconciliation algorithm

A full scan should conceptually operate as follows.

## Step 1 — validate source

Before changing any inventory state:

* ensure source exists
* ensure source is accessible
* ensure expected root is correct

If the root is unavailable:

```text
FAIL THE SCAN
```

Do NOT mark all existing files deleted.

This is an essential safety requirement.

## Step 2 — create scan record

Insert:

```text
lp_file_scan
status = RUNNING
```

## Step 3 — enumerate files

For every file found:

look up by:

```text
source_id + normalized_relative_path
```

### Not found

Insert into `lp_file`.

Record:

```text
change_type = NEW
```

### Existing and marked deleted

Update metadata.

Set:

```text
is_deleted = 0
deleted_at = NULL
```

Record:

```text
change_type = REACTIVATED
```

### Existing and filesystem attributes changed

Update the row.

Record:

```text
change_type = CHANGED
```

### Existing and unchanged

Only update appropriate scan/last-seen fields.

Do not add a change queue entry.

## Step 4 — detect missing files

Only after successful enumeration should deletion reconciliation occur.

For a full source scan:

Any currently active row for that source that was not seen by this scan becomes deleted.

For a scoped scan:

Only rows **inside the successfully scanned scope** may be marked deleted.

Never mark files outside the requested scope deleted.

## Step 5 — complete scan

Update:

```text
status = SUCCESS
completed_at
counts
```

Only a successful scan may establish the new incremental checkpoint.

---

# 15. Change detection

A file should normally be considered changed when relevant inexpensive filesystem attributes differ.

At minimum compare:

```text
size
date_modified
```

Other supplied filesystem dates may also be updated when appropriate.

Do not calculate file hashes simply to determine whether a file should be reprocessed.

The design must allow hashes to be added later as a specialist processor if needed.

---

# 16. Fast incremental scanning

A major requirement is:

> After an initial full inventory exists, LifePIM must have a fast method to determine which files have changed since the last successful scan.

Do NOT design incremental scanning as:

```text
open every file
extract metadata again
compare results
```

The scanner architecture should have pluggable change-detection providers.

Define an interface roughly representing:

```text
get_changes_since(source, checkpoint)
```

The initial providers should be:

```text
FullScanProvider
WindowsNtfsUsnProvider
```

---

# 17. Windows NTFS USN Change Journal

For local NTFS-backed sources, implement support for the Windows **USN Change Journal** as the preferred fast incremental mechanism.

This is particularly valuable for LifePIM's local mirrored drives containing very large file libraries.

After a successful full scan, store the necessary journal/checkpoint information for the source.

A later:

```text
mode = INCREMENTAL
```

scan should ask NTFS for filesystem changes since that checkpoint rather than recursively enumerating every file.

Use the changed paths to determine:

```text
NEW
CHANGED
DELETED
RENAMED / MOVED
```

and reconcile only those affected filesystem records.

The exact underlying Windows API/library can be selected based on what fits the project cleanly.

Keep Windows-specific implementation isolated under something like:

```text
src/apps/files/providers/ntfs_usn.py
```

The rest of LifePIM must not depend directly on NTFS implementation details.

---

# 18. Incremental fallback

USN Journal support cannot be assumed for every source.

Examples include:

* network shares
* non-NTFS volumes
* removable media
* unsupported configurations
* journal reset/wrap
* unavailable checkpoint

If fast incremental detection cannot safely be used:

```text
fall back to a normal filesystem reconciliation scan
```

and record the provider actually used in `lp_file_scan`.

Never silently skip reconciliation simply because an incremental provider failed.

---

# 19. Important incremental-scan safety rule

A timestamp such as:

```text
last_scan = 2026-08-10 02:00
```

by itself is NOT sufficient to reliably detect deleted files.

Therefore do not implement deletion detection by simply saying:

```text
find files where modified_time > last_scan
```

Files that were deleted cannot be found that way.

Reliable incremental deletion detection should come from something like the NTFS journal.

If the change journal cannot guarantee correctness, use a reconciliation scan.

---

# 20. Scoped scans

The scanner must support:

```text
scope
```

for fast user-triggered refreshes.

Example:

```text
files.scan
source_id = 1
scope = Photos/Family/2026/Birthday
```

Only this folder and its descendants are scanned.

Deletion reconciliation must also be limited to this subtree.

This is what will eventually support the LifePIM Media command:

```text
Refresh this folder
```

without rescanning the complete file library.

---

# 21. Scan modes

Expose clear scan modes.

## AUTO

```text
mode = AUTO
```

Preferred default.

Behaviour:

```text
if no successful baseline:
    FULL
elif fast incremental provider available:
    INCREMENTAL
else:
    reconciliation scan
```

## FULL

```text
mode = FULL
```

Force complete recursive reconciliation.

## INCREMENTAL

```text
mode = INCREMENTAL
```

Use reliable change information since the previous successful checkpoint.

If unavailable, either fall back safely or clearly report the fallback in the scan result.

## SCOPED

A scope may be combined with normal/full scanning:

```text
scope = Family/2026
```

This explicitly scans only the selected subtree.

---

# 22. Last successful scan

Never use the timestamp of a failed or incomplete scan as the next baseline.

Incremental processing must use:

```text
last SUCCESSFUL scan/checkpoint
```

A failed scan must leave the previous known-good incremental checkpoint intact.

---

# 23. Transaction safety

A scan of millions of files must not leave the database logically corrupted if interrupted.

Use appropriate transactions/batching.

Do not require holding one enormous SQLite transaction open for two hours if that creates operational problems.

However:

* scan status must remain clear
* missing-file reconciliation must only occur after successful enumeration
* failed scans must not incorrectly produce mass deletions
* checkpoints must only advance after successful completion

A partially completed scan must be identifiable as:

```text
FAILED
```

or stale `RUNNING`.

On the next invocation, the scanner must recover safely.

---

# 24. Large-library performance

Design for at least:

```text
1,500,000+ files
```

Indexes must support:

```text
source + path lookup
source + relative path lookup
extension filtering
is_deleted filtering
last scan lookup
scan change lookup
```

Add sensible indexes, for example:

```text
(source_id, normalized_relative_path)
(source_id, is_deleted)
(xtn)
(last_seen_scan_id)
```

and appropriate indexes on `lp_file_change`.

Do not over-index fields that will make bulk scanning unnecessarily slow.

---

# 25. Progress reporting

The App should expose useful progress information suitable for LifePIM Task Runs.

For example:

```text
Scanning Local Photos Mirror

Files examined:   928,481
New:                   17
Changed:               42
Deleted:                3
Reactivated:            1
Unchanged:        928,418
```

Long scans should periodically report progress rather than appearing hung.

Do not print one log line per ordinary file.

Log errors and summary information.

---

# 26. Error handling

Individual inaccessible/problematic files should normally be logged and allow the scan to continue.

Track scan error count.

Examples:

```text
permission denied
path disappeared during scan
stat failure
invalid filename
```

A catastrophic source-level problem should fail the scan.

Example:

```text
root folder unavailable
volume disconnected
database failure
```

Again: source-level failure must never result in mass deletion marking.

---

# 27. File rename/move behaviour

For V1 it is acceptable for path-based identity to treat:

```text
OldFolder/photo.jpg
```

becoming:

```text
NewFolder/photo.jpg
```

as:

```text
old path = DELETED
new path = NEW
```

unless the USN provider can reliably identify the rename and retain the same `file_id`.

Architect the implementation so improved rename tracking can be added later.

Do not introduce expensive file hashing merely to solve rename detection in V1.

---

# 28. App interface

The scanner must be runnable as a normal LifePIM App.

Conceptual usage:

```text
files.scan
```

Parameters:

```text
source_id
scope
mode
```

Example:

```text
source_id = 1
scope = /
mode = AUTO
```

or:

```text
source_id = 1
scope = Family/2026/Birthday
mode = FULL
```

The Python entry point should also be runnable directly for development/testing.

For example:

```text
python -m src.apps.files.scan --source-id 1 --mode auto
```

Exact CLI syntax may follow project conventions.

The scanner must return a structured result suitable for a LifePIM Task Runner.

Example information:

```text
scan_id
status
provider
files_seen
new
changed
deleted
reactivated
unchanged
errors
```

---

# 29. No dependency on Aggie

Do not put any of this processing logic into Aggie or InfoLink.

The ownership model is:

```text
LifePIM/src/apps/files/*
        =
actual implementation
```

Aggie may later trigger:

```text
LifePIM Task: Nightly File Refresh
```

but Aggie must not contain the scanner implementation.

Likewise the Media screen may trigger:

```text
LifePIM Task: Refresh Media Folder
```

but the Media UI must not contain scanning logic.

---

# 30. Future Task integration

Do not need to fully build the following workflow in this ticket unless the existing Task framework makes it trivial.

However, design this scanner explicitly to support:

```text
TASK: Refresh Files

1. sync folder
2. files.scan
3. image metadata processor
4. audio metadata processor
5. media updater
6. audio updater
7. generic file updater
```

The important output from this scanner is therefore:

```text
scan_id
```

Downstream Apps can consume:

```text
files changed during scan_id X
```

rather than searching the entire master inventory.

---

# 31. Full refresh / rebuild support

The subsystem must remain completely rebuildable.

Provide a clear method to:

### Normal full refresh

```text
scan --mode FULL
```

Reconcile everything without deleting the existing database.

### Empty rebuild

Allow an administrator/developer to deliberately remove/recreate the inventory database and perform a new baseline full scan.

Do NOT automatically destroy/recreate the database during ordinary operation.

---

# 32. Useful future processing query

The architecture should make this cheap:

```sql
SELECT f.*
FROM lp_file_change c
JOIN lp_file f
  ON f.file_id = c.file_id
WHERE c.scan_id = ?
  AND c.change_type IN ('NEW', 'CHANGED', 'REACTIVATED')
  AND f.is_deleted = 0;
```

Then specialist Apps can add:

```sql
AND f.xtn IN ('jpg', 'jpeg', 'png')
```

or:

```sql
AND f.xtn IN ('mp3', 'flac', 'm4a')
```

This is the main mechanism by which LifePIM avoids reprocessing unchanged files.

---

# 33. Tests

Add automated tests for at least the following.

## Empty database

Given:

```text
database does not exist
```

running a scan:

* creates database
* creates schema
* inserts files correctly

## New file

Create:

```text
one.txt
```

Scan.

Confirm:

```text
NEW
is_deleted = 0
```

## Changed file

Modify size/content/date.

Scan.

Confirm:

* same `file_id`
* metadata updated
* one `CHANGED` record

## Unchanged file

Scan twice without modification.

Confirm:

* same record
* no unnecessary `CHANGED` record

## Deleted file

Remove a file.

Full/scoped reconciliation.

Confirm:

```text
is_deleted = 1
deleted_at populated
```

and row remains in database.

## Reactivated file

Restore same file path.

Scan again.

Confirm:

```text
same logical inventory row
is_deleted = 0
deleted_at = NULL
change_type = REACTIVATED
```

## Scoped deletion

Have:

```text
FolderA/a.txt
FolderB/b.txt
```

Delete both.

Scan only:

```text
FolderA
```

Confirm:

```text
a.txt = deleted
b.txt = still current
```

The scanner must not infer anything about FolderB.

## Missing source

Populate inventory.

Make source root unavailable.

Run scan.

Confirm:

* scan fails
* existing records are NOT marked deleted

## Failed scan checkpoint

Force scan failure.

Confirm previous successful incremental checkpoint remains active.

## Incremental scan

After baseline scan:

* add file
* modify file
* delete file

Run incremental provider.

Confirm correct change classifications without full metadata reprocessing.

## Large-volume behaviour

Include a synthetic test or benchmark capable of exercising large directory counts without excessive memory consumption.

---

# 34. Data migration

Do not require migration of the old FileLister output as part of the first implementation unless straightforward.

The new database should be capable of being created cleanly from scratch by scanning the filesystem.

The existing FileLister/import process can remain temporarily while this is tested.

Once validated, the new inventory becomes the replacement source for subsequent Image, Audio and generic Files processors.

---

# 35. UI scope

This ticket is primarily the backend/App implementation.

A minimal LifePIM interface may expose enough functionality to test:

```text
Data / Apps / Files
```

or existing Apps UI:

```text
Run File Scan
```

with:

```text
Source
Scope
Mode
```

and display the returned scan summary.

Do not spend substantial effort building a specialist FileLister UI.

The scanner should be reusable through the general Apps/Tasks infrastructure.

---

# 36. Documentation

Document:

* purpose of the File Inventory
* database/table structure
* full vs incremental scans
* scoped scans
* soft deletion behaviour
* fast NTFS incremental behaviour
* fallback behaviour
* how another LifePIM App consumes changed files using `scan_id`
* how to run the scanner directly for testing

---

# 37. Definition of done

The feature is complete when the following workflow works from a completely blank environment:

```text
1. Configure a filesystem source.

2. Run files.scan.

3. LifePIM automatically creates the File Inventory database/schema.

4. All files beneath the source are recorded with:

   fullfilename
   path
   xtn
   date_modified
   date_created
   date_accessed
   size
   name

5. Add some files.

6. Modify some files.

7. Delete some files.

8. Run files.scan again.

9. Existing changed rows are updated in-place.

10. New files are inserted.

11. Missing files remain in lp_file but are flagged deleted.

12. lp_file_change contains only the files that downstream
    processing needs to react to.

13. A scoped folder scan modifies only that subtree.

14. Where supported, an incremental scan can discover filesystem
    changes since the previous successful scan without walking the
    complete 1.5M+ file tree.

15. A forced FULL scan remains available at any time and reconciles
    the database safely.

16. A failed/unavailable source can never accidentally mark the
    complete library deleted.
```

## Core design rule

The key long-term contract is:

> **The File Inventory scanner discovers filesystem state. It does not process file contents. Every scan produces a reliable set of NEW, CHANGED, DELETED and REACTIVATED files, and downstream LifePIM Apps process only those changes.**

This File Inventory should become the foundation for subsequent:

```text
src/apps/media/*
src/apps/audio/*
src/apps/files/catalog/*
```

processing and replace the current full FileLister → Image List → Audio List batch dependency.
