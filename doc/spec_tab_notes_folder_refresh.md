# Codex Spec: LifePIM Notes Folder Sync

## Objective

Implement a lightweight folder synchronisation mechanism for LifePIM Notes.

LifePIM Notes can be edited both inside LifePIM and externally using editors such as VS Code, Emacs, etc. Because the note files on disk are the source of truth, LifePIM must detect structural filesystem changes such as:

* new note files
* renamed note files
* deleted note files
* moved note files
* new folders
* renamed folders
* deleted folders

The implementation must avoid repeatedly scanning all note files.

Instead, LifePIM should maintain its own small SQLite index of the folders beneath the configured Notes roots and use each folder's filesystem modification timestamp to determine whether that individual folder needs to be rescanned.

The design should remain deliberately simple.

Do not introduce background services, filesystem watchdogs, scheduled scanners, workers or other persistent processes.

---

# Core Principle

The filesystem remains the source of truth.

LifePIM maintains a lightweight index of known Notes folders only so it can determine which folders may have structurally changed.

Normal operation should be:

```text
Get known note folders from SQLite
        ↓
stat() each folder
        ↓
mtime unchanged
    → do nothing

mtime changed
    → scandir() that individual folder
    → reconcile its immediate contents
```

Do not recursively rescan existing folder trees during the normal quick sync.

Recursive scanning is only required when:

1. A Notes root is indexed for the first time.
2. A completely new subfolder/tree is discovered.
3. The user explicitly requests a full/manual sync.

---

# Scope

This work applies only to the Notes functionality.

Create and maintain a Notes-specific folder index.

Do not attempt to generalise this into a global filesystem indexing framework.

Do not add a daemon/service architecture.

Prefer straightforward Python functions integrated into the existing Notes code.

---

# 1. New Notes Folder Index

Create a new SQLite table specifically for folders managed by Notes.

Use the existing LifePIM naming conventions where appropriate.

A suggested structure is:

```sql
lp_note_folders
---------------
id
root_path
parent_id
name
relative_path
folder_mtime_ns
last_scanned_at
is_missing
```

Exact naming may be adjusted to match the existing database conventions.

Minimum required information:

### `id`

Primary key.

### `root_path`

The configured Notes root this folder belongs to.

If the existing Notes configuration already has a root/folder identifier, reference that instead of duplicating the path unnecessarily.

### `parent_id`

References the parent folder record.

This allows the table to be used to construct a nested folder tree efficiently.

Root folders may have `parent_id = NULL`.

### `name`

Folder display name.

Example:

```text
drafts
```

### `relative_path`

Path relative to the configured Notes root.

Example:

```text
Book/drafts
```

Prefer storing relative paths rather than relying entirely on machine-specific absolute paths.

Use normalised forward-slash paths internally where this matches existing LifePIM conventions.

### `folder_mtime_ns`

The last directory modification timestamp observed by LifePIM.

Use the highest practical filesystem timestamp precision available, preferably:

```python
os.stat(path).st_mtime_ns
```

Do not rely on second-resolution timestamps if nanosecond-resolution timestamps are available.

### `last_scanned_at`

Timestamp showing when LifePIM last actually enumerated this folder.

This is useful for diagnostics.

### `is_missing`

Optional boolean/status flag.

Use this if the existing LifePIM data model prefers soft deletion/missing-state tracking.

If the existing application simply deletes obsolete index rows safely, follow the existing convention instead.

---

# 2. Initial Folder Index Build

When a configured Notes root has no folder index yet, build it.

Initial indexing may recursively walk the configured Notes root.

For each directory:

1. Add the folder to `lp_note_folders`.
2. Store its parent relationship.
3. Store its relative path.
4. Store its current `st_mtime_ns`.
5. Reconcile/index the files inside that folder using the existing Notes import/sync behaviour.

The initial scan may recurse because the complete directory structure is not yet known.

After this initial build, normal operation must switch to folder-level change detection.

---

# 3. Quick Folder Check

Implement a simple function along the lines of:

```python
check_note_folders(...)
```

The exact name/location should follow the current project conventions.

This is a normal function, not a service or background process.

For each folder currently recorded under the configured Notes root:

```python
current_mtime = os.stat(folder_path).st_mtime_ns
```

Compare it against:

```text
folder_mtime_ns
```

stored in SQLite.

The condition must be:

```text
current_mtime != stored_mtime
```

not:

```text
current_mtime > stored_mtime
```

The goal is to detect whether the directory is different from the state LifePIM previously observed, regardless of whether the timestamp moved forwards or backwards.

If the timestamps are equal:

```text
do nothing
```

Do not enumerate the files in the folder.

If the timestamps differ:

```text
refresh that folder
```

If the folder no longer exists:

```text
mark/remove it appropriately
```

and reconcile the relevant Notes data.

---

# 4. Folder Refresh Must Be Non-Recursive

Implement a function along the lines of:

```python
refresh_note_folder(...)
```

This function operates on exactly one directory.

Use:

```python
os.scandir(folder_path)
```

or an equivalent efficient directory enumeration.

Do not recursively walk existing child folders from this function.

Collect the immediate contents:

