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
| Import CSV | `/calendar/import` | CSV imports remain supported. Mapped rows are previewed before confirmation and then trigger Calendar migration/projection. |
| Import public holidays | `/calendar/import/holidays/<source_key>` | Previews and imports an inclusive year range for the AU or SA source. Confirmation replaces only that source's rows inside the selected years. |
| Import external events | `/calendar/import/external` | Previews an iCalendar (`.ics`) file. Re-importing the same calendar name replaces only that external calendar's prior rows. |
| Edit Birthdays | `/calendar/birthdays` | Adds, edits, and deletes annual all-day birthday events using a name and MM/DD. |
| View event | `/calendar/view/<event_id>` | Shows an editable Calendar event. Edit and Delete actions are located on this page. |
| View indexed item | `/calendar/item/<item_id>` | Shows a read-only imported or generated item, such as a public holiday or external event without an authoritative event row. |

`/calendar/list` remains the compatibility route, but the UI labels it Agenda.

Weekday dates containing a selected AU or SA holiday use the configurable
Holiday highlight colour from Settings > Calendar. Weekend holiday dates keep
the weekend background; their holiday label (or date number in compact year
views) is shown in green instead.

Birthdays are authoritative rows in `lp_calendar_events` with
`event_type='birthday'` and an annual recurrence rule, but are projected only
through the `birthdays` source. Explicit source selections take precedence over
legacy grouped filters, so the Birthdays checkbox remains effective while
navigating between months. Birthday cells use the background, text colour, and
font size configured in Settings > Calendar. Birthday projections cover whole
calendar years and default to 20 years before and after today. Existing
future-only birthday source settings are upgraded once, which ensures birthdays
that have already occurred in the current year remain visible. Editing a name
rebuilds the generated occurrences, so the new name is used on every year.

Calendar grids now show each event as one uncluttered title link instead of a
boxed event with separate View, Edit, and Delete controls. The link opens view
mode. Editable events expose Edit and Delete there; imported/generated items
without an authoritative event record are read-only and identify their source.
The Month view has one Add Event action in its toolbar and no per-day `+ Add`
links.

The toolbar `...` menu contains CSV import, AU and SA public-holiday import,
external iCalendar import, and Edit Birthdays. Every import presents a preview
before confirmation. Re-importing public holidays first removes only the chosen
jurisdiction and selected year range; re-importing an external calendar replaces
only rows belonging to the supplied calendar name.

## Source Filters

The source filter is driven by `lp_calendar_sources`. Query parameters support:

- `source` repeated values from the source checkbox form.
- `sources` as a comma-separated source key list, used for navigation
  persistence.
- legacy `show_events`, `show_files`, and `show_usage` parameters.

Default visibility, enabled state, colours, icons, priority, horizons, and
refresh state are managed in Settings -> Calendar.

### Checkbox reference

The `Calendars / Sources` form submits one repeated `source` value for each
checked box plus `source_filter=1`. Therefore each visible checkbox selects its
exact `source_key`; clearing every box intentionally selects no sources. Only
enabled sources can return indexed events. Date range, `is_visible`,
non-cancelled status, and the current Area filter are then applied to indexed
items. A normal Area selection includes that Area and its child Areas;
`Unmapped` matches blank/unmapped values.

