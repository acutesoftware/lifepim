# Calendar Tab

The Calendar tab is for browsing dated events, with optional overlays from indexed files, media, and audio.

Calendar events are stored in SQLite in `lp_calendar_events`. File and media overlays are read from the existing Files, Media, and Audio tables; they are not copied into `lp_calendar_events`.

## Use

Open:

```text
http://127.0.0.1:9741/calendar/
```

Main views:

- Monthly: default route, one month grid.
- Weekly: one Monday-to-Sunday week with all-day and time-slot rows.
- Daily: selected day, mini-month, events, media/audio thumbnails, and non-media file list.
- Yearly: twelve mini-months.
- List: paginated table of calendar events.

The Calendar tab is registered at `/calendar` in `src/app.py`. Routes and view logic are in:

```text
src/modules/calendar/routes.py
src/modules/calendar/templates/
```

## Navigation

The normal controls are rendered at the top of each calendar view.

- `Monthly`, `Weekly`, `Daily`, `Yearly`, and `List` switch view mode.
- `Prev` and `Next` move by the current view period.
- `Today` opens the daily view for the current local date.
- `Jump` opens a dialog for selecting year, month, and day.
- Day numbers in mini-month calendars link to the daily view.
- `+ Add` in month cells creates an event for that date.
- `Add Event` creates an event for the current selected date, or today when no date is selected.
- `Import Events` opens the CSV import workflow.

Routes:

| View | Route | Main parameters |
| --- | --- | --- |
| Month | `/calendar/` | `year`, `month`, `proj`, `show_events`, `show_files`, `show_usage` |
| Week | `/calendar/week` | `date`, `proj`, `show_events`, `show_files`, `show_usage` |
| Day | `/calendar/day` | `date`, `proj`, `show_events`, `show_files`, `show_usage` |
| Year | `/calendar/year` | `year`, `proj`, `show_events`, `show_files`, `show_usage` |
| List | `/calendar/list` | `proj`, `sort`, `dir`, `page` |
| Add | `/calendar/add` | `date`, `proj` |
| Import | `/calendar/import` | `proj` |

Dates are expected in `YYYY-MM-DD` format.

## Calendar Events

Calendar event table definition is configured in `src/common/config.py`:

```python
{'name':'lp_calendar_events', 'route':'calendar', 'display_name':'Events', 'col_list':['title','content', 'event_date', 'remind_date', 'project']}
```

Effective event columns are:

- `id`
- `title`
- `content`
- `event_date`
- `remind_date`
- `project`
- common audit columns, when present, such as `user_name` and `rec_extract_date`

In the UI, `content` is treated as the event detail body. `event_date` stores the date and optional time. Supported parsing formats are:

- `YYYY-MM-DD HH:MM:SS`
- `YYYY-MM-DD HH:MM`
- `YYYY-MM-DDTHH:MM`
- date-only values, where the first 10 characters are used as the date

Adding or editing an event writes:

- `title`
- `content`
- `event_date`, built from the submitted date and time
- empty `remind_date`
- `project`, defaulting to `General`

Delete is currently a GET route at `/calendar/delete/<event_id>` with a browser confirmation in the template.

## Project Filter

Calendar event queries accept `proj`.

If `proj` is blank, `any`, `All`, `all`, `ALL`, or `spacer`, the view shows all projects. Otherwise the route filters calendar events with:

```sql
lower(project) = lower(?)
```

The project filter applies to `lp_calendar_events`. It does not currently filter media, audio, or file overlays.

## View Sources

Month, week, day, and year views include a `View:` source box with:

- Events
- Files
- Usage

These are controlled by query parameters:

```text
show_events=1|0
show_files=1|0
show_usage=1|0
```

When any of those parameters is submitted, the selected values are also saved as defaults in `sys_settings`.

Current source behavior:

- `Events`: reads `lp_calendar_events`.
- `Files`: enables media/audio overlays and, on the daily view, the non-media file list.
- `Usage`: shows a placeholder; usage lookups are not wired yet.

Default values are defined in `src/common/settings.py`:

```python
"calendar.view.events": ("1", "Calendar", "Show events")
"calendar.view.files": ("0", "Calendar", "Show files/images")
"calendar.view.usage": ("0", "Calendar", "Show usage")
"calendar.media.thumbnail_size": ("small", "Calendar", "Thumbnail size")
"calendar.media.thumbnail_limit": ("5", "Calendar", "Thumbnails per day")
```

## Settings

Open:

```text
LifePIM Menu -> Settings -> Calendar
```

The Calendar settings page writes to `sys_settings` through `src/common/settings.py`.

Runtime settings:

| Setting key | Default | Meaning |
| --- | --- | --- |
| `calendar.view.events` | `1` | Default state for the Events source checkbox. |
| `calendar.view.files` | `0` | Default state for the Files source checkbox. |
| `calendar.view.usage` | `0` | Default state for the Usage source checkbox. |
| `calendar.media.thumbnail_size` | `small` | Thumbnail class for calendar media overlays. Valid values: `small`, `medium`, `large`. |
| `calendar.media.thumbnail_limit` | `5` | Number of media/audio preview items per day. Clamped to `1..20`. |

The source checkboxes can be changed either from the Calendar view source box or from Settings. Thumbnail size and limit are changed from Settings only.

The same Settings page also has `Rebuild from media`. That rebuilds Media tab event clusters in `lp_events` / `lp_event_items`; it does not create records in `lp_calendar_events`.