```text
files
subfolders
```

Compare those against what LifePIM currently knows.

Reconcile:

```text
new file
missing file
new folder
missing folder
existing file
existing folder
```

After the folder has been successfully reconciled, update:

```text
folder_mtime_ns
last_scanned_at
```

to represent the filesystem state that was just processed.

---

# 5. New Folder Discovery

A changed folder may contain a newly created subfolder that is not yet present in `lp_note_folders`.

Example:

```text
Book/
    research/       <-- new
        chapter01/
            sources.md
        chapter02/
            sources.md
```

When `Book` is refreshed, LifePIM discovers the new `research` folder.

Because this subtree has never been indexed, LifePIM must recursively discover it once.

Implement a helper function if appropriate, e.g.:

```python
add_note_folder_tree(...)
```

or similar.

For the newly discovered tree:

1. Add all folders to `lp_note_folders`.
2. Populate parent relationships.
3. Store their current mtimes.
4. Import/reconcile note files within them.

Once indexed, future changes to those directories are handled individually by the normal quick folder checks.

---

# 6. Removed Folder Handling

If a previously known folder no longer exists, the sync must reconcile the folder and its descendants safely.

For example:

```text
Book/research/
```

was indexed but has been deleted externally.

LifePIM should:

1. Detect that the folder is missing.
2. Remove or mark missing the corresponding folder index record.
3. Remove/mark missing descendant folder records.
4. Reconcile Notes records belonging to those folders using the application's existing missing/deleted-note behaviour.

Follow existing LifePIM deletion conventions.

Do not invent a new deletion lifecycle if Notes already has one.

---

# 7. File Changes Inside a Dirty Folder

The folder sync is primarily intended to detect structural changes.

Examples:

```text
new file
delete file
rename file
move file
```

A directory's modification time generally changes when directory entries change.

When a dirty folder is rescanned, reconcile its immediate file list against the Notes database.

Reuse existing Notes sync/import logic wherever practical.

Do not duplicate note parsing or metadata handling unnecessarily.

---

# 8. External File Content Edits

This feature is not intended to continuously detect arbitrary content changes inside otherwise unchanged directory structures.

For example:

```text
chapter01.md
```

may be edited externally without changing the containing directory's modification timestamp.

That is acceptable.

LifePIM already works directly with the underlying note files, so opening a note should continue to read the actual current file.

Do not introduce hashing or repeated file-content scanning as part of this feature.

---

# 9. Rename / Move Behaviour

Where practical, preserve the existing LifePIM Note record when a file is renamed or moved rather than automatically treating every rename as:

```text
delete old note
create new note
```

This is useful because Notes may contain LifePIM-specific metadata such as:

```text
is_template
is_important
```

However, keep rename detection conservative and simple.

Do not build a complex content-matching subsystem.

Reuse any existing Note identity or rename logic if available.

If the existing Notes sync already handles renames adequately, use that implementation.

The main purpose of this change is to determine **which folders need reconciliation**, not to redesign Note identity.

---

# 10. Automatic Sync on Notes Startup

When the Notes area/tab is opened or initialised, run the lightweight folder check.

The sequence should be:

```text
Notes starts
    ↓
load configured Notes roots
    ↓
load known folders from SQLite
    ↓
stat() each known folder
    ↓
refresh only dirty/missing folders
    ↓
continue loading Notes UI
```

Do not perform a recursive scan unless required because a new subtree has been discovered.

If no folders have changed, startup should involve only:

```text
SQLite query
+
one stat() per known directory
```

It should not enumerate note files.

The performance objective is that the normal "nothing changed" case is extremely cheap.

---

# 11. Manual Sync Button

Retain or implement a clear manual Notes sync/refresh button.

This must provide the user with an authoritative way to force reconciliation.

The manual action should perform a **full Notes root sync**.

It may recursively walk the configured Notes roots.

Its job is to repair/rebuild the Notes folder index and Notes file list from the actual filesystem.

Use this for cases such as:

* the user suspects the index is stale
* unusual filesystem operations occurred
* timestamps were preserved/restored unexpectedly
* the application was upgraded
* debugging/recovery

The manual sync is deliberately more expensive than the automatic startup check.

That is acceptable because it is explicitly requested by the user.

---

# 12. Full Sync / Rebuild Behaviour

The full sync should:

1. Read all configured Notes roots.
2. Walk each Notes directory tree.
3. Reconcile folders against `lp_note_folders`.
4. Add newly discovered folders.
5. Update parent relationships.
6. Update folder mtimes.
7. Remove/mark missing obsolete folders.
8. Reconcile note files using existing Notes behaviour.
9. Leave the database representing the current filesystem state.

The operation should be safe to run repeatedly.

It must be idempotent.

Running Full Sync twice with no filesystem changes should produce no meaningful database changes.

---

# 13. Folder Tree UI Support

The new `lp_note_folders` table should be designed so it can later be used to build a nested folder browser.

This feature does not need to redesign the Notes UI unless a folder tree already exists and can trivially be switched to the new table.

However, ensure that the folder records support efficient queries such as:

```sql
SELECT *
FROM lp_note_folders
WHERE parent_id = ?
ORDER BY name;
```