| Checkbox | Source key | What it includes | Additional source filters or notes |
|---|---|---|---|
| Manual Events | `manual` | Non-recurring events entered in Calendar and stored in `lp_calendar_events`. | Indexed by event dates; cancelled/hidden rows are excluded. Area filtering applies. |
| Recurring Events | `recurring` | Generated occurrences for recurring Calendar events. | Birthdays are explicitly excluded and appear only under Birthdays. Projection is limited by the source past/future horizon. |
| Birthdays | `birthdays` | Annual all-day birthday occurrences entered through Edit Birthdays, plus compatible legacy yearly events whose title ends in Birthday. | Uses full boundary years, maps 29 February to 28 February in non-leap years, and uses the birthday colours/font from Settings > Calendar. |
| Australian Public Holidays | `holidays_au` | Imported national AU public holidays for the confirmed year range. | Does not include SA-only holidays such as Adelaide Cup or SA Labour Day. Re-import replaces this source only in the selected years. |
| South Australian Public Holidays | `holidays_sa` | Imported SA holidays, including applicable national holidays and SA-specific dates. | Re-import replaces this source only in the selected years. Weekday cells use the configured holiday background; weekend holidays retain the weekend background and use green text. |
| External Events | `external_events` | Occurrences imported from an `.ics` calendar for the chosen year range. | Recurrence and excluded dates are expanded during import. Re-import replacement is scoped to the external calendar name. These items are read-only in Calendar. |
| Task Deadlines | `tasks` | Indexed task deadline items, when provided by a task adapter. | Registered but not visible by default. There is currently no refresh adapter, so checking it normally returns no items unless task projections already exist. |
| File Activity | `files` | Daily counts from `lp_files.mtime_utc` and non-media file details on an opened day. | Deleted file rows are excluded when `is_deleted` exists. In Month/Week previews this selection also enables image/video previews from `lp_media`. |
| Photos and Videos | `media` | Daily photo/video counts and image/video previews from `lp_media`. | Only `media_type` image/video rows are previewed, using `mtime_utc` as the displayed Calendar date. |
| Audio | `audio` | Daily audio counts and audio previews from `lp_audio`. | Uses `date_modified` as the Calendar date. |
| Usage | `usage` | Intended usage/activity data. | Registered but no adapter is currently wired, so it shows no records. |

The opened Day view currently treats File Activity, Photos and Videos, and
Audio as one detail group: selecting any one enables the shared file/media
detail loaders. Month and Week previews are more source-specific, except that
File Activity deliberately enables image/video previews as noted above.

When the page has no explicit source selection, checkboxes start from each
source's `visible_by_default` setting. Navigation carries the exact selection in
the comma-separated `sources` parameter. The older `show_events`, `show_files`,
and `show_usage` parameters are compatibility groups; they are used only when
an explicit `source`/`sources` selection is absent, and explicit source choices
always win.

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

The rebuild buttons map to these code paths:

| Button | What it does | When to use |
|---|---|---|
| Rebuild source | Rebuilds the selected source from the dropdown. | Use when one source looks stale or its configuration changed. |
| Rebuild all enabled | Rebuilds all enabled source projections/stats. | Use after broad Calendar source changes. |
| Rebuild item days | Rebuilds `lp_calendar_item_days` from existing `lp_calendar_items`. | Use when event placement is wrong but source items are correct. |
| Rebuild daily stats | Rebuilds historical `lp_calendar_day_stats` for files, media, and audio. | Use when old file/media/audio indicators are missing. |

Large source refreshes should be run from Settings rather than during ordinary
calendar navigation.

## Daily Stats And Historical Baseline

File, media, and audio counts are shown from `lp_calendar_day_stats`, not by
scanning source tables during every Calendar view. Calendar navigation refreshes
a recent rolling window for selected daily-stat sources.

Old dates need a historical baseline once. If a selected daily-stat source has
data but no baseline marker, Calendar shows a prompt asking whether to build the
baseline. Accepting it posts to `/calendar/day-stats-baseline` and calls
`calendar_index.rebuild_calendar_day_stat_baselines()` for the selected sources.

Admin -> Migration also refreshes Calendar daily stats after FileLister media or
audio migration, so a separate Calendar rebuild is normally not needed after
using those migration buttons.

## Limitations

- People/contact birthday projection is graceful no-data unless a compatible
  people schema is introduced. Birthday events in `lp_calendar_events` are
  supported now.
- Usage is registered as a source but has no adapter until the usage schema is
  standardised. The new logger `activity_session` table is not yet wired into
  Calendar.
- File/media/audio runtime grids use daily stats. Detailed source rows are only
  queried for an opened day.
