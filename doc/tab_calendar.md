# Calendar Tab

The Calendar tab is registered at `/calendar` and implemented in
`src/modules/calendar/routes.py` with templates under
`src/modules/calendar/templates/`.

Calendar uses a materialised index. Runtime views read indexed Calendar
tables instead of calculating recurrence or scanning large source tables.
Architecture details are in `doc/calendar_index.md`.

## Views

| View | Route | Notes |
|---|---|---|
| Month | `/calendar/` | Indexed item-day query for the selected month. |
| Week | `/calendar/week` | Indexed item-day query for Monday-Sunday. |
| Day | `/calendar/day` | Indexed item-day query plus optional detail for the selected day. |
| Year | `/calendar/year` | Indexed markers and daily stats. |
| Agenda | `/calendar/list` | Indexed item search, filters, sorting, and pagination. |
| Summary | `/calendar/summary` | Upcoming items, grouped counts, stats, and source status. |
| Add/Edit | `/calendar/add`, `/calendar/edit/<id>` | Writes authoritative event rows and immediately updates projections. |
| Import | `/calendar/import` | Legacy CSV imports remain supported and trigger Calendar migration/projection. |

`/calendar/list` remains the compatibility route, but the UI labels it Agenda.

## Source Filters

The source filter is driven by `lp_calendar_sources`. Query parameters support:

- `source` repeated values from the source checkbox form.
- `sources` as a comma-separated source key list, used for navigation
  persistence.
- legacy `show_events`, `show_files`, and `show_usage` parameters.

Default visibility, enabled state, colours, icons, priority, horizons, and
refresh state are managed in Settings -> Calendar.

## Event Writes

Manual event add/edit/delete updates:

1. `lp_calendar_events`
2. matching `lp_calendar_items`
3. matching `lp_calendar_item_days`

Recurring events rebuild the `recurring` source projection. Delete uses POST in
the UI. The GET delete route remains only as a compatibility redirect and does
not delete data.

## CSV Import

Legacy imports that provide `event_date` still work. Migration derives:

- `start_date`
- `start_time`
- `end_date`
- `end_time`
- `all_day`

After import, Calendar migration/projection is rerun so imported events appear
through the index.

## Settings

Settings -> Calendar includes:

- enabled sources
- default source visibility
- source colour, icon, priority, and horizons
- media thumbnail settings
- rebuild one source
- rebuild all enabled sources
- rebuild item-day index
- rebuild daily stats
- source refresh status

Large source refreshes should be run from Settings rather than during ordinary
calendar navigation.

## Limitations

- People/contact birthday projection is graceful no-data unless a compatible
  people schema is introduced. Birthday events in `lp_calendar_events` are
  supported now.
- Usage is registered as a source but has no adapter until the usage schema is
  standardised.
- File/media/audio runtime grids use daily stats. Detailed source rows are only
  queried for an opened day.

