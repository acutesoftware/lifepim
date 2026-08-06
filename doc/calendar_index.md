# Calendar Materialised Index

LifePIM Calendar uses disposable projection tables for runtime reads.
Authoritative records remain in their owner tables. Manual and recurring calendar
definitions are authoritative in `lp_calendar_events`; views read
`lp_calendar_items`, `lp_calendar_item_days`, `lp_calendar_day_stats`, and
`lp_calendar_sources`.

## Tables

- `lp_calendar_sources`: source registry, default visibility, style, horizons,
  refresh mode, and last refresh status.
- `lp_calendar_events`: authoritative manual and recurring event definitions.
  Legacy `event_date` is retained for compatibility.
- `lp_calendar_items`: one indexed row per event occurrence or generated item.
- `lp_calendar_item_days`: one row per occupied date for fast month/week/day
  lookups and multi-day rendering.
- `lp_calendar_day_stats`: daily summary metrics for high-volume sources such as
  files, media, audio, and usage.

The projection tables are rebuildable. Do not edit `lp_calendar_items` directly
as the source of truth.

## Refresh Modes

- `immediate`: manual event create/edit/delete updates projections during the
  request.
- `rebuild`: recurring events, birthdays, and holidays are regenerated for their
  configured horizons.
- `incremental`: file/media/audio daily stats can be refreshed independently.
- `manual`: reserved for future sources that should not refresh automatically.

Use Settings -> Calendar to rebuild one source, rebuild all enabled sources,
rebuild item-days, or rebuild daily stats.

## Recurrence

Recurring definitions store a restricted iCalendar-style `recurrence_rule`.
Supported rules include daily, weekly, selected weekdays, fortnightly,
monthly-by-day, monthly ordinal weekday, yearly, interval, end date, and count.
Default recurring projection is two years back and ten years forward unless the
source row overrides its horizon.

Occurrence keys are deterministic, for example:

```text
manual:412
recurring:27:2029-05-17
holiday:AU-SA:2030-04-25:Anzac Day
```

Rerunning a refresh is idempotent.

## Runtime Queries

Month, week, day, and year routes use `lp_calendar_item_days` joined to
`lp_calendar_items` and `lp_calendar_sources`. Agenda uses `lp_calendar_items`
with indexed filters. Summary uses upcoming indexed items, grouped counts,
daily stats, and source refresh status.

Grid navigation does not expand recurrence and does not scan files, media,
audio, or usage tables for event rows. Day view may query file/media/audio
detail only for the selected date when those sources are enabled.

The main event query is `calendar_index.fetch_calendar_items_for_days()`:

```sql
SELECT ci.*, cid.item_date, cid.day_number, cid.total_days,
       cid.is_first_day, cid.is_last_day,
       cs.source_name, cs.default_color, cs.default_text_color, cs.default_icon
FROM lp_calendar_item_days cid
JOIN lp_calendar_items ci ON ci.id = cid.calendar_item_id
JOIN lp_calendar_sources cs ON cs.source_key = ci.source_key
WHERE cid.item_date >= ?
  AND cid.item_date < ?
  AND ci.is_visible = 1
  AND cs.enabled = 1
  AND ci.status != 'cancelled'
ORDER BY cid.item_date, ci.all_day DESC, ci.start_time, ci.sort_priority, ci.title;
```

Source and Area filters are appended to that query when selected.

## Media On The Calendar

Media display uses two paths:

- thumbnails/details are read directly from owner tables at request time;
- daily counts are materialised into `lp_calendar_day_stats`.

This means media thumbnails do not need `lp_calendar_items` or
`lp_calendar_item_days` projection first. They do need the media import/indexing
pipeline to have populated `lp_media`. The source checkbox still controls
whether the route asks for media, and the summary/stat panels need
`lp_calendar_day_stats` to be rebuilt before their counts are current.

The route source parsing has a compatibility grouping: the legacy `show_files`
toggle enables `files`, `media`, and `audio` together. When the explicit source
selector is used, media thumbnails are fetched when `media` is selected. The
route also treats `files` as enabling media previews for older links/settings.

The current media thumbnail query is in `routes._fetch_media_rows()`. If
`lp_media_meta.taken_utc` exists it is selected, but the displayed calendar date
is still `lp_media.mtime_utc`:

