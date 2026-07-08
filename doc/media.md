# Media Tab

The Media tab is for browsing local image and video files that have already been indexed into the LifePIM SQLite database. It stores file metadata and paths; it does not store image blobs or generated thumbnails in the database.

The UI reads media from `lp_media` and streams the real file through `/media/file/<media_id>` for thumbnails and previews.

## Use

Open:

```text
http://127.0.0.1:9741/media/
```

Main views:

- All Media: flat browse of indexed media.
- Timeline: media grouped by year, month, or day.
- Albums: manually curated sets of media.
- Events: automatically clustered media events.
- Smart Views: saved search/filter combinations.

Display modes:

- Filmstrip: default browse mode with thumbnails and metadata.
- Grid: compact thumbnail grid.
- Table: metadata-first list.

The right inspector shows the selected item preview, file path, taken/modified time, dimensions, camera metadata, tags, album membership, event membership, and an Open folder link when the file exists locally.

## Filters

Search uses the toolbar `Search media` field. Each search term must match somewhere in the media record. Quoted phrases are treated as phrases. Search covers:

- filename
- path
- extension
- media type
- camera make/model
- tags

Other filters:

- Media type: All types, Images, or Videos.
- Sort: taken date descending, modified date descending, or filename.
- Timeline year: available in Timeline and Events views.
- Group by: year, month, or day in Timeline view.
- Album filter: select an album in Albums view.
- Event filter: select an event in Events view.
- Smart View: save the current search/media type/sort and reuse it later.
- Search everywhere: ignores the current album/event/smart base scope and searches the broader media set.

Bulk actions work on selected media items:

- Add to album.
- Remove from album, when inside an album.
- Tag.
- Copy paths, handled client-side by the browser script.

## Migrate

Media and audio are migrated from the filelister SQLite database, configured in `src/common/config.py`:

```python
FILELIST_DB = r"D:\TRANSFER_NAS\filelister\filelist_master.db"
FILELIST_IMAGE_WHERE = r"WHERE folder_name IN ('Photos', 'Movies', 'TV Shows')"
FILELIST_AUDIO_WHERE = r"WHERE folder_name = 'Music'"
```

Open:

```text
LifePIM Menu -> Settings -> Media
```

The Settings page shows:

- Source database path.
- Image source `WHERE` clause.
- Audio source `WHERE` clause.
- `Save filters`.
- `Migrate images/videos from filelist`.
- `Migrate audio from filelist`.

The filters are saved as config overrides in `sys_settings`, so they can be changed without editing `config.py`.

### Image and Video Migration

The `Migrate images/videos from filelist` button reloads the Media tab from:

- `u_image_files` for images.
- `fl_video`, joined to `filelist_output`, for videos.

Both sources use the Image source `WHERE` clause. The default is:

```sql
WHERE folder_name IN ('Photos', 'Movies', 'TV Shows')
```

Before loading, the migration clears the Media tables:

- `lp_media`
- `lp_media_meta`
- `lp_media_tags`
- `lp_event_items`
- `lp_events`
- album item links and album covers that reference media

Images are loaded into `lp_media` with:

- full file path in `lp_media.path`
- filename
- extension
- `media_type = image`
- `size_bytes` from `filelist_size`, falling back to `image_size`
- `mtime_utc` from `u_image_files.modified`
- `ctime_utc` from `u_image_files.created`
- hash from `u_image_files.hash`

Image metadata is loaded into `lp_media_meta`:

- `taken_utc` from EXIF date fields when available.
- width and height.
- GPS latitude and longitude.
- camera make and model.

Videos are loaded into `lp_media` with `media_type = video`. Video metadata is loaded into `lp_media_meta`:

- width and height.
- duration in seconds.
- frame rate.

### Audio Migration

The `Migrate audio from filelist` button reloads the Audio tab from `fl_audio`, joined to `filelist_output` so the audio filter can use `folder_name`.

The default Audio source `WHERE` clause is:

```sql
WHERE folder_name = 'Music'
```

Before loading, the migration clears:

- `lp_audio_playlist_items`, when it exists.
- `lp_audio`.

Audio rows are loaded into `lp_audio` with:

- file name.
- containing path.
- folder mapping id.
- file type / extension.
- size.
- date modified, derived from the audio `date` field when present.
- artist, album, and song title.

### WHERE Clauses

The `WHERE` clauses are appended directly to the filelister source query. They must:

- start with `WHERE`
- not contain semicolons
- use columns available from the source query

For images and videos, `folder_name` comes from:

- `u_image_files.folder_name`
- `filelist_output.folder_name` joined to `fl_video`

For audio, `folder_name` comes from `filelist_output.folder_name` joined to `fl_audio`.

### Event Generation

Media events are separate from Calendar events. They use:

- `lp_events`
- `lp_event_items`

They do not write to `lp_calendar_events`.

Current rebuild button:

```text
Media tab -> Events -> Rebuild events
```

Current event rebuild behavior:

1. Reads all media ordered by `COALESCE(lp_media_meta.taken_utc, lp_media.mtime_utc)`.
2. Deletes all existing rows from `lp_event_items`.
3. Deletes all existing rows from `lp_events`.
4. Starts a new event cluster when:
   - the gap from the previous item is greater than 2 hours, or
   - the date changes, when split-on-day is enabled.