The folder tree should be constructible entirely from SQLite without walking the filesystem.

Do not add unnecessary UI work as part of this implementation if the current request can be completed without it.

---

# 14. Performance Requirements

Performance is a major requirement.

Avoid introducing any routine that repeatedly scans every note file.

The common startup case should be:

```text
N known folders
=
N lightweight stat() calls
```

If only two folders changed:

```text
stat all known folders
+
scandir only those two folders
```

Do not:

* recursively walk every Notes root on every startup
* hash every file
* open every note
* inspect every file modification timestamp
* run scheduled/background scans
* introduce filesystem watchers
* poll folders periodically

Use `os.scandir()` for actual directory enumeration where practical.

---

# 15. Error Handling

Filesystem access may fail because a directory:

* is temporarily unavailable
* resides on an offline drive
* resides on a disconnected network path
* has permission problems
* disappears during scanning

Handle these situations without crashing Notes startup.

A failed directory check should:

1. be logged using the existing LifePIM logging system
2. preserve enough existing index information for recovery
3. not result in destructive deletion unless absence has been reliably established according to existing application behaviour

Be conservative with unavailable roots.

A temporarily unavailable Notes root must not cause LifePIM to conclude that all Notes have been permanently deleted.

---

# 16. Database Migration

Add the new folder-index table through the existing LifePIM database migration/schema mechanism.

Do not require the user to manually rebuild or recreate the LifePIM database.

Existing installations must upgrade cleanly.

On first use after upgrade:

```text
no folder index exists
    ↓
build index from configured Notes roots
```

---

# 17. Logging

Add useful but restrained logging.

Examples:

```text
Notes folder check: 184 folders checked, 2 dirty, 0 missing
```

```text
Notes folder refreshed: Book/drafts
```

```text
Notes discovered new subtree: Book/research
```

```text
Notes full sync complete: 186 folders, 724 notes
```

Avoid logging one line for every unchanged folder during normal startup.

---

# 18. Suggested Functions

Follow the existing project structure and naming conventions, but the implementation should remain approximately this simple:

```python
def check_note_folders(...):
    """Check stored folder mtimes and refresh folders whose state changed."""
```

```python
def refresh_note_folder(...):
    """Reconcile the immediate contents of one folder. Non-recursive."""
```

```python
def add_note_folder_tree(...):
    """Recursively index a newly discovered subtree."""
```

```python
def full_sync_note_folders(...):
    """Explicitly rebuild/reconcile the complete Notes folder structure."""
```

These are normal application functions.

Do not introduce a new service, daemon, worker, queue or scheduler.

Reuse existing Notes database/access/helper modules where sensible rather than creating unnecessary architecture.

---

# 19. Tests

Add tests covering at minimum:

### Initial index

Given:

```text
Notes/
    A/
    B/
        C/
```

the folder index correctly contains the hierarchy and parent relationships.

### No filesystem changes

Run quick sync twice.

Second run should:

* stat known directories
* perform no folder enumeration/reconciliation
* result in no Notes changes

### New file

Add:

```text
A/new.md
```

The `A` directory becomes dirty.

Quick sync should rescan `A` only and add the Note.

### Deleted file

Delete a note externally.

Quick sync should detect the changed parent folder and reconcile the missing Note.

### Renamed file

Rename a note externally.

Quick sync should detect the parent folder change and reconcile correctly.

Preserve existing LifePIM Note identity/metadata where supported by current behaviour.

### New folder

Create:

```text
A/NewFolder/
    one.md
    Nested/
        two.md
```

Quick sync should detect that `A` changed, discover the new subtree recursively once, and add the folders and Notes.

### Deleted folder

Delete an indexed folder tree.

Quick sync should reconcile the missing subtree safely.

### Unavailable root

Simulate an inaccessible Notes root.

Ensure Notes startup does not crash and existing records are not destructively removed merely because the root is temporarily inaccessible.

### Full/manual sync

Make several filesystem changes and run Full Sync.

Ensure the SQLite folder index and Notes database correctly reflect the actual filesystem.

---

# 20. Definition of Done

This work is complete when:

* LifePIM has its own persistent SQLite list of folders beneath configured Notes roots.
* Folder hierarchy and parent relationships are stored.
* Folder `mtime_ns` values are stored.
* Opening Notes performs a lightweight check of known folder timestamps.
* Unchanged folders are not enumerated.
* Changed folders are individually rescanned.
* Individual folder refreshes are non-recursive.
* Newly discovered subtrees are recursively indexed once.
* Deleted/missing folders are reconciled safely.
* New, removed, renamed and moved Notes are discovered through dirty-folder reconciliation.
* A manual Full Sync performs an authoritative recursive reconciliation.
* Full Sync can repair/rebuild the folder index.
* No watchdog/background service is introduced.
* No periodic scan is introduced.
* No global scan of every note file occurs during normal startup.
* Existing Notes behaviour and metadata are preserved.
* The folder index can later be used to build an SQLite-backed nested folder browser.
* Existing LifePIM database installations migrate cleanly.
* Relevant automated tests pass.
* Existing unrelated functionality is not modified.