```sql
SELECT m.media_id, m.path, m.filename, m.ext, m.media_type,
       m.size_bytes, m.mtime_utc, meta.taken_utc,
       m.mtime_utc AS display_date
FROM lp_media m
LEFT JOIN lp_media_meta meta ON meta.media_id = m.media_id
WHERE lower(m.media_type) IN ('image', 'video')
  AND m.mtime_utc >= ?
  AND m.mtime_utc < ?
ORDER BY display_date, lower(m.filename);
```

Without `lp_media_meta` the same query runs against `lp_media` only, with
`NULL AS taken_utc`.

Month and week views call `_fetch_image_media()` for the visible date range and
group rows by `display_date`. Day view calls `_fetch_day_media()` for a single
date and renders the media grid. Audio uses the same direct-detail approach
against `lp_audio.date_modified`.

The media schema creates `idx_lp_media_mtime` on `lp_media(mtime_utc)`, which
matches the direct thumbnail range query. It also creates
`idx_lp_media_meta_taken` on `lp_media_meta(taken_utc)`, but Calendar does not
currently use `taken_utc` as the display date.

Current daily media stats are built by `calendar_index._stats_media()`:

```sql
SELECT substr(mtime_utc, 1, 10) AS stat_date,
       lower(media_type) AS media_type,
       COUNT(1) AS cnt
FROM lp_media
WHERE substr(mtime_utc, 1, 10) >= ?
  AND substr(mtime_utc, 1, 10) < ?
GROUP BY substr(mtime_utc, 1, 10), lower(media_type);
```

The resulting metrics are `media/photos_taken` for non-video media and
`media/videos_taken` for video media. The metric names are historical; the
current implementation groups by file modified time, not EXIF taken time. To
show photos on the date taken instead, change both `_fetch_media_rows()` and
`_stats_media()` to use `COALESCE(lp_media_meta.taken_utc, lp_media.mtime_utc)`
as the display/stat date.

The stats query uses `substr(mtime_utc, 1, 10)` so it is an aggregation pass, not
the same indexed range query used for thumbnails. For very large media tables,
prefer a date expression index or rewrite the stats adapter to use indexed
`mtime_utc` ranges.

## Daily Stats

High-volume sources should usually write one stat row per date, source, and
metric instead of creating an item for every source record. Current metrics are:

- `files/files_modified`
- `media/photos_taken`
- `media/videos_taken`
- `audio/tracks_added`

Usage is registered as a source but has no adapter until a usage schema is
available.

Stats are read with `calendar_index.fetch_calendar_day_stats()`:

```sql
SELECT *
FROM lp_calendar_day_stats
WHERE stat_date >= ?
  AND stat_date < ?
ORDER BY stat_date, source_key, metric_key;
```

Rebuilding stats does not rebuild thumbnails. It refreshes summary/count rows
only. Direct file/media/audio details reflect whatever is currently in their
owner tables.

### Stats Refresh Strategy

`lp_calendar_day_stats` supports full and date-bounded refreshes.

Full refresh is appropriate after an import that can add, remove, or rewrite
old-dated records. For example, the Admin media and audio migration actions
rebuild the full `media` or `audio` calendar stats source after they repopulate
`lp_media` or `lp_audio`.

Rolling refresh is appropriate during normal app use. Calendar routes call
`refresh_recent_calendar_day_stats()` before reading stats. It refreshes selected
high-volume sources for a bounded window, currently 45 days back through
tomorrow, and skips sources refreshed within the last 24 hours. This keeps recent
file/media/audio summaries fresh without scanning every historical date on
every Calendar page load.

Historical baseline refresh is explicit. When Calendar sees selected
file/media/audio sources that have source rows but no
`stats_baseline_built_at` marker in `lp_calendar_sources.config_json`, it shows
a confirmation dialog. If the user accepts, the dialog posts to
`calendar.day_stats_baseline_route()`, which calls
`calendar_index.rebuild_calendar_day_stat_baselines()` for the selected sources.
That performs a full source refresh and records baseline metadata such as
`stats_baseline_built_at`, `stats_baseline_min_date`, and
`stats_baseline_max_date`.