5. Creates one `lp_events` row per cluster.
6. Adds each clustered media item to `lp_event_items`.
7. Titles each generated event as `Event YYYY-MM-DD`.
8. Marks generated events with `event_source = 'auto'`.

Current limitations:

- Rebuild is manual.
- Rebuild is destructive for media events because it deletes existing media event rows first.
- Renamed event titles are lost on rebuild.
- Event location is not inferred.
- Event quality depends on `taken_utc`; without it, filesystem modified time is used.

## Migration Sources

### Images: `u_image_files` -> `lp_media`

Default filter:

```sql
WHERE folder_name IN ('Photos', 'Movies', 'TV Shows')
```

| Source column | LifePIM column | Notes |
| --- | --- | --- |
| `filepath` | `lp_media.path` | Full file path and uniqueness key. |
| `basename` | `lp_media.filename` | Falls back to basename from `filepath`. |
| `basename` / `format` | `lp_media.ext` | Extension is taken from filename first, then `format`. |
| fixed value | `lp_media.media_type` | Always `image`. |
| `filelist_size` / `image_size` | `lp_media.size_bytes` | Prefers `filelist_size`, falls back to `image_size`. |
| `modified` | `lp_media.mtime_utc` | Normalized to UTC text format. |
| `created` | `lp_media.ctime_utc` | Falls back to `mtime_utc`. |
| `hash` / `thumb_sha1` / `phash` / `ahash` | `lp_media.hash` | Uses first populated value. |
| `path` | `lp_media.folder_id` | Upserts `dim_folder` and stores the folder id. |

### Images: `u_image_files` -> `lp_media_meta`

| Source column | LifePIM column | Notes |
| --- | --- | --- |
| `exif_datetime` / `cam_date_digitized` | `lp_media_meta.taken_utc` | Uses first parseable EXIF date. |
| `width` | `lp_media_meta.width` | Image width. |
| `height` | `lp_media_meta.height` | Image height. |
| `lat` | `lp_media_meta.gps_lat` | Empty values become null. |
| `lon` | `lp_media_meta.gps_lon` | Empty values become null. |
| `cam_make` | `lp_media_meta.camera_make` | Camera make. |
| `cam_model` | `lp_media_meta.camera_model` | Camera model. |

### Videos: `fl_video` + `filelist_output` -> `lp_media`

`fl_video` is joined to `filelist_output` on:

```sql
filelist_output.file_path = fl_video.filepath
```

The joined query uses the same Image source `WHERE` clause, usually filtering `folder_name` to `Movies` and `TV Shows`.

| Source column | LifePIM column | Notes |
| --- | --- | --- |
| `fl_video.filepath` | `lp_media.path` | Full file path and uniqueness key. |
| `fl_video.basename` | `lp_media.filename` | Falls back to basename from `filepath`. |
| `fl_video.basename` / `filelist_output.file_type` | `lp_media.ext` | Extension is taken from filename first, then file type. |
| fixed value | `lp_media.media_type` | Always `video`. |
| `fl_video.file_size` / `fl_video.size` | `lp_media.size_bytes` | Prefers `file_size`, falls back to `size`. |
| `filelist_output.modified` | `lp_media.mtime_utc` | Normalized to UTC text format. |
| `filelist_output.created` | `lp_media.ctime_utc` | Falls back to `mtime_utc`. |
| `filelist_output.hash` | `lp_media.hash` | File hash when available. |
| `fl_video.path` | `lp_media.folder_id` | Upserts `dim_folder` and stores the folder id. |

### Videos: `fl_video` + `filelist_output` -> `lp_media_meta`

| Source column | LifePIM column | Notes |
| --- | --- | --- |
| `fl_video.width` | `lp_media_meta.width` | Video width. |
| `fl_video.height` | `lp_media_meta.height` | Video height. |
| `fl_video.duration` | `lp_media_meta.duration_sec` | Duration in seconds. |
| `fl_video.frame_rate` | `lp_media_meta.fps` | Frames per second. |

### Audio: `fl_audio` + `filelist_output` -> `lp_audio`

`fl_audio` is joined to `filelist_output` on:

```sql
filelist_output.file_path = fl_audio.filepath
```

Default filter:

```sql
WHERE folder_name = 'Music'
```

| Source column | LifePIM column | Notes |
| --- | --- | --- |
| `fl_audio.basename` | `lp_audio.file_name` | Falls back to basename from `filepath`. |
| `fl_audio.path` | `lp_audio.path` | Containing folder path. |
| `fl_audio.path` | `lp_audio.folder_id` | Upserts `dim_folder` and stores the folder id. |
| `fl_audio.basename` | `lp_audio.file_type` | Extension from filename. |
| `fl_audio.size` | `lp_audio.size` | Stored as text for the existing audio table shape. |
| `fl_audio.date` | `lp_audio.date_modified` | Normalized to date text when parseable. |
| `fl_audio.artist` | `lp_audio.artist` | Audio tag. |
| `fl_audio.album` | `lp_audio.album` | Audio tag. |
| `fl_audio.title` | `lp_audio.song` | Falls back to filename without extension. |
| fixed blank | `lp_audio.project` | Project is currently left blank. |