## Config Constants

Calendar layout and time-grid defaults are in `src/common/config.py`:

```python
CAL_TIMESLOT_START_TIME = 800
CAL_TIMESLOT_END_TIME = 2330
CAL_TIMESLOT_MINUTES = 30
CAL_HIGHLIGHT_DAY_DATA = 'Bold'
CAL_HIGHLIGHT_DAY_TODAY = 'Red'
CAL_COL_BG_DAY = 'white'
CAL_COL_BG_WEEKEND = '#f0f0f0'
CAL_COL_BG_TODAY = 'yellow'
CAL_TIME_START_WORK = 900
CAL_TIME_END_WORK = 1700
CAL_TIME_LUNCH_START = 1200
CAL_TIME_LUNCH_END = 1230
```

These are imported as `cfg` by `src/modules/calendar/routes.py`.

The generic config override mechanism can override `src/common/config.py` values from `sys_settings` using keys prefixed with `config.`. Those values are managed from:

```text
LifePIM Menu -> Settings -> Config
```

Examples:

```text
config.CAL_TIMESLOT_START_TIME
config.CAL_TIMESLOT_END_TIME
config.CAL_TIMESLOT_MINUTES
config.CAL_COL_BG_TODAY
```

Because these are config-level settings, they affect route rendering after the app reads the config value. Restart the app if a changed config override is not reflected immediately.

## Event Filters

Calendar event filtering is intentionally simple.

Date filters:

- Month view reads events where `event_date >= first day of month` and `event_date < first day of next month`.
- Week view reads events from Monday inclusive to the next Monday exclusive.
- Day view reads events from the selected day inclusive to the next day exclusive.
- Year view repeats month-range event queries for each month.
- List view reads all events for the selected project.

Project filters:

- `proj` filters `lp_calendar_events.project`.
- `proj=any`, `proj=All`, `proj=all`, `proj=ALL`, and `proj=spacer` are treated as no project filter.

Source filters:

- `show_events=0` suppresses `lp_calendar_events` lookups in calendar grid views.
- `show_files=0` suppresses media/audio/file overlays.
- `show_usage=0` suppresses the Usage section.

List view sorting:

- `sort=date`
- `sort=time`
- `sort=title`
- `sort=project`
- `dir=asc|desc`

List pagination uses `cfg.RECS_PER_PAGE`.

There is no free-text event search in the Calendar tab at the moment.

## File And Media Filters

The Calendar tab does not have its own file-filter editor. It reads whatever has already been imported into the Files, Media, and Audio tables.

Media/audio overlay behavior:

- Month, week, day, and year views use media/audio dates when the `Files` source is enabled.
- Images and videos come from `lp_media`.
- Audio comes from `lp_audio`.
- Image/video date uses `lp_media_meta.taken_utc` when available, otherwise `lp_media.mtime_utc`.
- Audio date uses `lp_audio.date_modified`.
- Media rows are limited to `media_type in ('image', 'video')`.
- Audio rows are included as `media_type = 'audio'`.

Daily non-media file behavior:

- Daily view also reads `lp_files` when the `Files` source is enabled.
- It matches `substr(mtime_utc, 1, 10)` to the selected day.
- If `lp_files.is_deleted` exists, deleted rows are excluded with `COALESCE(is_deleted, 0) = 0`.
- Image and video files are skipped so media is not duplicated between the media thumbnail area and the file list.

Skipped daily file extensions:

```text
.jpg .jpeg .png .gif .webp .bmp .tif .tiff .mp4 .mov .avi .mkv .webm
```

Skipped daily file types:

```text
image images media photo video
```

To change what appears as files or media on the calendar, change the upstream import/migration filters and reload the relevant tables.

Media migration filters are configured at:

```text
LifePIM Menu -> Settings -> Media
```

Default media filters in `src/common/config.py` are:

```python
FILELIST_IMAGE_WHERE = r"WHERE folder_name IN ('Photos', 'Movies', 'TV Shows')"
FILELIST_AUDIO_WHERE = r"WHERE folder_name = 'Music'"
```

These are saved as config overrides in `sys_settings` when changed from Settings. See `doc/tab_media.md` for the full Media migration details.

## Import Events

Open:

```text
Calendar tab -> Import Events
```

The import workflow uses `utils/importer.py` through `src/modules/calendar/routes.py`.

Import steps:

1. Enter a CSV path or upload a CSV file.
2. Load headers.
3. Map CSV columns to the calendar table columns.
4. Use `{curr_project_selected}` when the imported project should be the currently selected `proj`.
5. Import into `lp_calendar_events`.

The mapped columns correspond to `config.py` `col_list`:

```text
title, content, event_date, remind_date, project
```

## Related Tables

Calendar view tables:

| Table | Used for |
| --- | --- |
| `lp_calendar_events` | User calendar events. |
| `lp_media` | Image/video overlays. |
| `lp_media_meta` | Taken date for image/video overlays. |
| `lp_audio` | Audio overlays. |
| `lp_files` | Daily non-media file list. |
| `sys_settings` | Calendar runtime settings and config overrides. |

Media event tables:

| Table | Used for |
| --- | --- |
| `lp_events` | Media tab clustered events. |
| `lp_event_items` | Media-to-event memberships. |

Media events are separate from Calendar events. Rebuilding media events does not write to `lp_calendar_events`.
