# Areas

Areas are the left-hand navigation taxonomy used by Notes and other LifePIM modules. They replace the older Projects terminology.

## Where Areas Are Stored

Area metadata is stored in SQLite, not in a markdown file.

- `lp_areas` stores the sidebar rows: Area ID, label, icon, group/header, sort order, status, and owner.
- `lp_area_folders` stores real disk folder mappings for an Area. Notes uses these mappings to sync files and to materialize `lp_notes.area`.
- The runtime schema and migrations are implemented in `src/common/areas.py`.
- `src/schema_areas.sql` is a schema reference file for inspection. The Python migration code is still authoritative at runtime.

The database file is configured by `common.config.DB_FILE` and is shown at the bottom of Settings > Edit Areas.

## How The Edit Areas Screen Loads Data

`/areas/edit` loads rows with:

```text
common.areas.areas_side_tabs(owner_user_id=current_user.user_id, seed=True)
```

If a user has no Area rows yet, defaults are seeded from the configured sidebar list. The page then posts the edited rows back to `common.areas.save_user_sidebar_rows()`.

The order of rows in the form becomes `lp_areas.sort_order`. The Move Up and Move Down buttons only change this order before save.

## What Each Edit Does

Changing Label, Group, Icon, or order changes navigation metadata only. It does not rewrite notes, tasks, files, folder paths, or markdown front matter.

Changing Area ID is treated as a rename when the row has an existing original Area ID. The save process updates exact matches from the old Area ID to the new Area ID in:

- `lp_area_folders.area_id`
- content tables with an `area` column
- content tables with an `area_id` column

If a table has `owner_user_id`, the update is scoped to the current user. The rename is exact-match only. It does not fuzzy-match labels, old display names, markdown front matter, or file paths.

Deleting an Area removes it from the sidebar by removing the `lp_areas` row. It does not delete notes, tasks, files, media, HOW rows, or other content. It also does not delete `lp_area_folders` mappings; re-adding the same Area ID will make those mappings visible again. Remove folder mappings from the Notes folder panel when you intend to stop using them.

Adding an Area creates a new sidebar row and, for normal Area rows, a default note folder mapping in `lp_area_folders`. The path is created under the current user's configured notes root using a safe folder name derived from the Area ID, for example `work/business` becomes `work-business`. Header rows do not get folders.

The new mapping is stored as `folder_role = 'default'`, `create_type = 'markdown'`, and `is_write_enabled = 1`. This gives the Note view's Move File action a destination immediately after the Area is saved. Adding an Area still does not move existing content; assign notes to the Area separately, then use Move File when you want the markdown file moved into the Area's default folder.

If the configured notes root is missing or cannot be created, the Area row is still saved and the Edit Areas screen reports the folder creation failure. In that case, fix the user notes root or add a default folder from the Notes folder panel before using Move File for that Area.

## Direct Database Edits

Direct SQL edits are possible but are not the safest normal workflow.

Before editing the database directly:

1. Stop LifePIM.
2. Back up the SQLite database file.
3. Edit `lp_areas` and `lp_area_folders` carefully.
4. Restart LifePIM and verify Notes filters and folder mappings.

Directly changing `lp_areas.area_id` will not automatically update notes, tasks, HOW records, or `lp_area_folders`. Use the Edit Areas screen for Area ID renames when possible because it performs the exact-reference updates described above.

## Pocket Mobile Sync Compatibility

Desktop stores the canonical taxonomy field as `area`. LifePIM Pocket may still label the same filter as Projects.

The Pocket API keeps both names compatible:

- Desktop-to-mobile manifest and item download responses include `area`, `area_id`, `project`, and `project_id` with the same canonical Area ID.
- The nested `metadata` object also includes `area`, `area_id`, `project`, and `project_id`.
- Mobile-to-desktop sync accepts `area`, `area_id`, `project`, `project_id`, or `proj` in the top-level item payload or nested `metadata` payload.
- Markdown front matter accepts `area`, `area_id`, `folder`, `sidebar_tab`, `project`, `project_id`, or `proj`.
- Legacy `project/...` and `proj/...` values are normalized to `area/...` before they are stored in `lp_notes.area`.

## Practical Guidance

Prefer stable, lowercase Area IDs such as `work/business`, `make/build`, or `area/dev/lifepim`.

Use labels for friendly display text. For example, `area/UE5` can have the label `UE5`.

Use group/header rows to organize the sidebar. Header rows do not represent content Areas.