Accept the dialog when old month/year views should show historical file, media,
or audio activity markers. Dismiss it when the historical activity dots are not
needed right now. Dismissal is remembered for the current browser session only;
the source remains eligible until the baseline is built.

Use `refresh_calendar_source(source_key, from_date, to_date, full_rebuild=True)`
for a bounded refresh. The `full_rebuild=True` flag matters: it deletes existing
stats for that source/date range before re-aggregating, so a day whose source
records dropped to zero is removed from `lp_calendar_day_stats`.

### Settings Rebuild Buttons

Settings -> Calendar has four manual rebuild buttons. They are still useful, but
they are mostly recovery and maintenance tools now that recent daily stats are
refreshed automatically by Calendar views.

| Button | Route action | Code path | What happens | When to use |
| --- | --- | --- | --- | --- |
| Rebuild source | `rebuild_calendar_source` | `admin.settings_route()` -> `calendar_index.refresh_calendar_source(source_key, full_rebuild=True)` | Rebuilds only the selected source from the Source dropdown. Manual events are projected from `lp_calendar_events`; recurring/birthday/holiday sources regenerate `lp_calendar_items` and `lp_calendar_item_days`; `files`, `media`, and `audio` delete and rebuild that source's daily stats. | Use after changing one source's configuration, after fixing one source's data, or when only one source looks stale. For `media`/`audio` after Admin migration this is normally not needed because migration already rebuilds that source's stats. |
| Rebuild all enabled | `rebuild_calendar_all` | `admin.settings_route()` -> `calendar_index.refresh_all_calendar_sources(enabled_only=True)` -> `refresh_calendar_source(..., full_rebuild=True)` for each enabled source | Runs the same source rebuild logic for every enabled row in `lp_calendar_sources`. Disabled sources are skipped. | Use after broad calendar schema/config changes, after restoring a database, or when several enabled sources look wrong. It is broader and slower than rebuilding one source. |
| Rebuild item days | `rebuild_calendar_item_days` | `admin.settings_route()` -> `calendar_index.rebuild_calendar_item_days()` | Deletes and rebuilds `lp_calendar_item_days` from existing `lp_calendar_items`. It does not regenerate source items and does not touch `lp_calendar_day_stats`. | Use only when month/week/day event placement looks wrong but `lp_calendar_items` itself looks correct. This is a repair button for the derived day-span index. |
| Rebuild daily stats | `rebuild_calendar_stats` | `admin.settings_route()` -> `calendar_index.rebuild_calendar_day_stat_baselines()` | Re-aggregates all current daily stat adapters: `files`, `media`, and `audio`. It upserts counts into `lp_calendar_day_stats`, records historical baseline metadata for non-empty sources, and does not rebuild thumbnails or event items. | Use after a file/media/audio import that did not run through the Admin migration hooks, after manually editing source tables, or when historical activity dots/counts are missing. Normal Calendar browsing refreshes only the recent rolling window, not every old date. |

In normal use, prefer the narrowest button. The common order for diagnosis is:
first rebuild the affected source, then rebuild item days if event placement is
still wrong. Use Rebuild daily stats when the problem is missing file/media/audio
activity counts rather than missing event rows.

## Adding A Source

There are two source patterns.

Use indexed calendar items when each source record is a real event the user
should see individually. Examples: walking trips, appointments imported from an
external calendar, travel bookings, or dated notes.

Use daily stats plus an optional direct detail query when the source is
high-volume and the calendar should mostly show counts. Examples: all files
modified on a day, photos/videos, audio files, or usage logs.

For an indexed item source:

1. Add a source seed in `calendar_index.SOURCE_SEEDS` or insert a row into
   `lp_calendar_sources`.
2. Keep the authoritative data in its owner table.
3. Add a branch to `refresh_calendar_source(source_key, ...)`.
4. Implement an adapter that deletes/replaces that source's projected rows for
   the requested date range and upserts deterministic `lp_calendar_items`.
5. Let `_upsert_item()` write `lp_calendar_item_days`, or rebuild item-days
   after bulk changes.
6. Add tests for idempotency, date filtering, source filtering, and Area
   filtering if the source has Areas.

