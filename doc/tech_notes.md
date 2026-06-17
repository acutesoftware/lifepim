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
- Columns: `id`, `title`, `content`, `event_date`, `remind_date`, `project`, `user_name`, `rec_extract_date`
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
- Columns: `id`, `parent_goal_id`, `title`, `description`, `goal_date`, `remind_date`, `project`, `user_name`, `rec_extract_date`

### Tasks

- Table: `lp_tasks`
- Columns: `id`, `title`, `content`, `project`, `start_date`, `due_date`, `user_name`, `rec_extract_date`

### How

- Table: `lp_how`
- Columns: `id`, `parent_how_id`, `title`, `description`, `project`, `user_name`, `rec_extract_date`

### Notes

- Table: `lp_notes`
- Columns: `id`, `file_name`, `path`, `folder_id`, `size`, `date_modified`, `project`, `user_name`, `rec_extract_date`
- Notes can also use project folder tables for default write locations.

### Data

- Table: `lp_data`
- Columns: `id`, `name`, `description`, `tbl_name`, `col_list`, `project`, `user_name`, `rec_extract_date`

### Files

- Table: `lp_files`
- Base columns: `id`, `filelist_name`, `path`, `folder_id`, `file_type`, `project`, `user_name`, `rec_extract_date`
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
- Columns: `id`, `file_name`, `path`, `folder_id`, `file_type`, `size`, `date_modified`, `artist`, `album`, `song`, `project`, `user_name`, `rec_extract_date`
- Helper tables:
  - `lp_audio_playlists`
  - `lp_audio_playlist_items`

### 3D

- Table: `lp_3d`
- Columns: `id`, `file_name`, `path`, `folder_id`, `size`, `date_modified`, `project`, `user_name`, `rec_extract_date`

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
- Columns: `id`, `file_path`, `folder_id`, `title`, `icon`, `project`, `user_name`, `rec_extract_date`

### Admin

- Main route: `/admin/`
- Folder mapping tables:
  - `dim_folder`
  - `map_folder_project`
  - `map_project_folder`
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
