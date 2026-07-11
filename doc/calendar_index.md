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
audio, or usage tables. Day view may query file/media/audio detail only for the
selected date when those sources are enabled.

## Daily Stats

High-volume sources should usually write one stat row per date, source, and
metric instead of creating an item for every source record. Current metrics are:

- `files/files_modified`
- `media/photos_taken`
- `media/videos_taken`
- `audio/tracks_added`

Usage is registered as a source but has no adapter until a usage schema is
available.

## Adding A Source

1. Add or seed a row in `lp_calendar_sources`.
2. Implement a source adapter that writes deterministic items or daily stats.
3. Keep source content authoritative in its owning table.
4. Use batched writes and update `last_refresh_*` fields.
5. Add source-specific tests for idempotency and filters.

## Migration

The migration is rerunnable. It creates missing tables/indexes/views, adds
missing columns to `lp_calendar_events`, backfills `start_date`, `start_time`,
`end_date`, `end_time`, and `all_day` from legacy `event_date`, seeds sources,
projects manual events, rebuilds recurring/birthday/holiday projections, and
builds item-day rows.

Invalid legacy dates are left unprojected rather than crashing migration.

## Troubleshooting

If in doubt - check Project filters!

Check Settings -> Calendar for source status, last refresh time, row count, and
message. If views look stale, rebuild the affected source first, then rebuild
item-days. Rebuild all enabled sources only when broad source state is suspect.