For a daily-stat source:

1. Add a source row in `lp_calendar_sources`.
2. Add a `_stats_<source>()` adapter that groups owner-table rows by date.
3. Write one or more metrics into `lp_calendar_day_stats` with `_upsert_stats()`.
4. Add the source to `rebuild_calendar_day_stats()` or call it from
   `refresh_calendar_source()`.
5. Add a direct-detail query in `routes.py` only if the UI needs clickable rows,
   thumbnails, or drill-down for a selected date/range.

### Example: Walking Trips

Walking trips are better as indexed calendar items than daily stats because each
walk has a start time, end time, start location, and end location.

Authoritative table example:

```sql
CREATE TABLE IF NOT EXISTS lp_walking_trips (
    walk_id INTEGER PRIMARY KEY,
    walk_date TEXT NOT NULL,
    time_start TEXT,
    lat_long_start TEXT,
    time_end TEXT,
    lat_long_end TEXT,
    title TEXT,
    distance_m REAL,
    notes TEXT,
    updated_at TEXT
);
```

Source seed example:

```python
(
    "walking", "Walking Trips", "activity", "incremental",
    None, None, "#2ca02c", "#ffffff", "map", 60, 1, 1
)
```

Refresh query example:

```sql
SELECT walk_id, walk_date, time_start, time_end,
       lat_long_start, lat_long_end, title, distance_m, notes, updated_at
FROM lp_walking_trips
WHERE walk_date >= ?
  AND walk_date < ?;
```

Each row should become one projected item:

```text
source_key:       walking
source_record_id: walk_id
occurrence_key:   walking:<walk_id>
title:            title or "Walk"
start_date:       walk_date
start_time:       time_start
end_date:         walk_date
end_time:         time_end
all_day:          0
blocks_time:      0
event_type:       walk
category:         walking
location:         lat_long_start
content:          lat_long_start -> lat_long_end, notes, distance
```

If the calendar should also show daily totals, add a second stats adapter that
groups `lp_walking_trips` by `walk_date` and writes metrics such as
`walking/walks` and `walking/distance_km` into `lp_calendar_day_stats`.

### Example: File Metadata

The "files modified on this date" use case already exists as the `files` source.
It reads from `lp_files.mtime_utc`.

Daily stats:

```sql
SELECT substr(mtime_utc, 1, 10) AS stat_date,
       COUNT(1) AS cnt
FROM lp_files
WHERE substr(mtime_utc, 1, 10) >= ?
  AND substr(mtime_utc, 1, 10) < ?
  AND COALESCE(is_deleted, 0) = 0
GROUP BY substr(mtime_utc, 1, 10);
```

Day view detail:

```sql
SELECT id, path, mtime_utc, filelist_name, file_type, size
FROM lp_files
WHERE substr(mtime_utc, 1, 10) = ?
  AND COALESCE(is_deleted, 0) = 0
ORDER BY mtime_utc, lower(path);
```

For all-file history, prefer the existing stats/detail approach. Creating one
`lp_calendar_items` row per file would make month/week views noisy and can grow
the projection tables very quickly.

Unlike `lp_media`, the current importer schema only ensures `lp_files.mtime_utc`
exists; it does not create a dedicated `lp_files(mtime_utc)` index. The current
Calendar file queries also use `substr(mtime_utc, 1, 10)`. If file history
becomes slow on a large database, add an expression index on
`substr(mtime_utc, 1, 10)` or change the queries to use `mtime_utc >= ? AND
mtime_utc < ?` with a normal `lp_files(mtime_utc)` index.

## Migration

The migration is rerunnable. It creates missing tables/indexes/views, adds
missing columns to `lp_calendar_events`, backfills `start_date`, `start_time`,
`end_date`, `end_time`, and `all_day` from legacy `event_date`, seeds sources,
projects manual events, rebuilds recurring/birthday/holiday projections, and
builds item-day rows.

Invalid legacy dates are left unprojected rather than crashing migration.

## Troubleshooting

If in doubt - check Area filters!

Check Settings -> Calendar for source status, last refresh time, row count, and
message. If views look stale, rebuild the affected source first, then rebuild
item-days. Rebuild all enabled sources only when broad source state is suspect.
