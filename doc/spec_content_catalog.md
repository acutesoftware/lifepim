# LifePIM Content Catalog — Implementation Specification

## 1. Purpose

Implement a core **Content Catalog** system for LifePIM.

The Content Catalog documents and configures:

* The kinds of information LifePIM can store.
* The canonical LifePIM object type for each kind.
* The top-level tab where the content normally belongs.
* The underlying database table used to store it.
* The Areas where the content kind is relevant.
* Common content patterns or use cases.
* Templates associated with a content kind.
* Views associated with a content kind.
* The current implementation or mapping status.

Examples:

* `Idea` → Note → Notes tab → `lp_notes`
* `Birthday` → Event → Calendar tab → `lp_cal_recurring`
* `Personal Journal` → Note → Notes tab → displayed using a timeline view
* `Food Shopping` → Shopping List → Lists tab → associated with the Food and Household Areas
* `Car Repair` → Repair Project → Goals/Projects tab → associated with the Vehicles Area
* `Blender Model` → Object → 3D tab → associated with the Design Area

The Content Catalog will initially be used as structured documentation and planning data. It must nevertheless be designed as production configuration data because it may later drive:

* Creation menus.
* Templates.
* Default views.
* Tab filters.
* Calendar displays.
* “Where does this go?” searches.
* Dynamic navigation.
* Content coverage reports.

The first implementation must include the full Version 1–3 data model and CRUD administration screens.

Do not implement automatic template suggestions, automatic content creation, dynamic view execution, or export functionality in this phase.

---

# 2. User Interface Location

Add a new section under the existing **Admin** area.

Admin sidebar entry:

```text
Content Catalog
```

The Content Catalog must not be added as a normal top-level LifePIM tab.

Suggested Admin navigation:

```text
Admin
├── Content Catalog
├── Content Patterns
├── Templates
└── Content Views
```

These may initially be implemented as separate pages or as tabs within one Admin Content Catalog page.

Preferred initial layout:

```text
Content Catalog
[Content Kinds] [Patterns] [Templates] [Views]
```

The primary landing page should be **Content Kinds**.

---

# 3. Important Design Rules

## 3.1 Content kind describes what something is

Examples:

* Journal entry
* Shopping list
* Birthday
* Repair project
* Physical asset
* Blender model
* Meeting note
* Recipe

## 3.2 Area describes where it is relevant

A content kind may be relevant to multiple Areas.

Examples:

* Birthday → Family, Friends, People
* Shopping list → Food, Household, Travel
* Repair project → House, Vehicles, Computers
* Journal entry → Personal, Health, Travel

Do not add a single `area_id` column to `lp_content_kind`.

Use a many-to-many mapping table.

## 3.3 Pattern describes a common use of a kind

Examples:

* Food Shopping is a pattern of Shopping List.
* Hardware Shopping is a pattern of Shopping List.
* Fix Door is a pattern of Small Repair Project.
* Replace Ensuite is a pattern of Renovation Project.
* Personal Daily Journal is a pattern of Journal Entry.
* Code Review is a pattern of Technical Note.

## 3.4 Template describes what can be created

Templates may eventually create:

* A note body.
* A project.
* A task set.
* A list.
* An event.
* A combination of linked records.

This phase stores and edits template definitions only.

It does not need to execute them.

## 3.5 View describes how content is displayed

Examples:

* Journal timeline.
* Birthday calendar.
* Active shopping lists.
* Project dashboard.
* Gallery.
* Map.
* Recent notes.
* Maintenance history.

This phase stores and edits view definitions only.

It does not need to dynamically execute arbitrary view configuration.

## 3.6 Codes are permanent identifiers

Fields such as `kind_code`, `pattern_code`, `template_code`, and `view_code` must be stable machine-readable identifiers.

Examples:

```text
JOURNAL_ENTRY
SHOPPING_LIST
FOOD_SHOPPING
BIRTHDAY_CALENDAR
SMALL_HOME_REPAIR
```

Changing a display name must not require changing the stable code.

Codes should:

* Be uppercase.
* Use underscores.
* Contain only `A-Z`, `0-9`, and `_`.
* Be unique within their table.

---

# 4. Database

LifePIM uses its existing SQLite database.

Create the following tables:

```text
lp_content_kind
lp_content_kind_area
lp_content_pattern
lp_template
lp_content_kind_template
lp_content_view
lp_content_kind_view
```

Follow the repository’s existing conventions for:

* Primary keys.
* Boolean values.
* Created and updated timestamps.
* Foreign keys.
* Audit columns.
* Soft deletion or active flags.
* Migration files.
* Database helper functions.

Do not create a separate database.

---

# 5. Table: `lp_content_kind`

## Purpose

Stores the durable catalogue of content types understood by LifePIM.

## Proposed columns

```sql
CREATE TABLE lp_content_kind (
    content_kind_id         INTEGER PRIMARY KEY,
    kind_code               TEXT NOT NULL UNIQUE,
    parent_content_kind_id  INTEGER NULL,

    name                    TEXT NOT NULL,
    plural_name             TEXT NULL,
    description             TEXT NULL,

    object_type_code        TEXT NOT NULL,
    canonical_tab_code      TEXT NULL,
    canonical_table_name    TEXT NULL,
    subtype_code            TEXT NULL,

    date_behaviour_code     TEXT NOT NULL DEFAULT 'NONE',
    mapping_status_code     TEXT NOT NULL DEFAULT 'UNDECIDED',

    is_active               INTEGER NOT NULL DEFAULT 1,
    sort_order              INTEGER NOT NULL DEFAULT 0,
    notes                   TEXT NULL,

    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    FOREIGN KEY (
        parent_content_kind_id
    ) REFERENCES lp_content_kind(content_kind_id)
);
```

Adapt timestamp defaults and key syntax to the existing LifePIM schema conventions.

## Field definitions

### `kind_code`

Stable machine-readable identifier.

Examples:

```text
NOTE
IDEA
JOURNAL_ENTRY
SHOPPING_LIST
BIRTHDAY
PHYSICAL_ASSET
BLENDER_MODEL
```

### `parent_content_kind_id`

Supports hierarchical content kinds.

Example:

```text
NOTE
├── IDEA
├── JOURNAL_ENTRY
├── MEETING_NOTE
└── DECISION_NOTE
```

Example:

```text
LIST
└── SHOPPING_LIST
```

Avoid making the hierarchy excessively detailed during seeding.

Specific use cases usually belong in `lp_content_pattern`.

### `object_type_code`

The broad LifePIM storage primitive.

Initial permitted values:

```text
NOTE
TASK
PROJECT
LIST
EVENT
HOWTO
PERSON
PLACE
OBJECT
FILE
MEDIA
AUDIO
DATA
MONEY
APP
GOAL
LOG
COLLECTION
```

Do not enforce these through a database CHECK constraint unless LifePIM already has a standard lookup mechanism.

The Admin editor should provide a dropdown using a central configured list.

### `canonical_tab_code`

The normal top-level LifePIM tab.

Initial values may include:

```text
NOTES
GOALS
HOW
FILES
PEOPLE
PLACES
DATA
3D
MONEY
APPS
CALENDAR
MEDIA
AUDIO
```

A content kind may have a null canonical tab if it is currently undecided or external.

### `canonical_table_name`

Documents the table where the actual content is stored.

Examples:

```text
lp_notes
lp_cal_recurring
lp_places
lp_prj
```

This is descriptive configuration only.

Do not dynamically execute SQL against this table name in this phase.

### `subtype_code`

Optional subtype value used by the canonical table.

Examples:

```text
IDEA
JOURNAL
BIRTHDAY
SHOPPING
PHYSICAL
MODEL
```

### `date_behaviour_code`

Initial permitted values:

```text
NONE
CREATED
OCCURRED
DUE
START_END
RECURRING
MEASUREMENT
```

Meanings:

* `NONE`: The content has no primary time behaviour.
* `CREATED`: Usually displayed by creation date.
* `OCCURRED`: Represents something that happened at a particular time.
* `DUE`: Has a due date.
* `START_END`: Has a scheduled start and end.
* `RECURRING`: Repeats according to recurrence rules.
* `MEASUREMENT`: Represents a time-stamped reading or observation.

### `mapping_status_code`

Initial permitted values:

```text
CONFIRMED
NEEDS_TEMPLATE
NEEDS_VIEW
NEEDS_OBJECT
EXTERNAL_SYSTEM
DO_NOT_STORE
UNDECIDED
```

### `is_active`

Inactive kinds remain available for historic references but are hidden from normal selection lists.

---

# 6. Table: `lp_content_kind_area`

## Purpose

Maps content kinds to one or more existing LifePIM Areas.

## Proposed columns

```sql
CREATE TABLE lp_content_kind_area (
    content_kind_area_id  INTEGER PRIMARY KEY,
    content_kind_id       INTEGER NOT NULL,
    area_id               INTEGER NOT NULL,

    is_default            INTEGER NOT NULL DEFAULT 0,
    display_name_override TEXT NULL,
    sort_order            INTEGER NOT NULL DEFAULT 0,
    notes                 TEXT NULL,

    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,

    FOREIGN KEY (
        content_kind_id
    ) REFERENCES lp_content_kind(content_kind_id),

    FOREIGN KEY (
        area_id
    ) REFERENCES lp_project(project_id),

    UNIQUE (
        content_kind_id,
        area_id
    )
);
```

Use the actual existing Area table and key names from the repository.

The old Projects system was renamed to **Areas** in the user interface, but the database may still use tables such as:

```text
lp_project
lp_project_folders
```

Do not create a duplicate Area table.

Inspect the repository and link `lp_content_kind_area.area_id` to the existing Area primary key.

## Behaviour

A content kind may have:

* No Area mappings.
* One Area mapping.
* Many Area mappings.

Only one mapping should normally have `is_default = 1` for a given content kind.

The UI should prevent or automatically correct multiple default Areas.

---

# 7. Table: `lp_content_pattern`

## Purpose

Stores common LifePIM use cases built on a content kind.

## Proposed columns

```sql
CREATE TABLE lp_content_pattern (
    content_pattern_id  INTEGER PRIMARY KEY,
    pattern_code        TEXT NOT NULL UNIQUE,
    content_kind_id     INTEGER NOT NULL,

    name                TEXT NOT NULL,
    description         TEXT NULL,

    default_area_id     INTEGER NULL,
    default_template_id INTEGER NULL,
    default_view_id     INTEGER NULL,

    creation_config     TEXT NULL,
    view_filter_config  TEXT NULL,

    is_active           INTEGER NOT NULL DEFAULT 1,
    sort_order          INTEGER NOT NULL DEFAULT 0,
    notes               TEXT NULL,

    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,

    FOREIGN KEY (
        content_kind_id
    ) REFERENCES lp_content_kind(content_kind_id),

    FOREIGN KEY (
        default_area_id
    ) REFERENCES lp_project(project_id),

    FOREIGN KEY (
        default_template_id
    ) REFERENCES lp_template(template_id),

    FOREIGN KEY (
        default_view_id
    ) REFERENCES lp_content_view(content_view_id)
);
```

There is a circular migration dependency because patterns reference templates and views.

Resolve this safely using one of these approaches:

1. Create the referenced tables first.
2. Create pattern initially without those foreign-key constraints and add repository-level validation.
3. Use SQLite-compatible deferred migration logic.

Use whichever approach best matches the existing migration framework.

## Configuration fields

`creation_config` and `view_filter_config` may contain JSON text.

Examples:

```json
{
  "subtype": "JOURNAL",
  "set_occurred_at": true
}
```

```json
{
  "event_type": "BIRTHDAY",
  "recurrence": "YEARLY"
}
```

```json
{
  "status": ["ACTIVE"],
  "sort": "updated_at DESC"
}
```

Requirements:

* JSON is optional.
* Empty values are valid.
* The editor should validate JSON before saving non-empty values.
* The system must not execute arbitrary SQL stored in these fields.
* JSON is configuration data only in this phase.

---

# 8. Table: `lp_template`

## Purpose

Stores templates that may later be used when creating LifePIM records or groups of linked records.

## Proposed columns

```sql
CREATE TABLE lp_template (
    template_id          INTEGER PRIMARY KEY,
    template_code        TEXT NOT NULL UNIQUE,

    name                 TEXT NOT NULL,
    description          TEXT NULL,

    template_type_code   TEXT NOT NULL,
    target_object_type   TEXT NULL,
    target_tab_code      TEXT NULL,

    template_content     TEXT NULL,
    template_config      TEXT NULL,

    is_active            INTEGER NOT NULL DEFAULT 1,
    sort_order           INTEGER NOT NULL DEFAULT 0,
    notes                TEXT NULL,

    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);
```

## `template_type_code`

Initial suggested values:

```text
NOTE
PROJECT
LIST
EVENT
HOWTO
OBJECT
MULTI_OBJECT
```

`MULTI_OBJECT` is reserved for future templates that may create a project plus tasks, lists, notes, and events.

## `template_content`

Stores the main human-editable body.

Examples:

* Markdown note template.
* Project description.
* Checklist text.
* How-to structure.

## `template_config`

Optional JSON containing future structured behaviour.

Example:

```json
{
  "create_tasks": [
    "Describe the fault",
    "Take photos",
    "Identify parts",
    "Complete repair",
    "Record final cost"
  ]
}
```

This phase stores the JSON but does not execute it.

---

# 9. Table: `lp_content_kind_template`

## Purpose

Many-to-many relationship between content kinds and templates.

## Proposed columns

```sql
CREATE TABLE lp_content_kind_template (
    content_kind_template_id INTEGER PRIMARY KEY,
    content_kind_id          INTEGER NOT NULL,
    template_id              INTEGER NOT NULL,

    is_default               INTEGER NOT NULL DEFAULT 0,
    sort_order               INTEGER NOT NULL DEFAULT 0,
    notes                    TEXT NULL,

    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL,

    FOREIGN KEY (
        content_kind_id
    ) REFERENCES lp_content_kind(content_kind_id),

    FOREIGN KEY (
        template_id
    ) REFERENCES lp_template(template_id),

    UNIQUE (
        content_kind_id,
        template_id
    )
);
```

A content kind may have multiple templates.

Example:

```text
REPAIR_PROJECT
├── Small Home Repair
├── Car Repair
└── Appliance Repair
```

Only one template should normally be marked as the default for each content kind.

---

# 10. Table: `lp_content_view`

## Purpose

Stores named view definitions associated with LifePIM content.

## Proposed columns

```sql
CREATE TABLE lp_content_view (
    content_view_id      INTEGER PRIMARY KEY,
    view_code            TEXT NOT NULL UNIQUE,

    name                 TEXT NOT NULL,
    description          TEXT NULL,

    tab_code             TEXT NULL,
    view_type_code       TEXT NOT NULL,
    view_config          TEXT NULL,

    is_active            INTEGER NOT NULL DEFAULT 1,
    sort_order           INTEGER NOT NULL DEFAULT 0,
    notes                TEXT NULL,

    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);
```

## `view_type_code`

Initial suggested values:

```text
TABLE
LIST
TIMELINE
CALENDAR
BOARD
GALLERY
MAP
TREE
DASHBOARD
DETAIL
```

## `view_config`

Optional JSON configuration.

Examples:

```json
{
  "sort": "occurred_at DESC",
  "group_by": "month"
}
```

```json
{
  "filter": {
    "event_type": "BIRTHDAY"
  },
  "calendar_mode": "YEAR"
}
```

```json
{
  "filter": {
    "status": "ACTIVE"
  },
  "group_by": "area"
}
```

This phase only stores and validates the configuration.

Do not implement a general-purpose query engine.

---

# 11. Table: `lp_content_kind_view`

## Purpose

Many-to-many relationship between content kinds and views.

## Proposed columns

```sql
CREATE TABLE lp_content_kind_view (
    content_kind_view_id INTEGER PRIMARY KEY,
    content_kind_id      INTEGER NOT NULL,
    content_view_id      INTEGER NOT NULL,

    is_default           INTEGER NOT NULL DEFAULT 0,
    sort_order           INTEGER NOT NULL DEFAULT 0,
    notes                TEXT NULL,

    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,

    FOREIGN KEY (
        content_kind_id
    ) REFERENCES lp_content_kind(content_kind_id),

    FOREIGN KEY (
        content_view_id
    ) REFERENCES lp_content_view(content_view_id),

    UNIQUE (
        content_kind_id,
        content_view_id
    )
);
```

Only one view should normally be marked as the default for each content kind.

---

# 12. Reusable Fast Table Editor

## Requirement

The Content Catalog will contain hundreds of rows and will be actively edited while LifePIM is being designed.

Editing must feel closer to editing a spreadsheet than completing a series of web forms.

Create or extend a reusable table editor component that can later be used by other LifePIM Admin functions and metadata tables.

Do not create a Content-Catalog-specific editor that cannot be reused.

## Suggested component name

Use naming appropriate to the existing application, such as:

```text
AdminTableEditor
EditableDataGrid
MetadataTableEditor
```

## Required capabilities

### Fast inline editing

* Click a cell to edit it.
* Enter saves the current cell or row.
* Tab moves to the next editable field.
* Shift+Tab moves to the previous field.
* Escape cancels the current edit.
* Arrow-key navigation should work where practical.
* A new blank row should be available without opening a modal.
* After inserting a row, keep focus in the grid so the user can immediately enter the next one.

### Efficient row creation

Provide a clearly visible:

```text
+ Add Row
```

The new row should appear inline.

For Content Kinds, the minimum required fields for a new row are:

```text
Name
Kind Code
Object Type
```

Where practical, generate an initial `kind_code` from the entered name:

```text
Personal Journal
→ PERSONAL_JOURNAL
```

The generated code remains editable before save.

### Dropdown fields

Use dropdowns for controlled values such as:

* Parent content kind.
* Object type.
* Canonical tab.
* Date behaviour.
* Mapping status.
* Template type.
* View type.
* Active status.

### Area editing

Display Areas as a compact multi-select or tag editor.

Example:

```text
[House] [Vehicles] [Design]
```

Adding or removing an Area must update `lp_content_kind_area`.

Do not store comma-separated Area names in `lp_content_kind`.

### Validation

Show validation errors adjacent to the edited row or cell.

Do not discard the user’s unsaved input when validation fails.

Validate:

* Required fields.
* Unique codes.
* Code format.
* Parent cannot be self.
* Invalid JSON.
* Duplicate mappings.
* Multiple defaults where only one default is expected.

### Saving behaviour

Preferred behaviour:

* Save on Enter.
* Save on leaving a changed row.
* Show a brief saved indicator.
* Avoid full-page refreshes.
* Preserve the current filter and scroll position after save.

If the existing application architecture makes row-level explicit Save buttons more reliable, they may be used, but editing must remain quick.

### Filtering and search

Provide:

* Free-text search.
* Active/inactive filter.
* Object type filter.
* Canonical tab filter.
* Area filter.
* Mapping status filter.
* Parent kind filter.

Search should cover at least:

* Name.
* Code.
* Description.
* Notes.
* Canonical table name.

### Sorting

Allow sorting by:

* Name.
* Code.
* Parent.
* Object type.
* Tab.
* Status.
* Sort order.
* Updated date.

### Large table behaviour

The editor should remain usable with at least 1,000 rows.

Use pagination, incremental loading, or lightweight rendering if required.

Do not load an excessively large DOM containing complex controls for every row when controls could be created only during editing.

### Reusability

The reusable editor should accept configuration describing:

* Table or API endpoint.
* Column definitions.
* Field types.
* Required fields.
* Dropdown sources.
* Validation rules.
* Read-only fields.
* Default values.
* Search fields.
* Sort options.
* Row-level create, update, and deactivate operations.

Avoid embedding Content Catalog field names throughout the generic component.

---

# 13. Content Catalog Page

## 13.1 Summary section

At the top of the Content Kinds page, show summary counts.

Examples:

```text
Total Kinds
Confirmed
Need Templates
Need Views
Need Objects
Undecided
Inactive
```

Also show counts by canonical top-level tab:

```text
Notes
Goals
How
Files
People
Places
Data
3D
Money
Apps
Calendar
Media
Audio
```

Clicking a summary count should apply the corresponding filter to the table.

## 13.2 Main Content Kinds grid

Suggested visible columns:

```text
Name
Code
Parent
Object Type
Tab
Canonical Table
Subtype
Date Behaviour
Areas
Mapping Status
Active
Notes
```

Less frequently edited fields may be placed in a row-detail drawer if the table becomes too wide.

## 13.3 Patterns grid

Suggested columns:

```text
Name
Code
Content Kind
Default Area
Default Template
Default View
Active
Notes
```

Provide an expandable or drawer editor for:

```text
Description
Creation Config
View Filter Config
```

## 13.4 Templates grid

Suggested columns:

```text
Name
Code
Template Type
Target Object Type
Target Tab
Active
Notes
```

Provide a detail editor for:

```text
Description
Template Content
Template Config
Associated Content Kinds
```

A larger textarea or Markdown editor is appropriate for `template_content`.

## 13.5 Views grid

Suggested columns:

```text
Name
Code
Tab
View Type
Active
Notes
```

Provide a detail editor for:

```text
Description
View Config
Associated Content Kinds
```

---

# 14. Data Access and Service Layer

Do not place raw SQL directly throughout the route or UI code.

Create repository/service functions consistent with the existing application structure.

Suggested responsibilities:

```text
get_content_kinds(filters, sort, paging)
get_content_kind(content_kind_id)
create_content_kind(data)
update_content_kind(content_kind_id, data)
set_content_kind_areas(content_kind_id, area_ids)
deactivate_content_kind(content_kind_id)

get_content_patterns(...)
create_content_pattern(...)
update_content_pattern(...)

get_templates(...)
create_template(...)
update_template(...)
set_content_kind_templates(...)

get_content_views(...)
create_content_view(...)
update_content_view(...)
set_content_kind_views(...)
```

When saving a content kind and its Areas, use a transaction.

When changing a default template, default view, or default Area, ensure any previous default for that content kind is cleared within the same transaction.

---

# 15. Delete Behaviour

Do not hard-delete referenced records through the normal Admin UI.

Normal removal should set:

```text
is_active = 0
```

Hard deletion may be available only when:

* The row has no dependent mappings.
* It is explicitly confirmed.
* This follows existing LifePIM Admin conventions.

For the initial implementation, deactivation is sufficient.

---

# 16. Seed Data

Create an idempotent seed migration or seed function.

Requirements:

* Insert sample rows only when the corresponding stable code does not already exist.
* Do not overwrite user-edited descriptions or notes on later application starts.
* Resolve Area mappings by existing Area names or stable Area identifiers.
* If a sample Area does not exist, skip that mapping rather than creating duplicate or unwanted Areas automatically.
* Log skipped Area mappings.

The seed data is intended as an example and starting point, not a complete ontology.

---

# 17. Sample Content Kinds

Seed the following content kinds.

The precise canonical table names should be adjusted after inspecting the actual repository.

Use null where the implementation is not yet known.

## Root and shared kinds

| Code       | Name             | Parent | Object Type | Tab      | Date Behaviour | Status       |
| ---------- | ---------------- | ------ | ----------- | -------- | -------------- | ------------ |
| NOTE       | Note             |        | NOTE        | NOTES    | CREATED        | CONFIRMED    |
| TASK       | Task             |        | TASK        | GOALS    | DUE            | CONFIRMED    |
| PROJECT    | Project          |        | PROJECT     | GOALS    | START_END      | CONFIRMED    |
| LIST       | List             |        | LIST        | GOALS    | CREATED        | CONFIRMED    |
| EVENT      | Event            |        | EVENT       | CALENDAR | START_END      | CONFIRMED    |
| HOWTO      | How-to           |        | HOWTO       | HOW      | CREATED        | CONFIRMED    |
| PERSON     | Person           |        | PERSON      | PEOPLE   | CREATED        | CONFIRMED    |
| PLACE      | Place            |        | PLACE       | PLACES   | CREATED        | CONFIRMED    |
| OBJECT     | Object           |        | OBJECT      | 3D       | CREATED        | NEEDS_OBJECT |
| FILE       | File             |        | FILE        | FILES    | CREATED        | CONFIRMED    |
| DATA_ITEM  | Data Item        |        | DATA        | DATA     | CREATED        | CONFIRMED    |
| MONEY_ITEM | Money Item       |        | MONEY       | MONEY    | CREATED        | UNDECIDED    |
| APP_ITEM   | Application Item |        | APP         | APPS     | CREATED        | CONFIRMED    |
| MEDIA_ITEM | Media Item       |        | MEDIA       | MEDIA    | CREATED        | CONFIRMED    |
| AUDIO_ITEM | Audio Item       |        | AUDIO       | AUDIO    | CREATED        | CONFIRMED    |
| LOG_ENTRY  | Log Entry        |        | LOG         | DATA     | MEASUREMENT    | NEEDS_OBJECT |
| COLLECTION | Collection       |        | COLLECTION  |          | CREATED        | CONFIRMED    |

## Notes tab

| Code             | Name                  | Parent | Subtype          | Date Behaviour | Status         |
| ---------------- | --------------------- | ------ | ---------------- | -------------- | -------------- |
| IDEA             | Idea                  | NOTE   | IDEA             | CREATED        | CONFIRMED      |
| JOURNAL_ENTRY    | Journal Entry         | NOTE   | JOURNAL          | OCCURRED       | NEEDS_VIEW     |
| MEETING_NOTE     | Meeting Note          | NOTE   | MEETING          | OCCURRED       | NEEDS_TEMPLATE |
| DECISION_NOTE    | Decision              | NOTE   | DECISION         | OCCURRED       | NEEDS_TEMPLATE |
| RESEARCH_NOTE    | Research Note         | NOTE   | RESEARCH         | CREATED        | NEEDS_TEMPLATE |
| CODE_REVIEW_NOTE | Code Review           | NOTE   | CODE_REVIEW      | OCCURRED       | NEEDS_TEMPLATE |
| BOOK_NOTE        | Book Note             | NOTE   | BOOK             | CREATED        | NEEDS_TEMPLATE |
| PERSON_NOTE      | Person Note           | NOTE   | PERSON           | OCCURRED       | CONFIRMED      |
| ANNUAL_REVIEW    | Annual Review         | NOTE   | REVIEW           | OCCURRED       | NEEDS_TEMPLATE |
| TECHNICAL_DESIGN | Technical Design Note | NOTE   | TECHNICAL_DESIGN | CREATED        | NEEDS_TEMPLATE |

## Goals, projects, tasks and lists

| Code               | Name                   | Parent  | Object Type | Subtype     | Status         |
| ------------------ | ---------------------- | ------- | ----------- | ----------- | -------------- |
| REPAIR_PROJECT     | Repair Project         | PROJECT | PROJECT     | REPAIR      | NEEDS_TEMPLATE |
| RENOVATION_PROJECT | Renovation Project     | PROJECT | PROJECT     | RENOVATION  | NEEDS_TEMPLATE |
| SOFTWARE_PROJECT   | Software Project       | PROJECT | PROJECT     | SOFTWARE    | NEEDS_TEMPLATE |
| TRAVEL_PROJECT     | Travel Project         | PROJECT | PROJECT     | TRAVEL      | NEEDS_TEMPLATE |
| PURCHASE_PROJECT   | Major Purchase Project | PROJECT | PROJECT     | PURCHASE    | NEEDS_TEMPLATE |
| ADMIN_PROJECT      | Administration Project | PROJECT | PROJECT     | ADMIN       | NEEDS_TEMPLATE |
| ERRAND_TASK        | Errand                 | TASK    | TASK        | ERRAND      | CONFIRMED      |
| FOLLOW_UP_TASK     | Follow-up              | TASK    | TASK        | FOLLOW_UP   | CONFIRMED      |
| MAINTENANCE_TASK   | Maintenance Task       | TASK    | TASK        | MAINTENANCE | CONFIRMED      |
| SHOPPING_LIST      | Shopping List          | LIST    | LIST        | SHOPPING    | CONFIRMED      |
| PACKING_LIST       | Packing List           | LIST    | LIST        | PACKING     | NEEDS_TEMPLATE |
| CHECKLIST          | Checklist              | LIST    | LIST        | CHECKLIST   | CONFIRMED      |
| WATCHLIST          | Watchlist              | LIST    | LIST        | WATCHLIST   | CONFIRMED      |
| QUESTIONS_LIST     | Questions List         | LIST    | LIST        | QUESTIONS   | CONFIRMED      |

## Calendar tab

| Code                | Name                | Parent | Subtype     | Date Behaviour | Status     |
| ------------------- | ------------------- | ------ | ----------- | -------------- | ---------- |
| APPOINTMENT         | Appointment         | EVENT  | APPOINTMENT | START_END      | CONFIRMED  |
| MEETING             | Meeting             | EVENT  | MEETING     | START_END      | CONFIRMED  |
| BIRTHDAY            | Birthday            | EVENT  | BIRTHDAY    | RECURRING      | NEEDS_VIEW |
| ANNIVERSARY         | Anniversary         | EVENT  | ANNIVERSARY | RECURRING      | NEEDS_VIEW |
| PUBLIC_HOLIDAY      | Public Holiday      | EVENT  | HOLIDAY     | RECURRING      | CONFIRMED  |
| DEADLINE            | Deadline            | EVENT  | DEADLINE    | DUE            | CONFIRMED  |
| PAYDAY              | Payday              | EVENT  | PAYDAY      | RECURRING      | CONFIRMED  |
| BILL_DUE_DATE       | Bill Due Date       | EVENT  | BILL_DUE    | RECURRING      | CONFIRMED  |
| WARRANTY_EXPIRY     | Warranty Expiry     | EVENT  | WARRANTY    | DUE            | NEEDS_VIEW |
| MEDICAL_APPOINTMENT | Medical Appointment | EVENT  | MEDICAL     | START_END      | CONFIRMED  |
| TRAVEL_BOOKING      | Travel Booking      | EVENT  | TRAVEL      | START_END      | CONFIRMED  |

## How tab

| Code                 | Name                 | Parent | Subtype    | Status    |
| -------------------- | -------------------- | ------ | ---------- | --------- |
| RECIPE               | Recipe               | HOWTO  | RECIPE     | CONFIRMED |
| REPAIR_GUIDE         | Repair Guide         | HOWTO  | REPAIR     | CONFIRMED |
| SOFTWARE_RUNBOOK     | Software Runbook     | HOWTO  | SOFTWARE   | CONFIRMED |
| BACKUP_PROCEDURE     | Backup Procedure     | HOWTO  | BACKUP     | CONFIRMED |
| RESTORE_PROCEDURE    | Restore Procedure    | HOWTO  | RESTORE    | CONFIRMED |
| DEPLOYMENT_PROCEDURE | Deployment Procedure | HOWTO  | DEPLOYMENT | CONFIRMED |
| EMERGENCY_PROCEDURE  | Emergency Procedure  | HOWTO  | EMERGENCY  | CONFIRMED |
| CLEANING_PROCEDURE   | Cleaning Procedure   | HOWTO  | CLEANING   | CONFIRMED |

## People tab

| Code                 | Name                 | Parent | Subtype      | Status    |
| -------------------- | -------------------- | ------ | ------------ | --------- |
| FAMILY_MEMBER        | Family Member        | PERSON | FAMILY       | CONFIRMED |
| FRIEND               | Friend               | PERSON | FRIEND       | CONFIRMED |
| PROFESSIONAL_CONTACT | Professional Contact | PERSON | PROFESSIONAL | CONFIRMED |
| MEDICAL_CONTACT      | Medical Contact      | PERSON | MEDICAL      | CONFIRMED |
| TRADESPERSON         | Tradesperson         | PERSON | TRADESPERSON | CONFIRMED |
| ORGANISATION         | Organisation         | PERSON | ORGANISATION | CONFIRMED |
| EMERGENCY_CONTACT    | Emergency Contact    | PERSON | EMERGENCY    | CONFIRMED |

## Places tab

| Code               | Name               | Parent | Subtype    | Status     |
| ------------------ | ------------------ | ------ | ---------- | ---------- |
| EARTH_PLACE        | Earth Place        | PLACE  | EARTH      | CONFIRMED  |
| FICTIONAL_PLACE    | Fictional Place    | PLACE  | FICTIONAL  | CONFIRMED  |
| GAME_WORLD_PLACE   | Game World Place   | PLACE  | GAME_WORLD | CONFIRMED  |
| HOME_LOCATION      | Home Location      | PLACE  | HOME       | CONFIRMED  |
| BUSINESS_LOCATION  | Business Location  | PLACE  | BUSINESS   | CONFIRMED  |
| TRAVEL_DESTINATION | Travel Destination | PLACE  | TRAVEL     | CONFIRMED  |
| ROUTE              | Route              | PLACE  | ROUTE      | NEEDS_VIEW |

## 3D and Objects tab

| Code             | Name                 | Parent         | Subtype       | Status       |
| ---------------- | -------------------- | -------------- | ------------- | ------------ |
| PHYSICAL_ASSET   | Physical Asset       | OBJECT         | PHYSICAL      | NEEDS_OBJECT |
| FURNITURE        | Furniture            | PHYSICAL_ASSET | FURNITURE     | NEEDS_OBJECT |
| APPLIANCE        | Appliance            | PHYSICAL_ASSET | APPLIANCE     | NEEDS_OBJECT |
| VEHICLE          | Vehicle              | PHYSICAL_ASSET | VEHICLE       | NEEDS_OBJECT |
| DEVICE           | Device               | PHYSICAL_ASSET | DEVICE        | NEEDS_OBJECT |
| TOOL             | Tool                 | PHYSICAL_ASSET | TOOL          | NEEDS_OBJECT |
| BLENDER_MODEL    | Blender Model        | OBJECT         | BLENDER_MODEL | CONFIRMED    |
| UE_OBJECT        | Unreal Engine Object | OBJECT         | UE_OBJECT     | CONFIRMED    |
| THREE_D_SCENE    | 3D Scene             | OBJECT         | SCENE         | CONFIRMED    |
| GAME_OBJECT      | Game Object          | OBJECT         | GAME_OBJECT   | CONFIRMED    |
| FICTIONAL_OBJECT | Fictional Object     | OBJECT         | FICTIONAL     | CONFIRMED    |
| OBJECT_COMPONENT | Object Component     | OBJECT         | COMPONENT     | NEEDS_OBJECT |
| DESIGN_CONCEPT   | Design Concept       | OBJECT         | CONCEPT       | CONFIRMED    |
| THREE_D_SCAN     | 3D Scan              | OBJECT         | SCAN          | CONFIRMED    |

## Files tab

| Code             | Name              | Parent | Subtype     | Status    |
| ---------------- | ----------------- | ------ | ----------- | --------- |
| DOCUMENT_FILE    | Document          | FILE   | DOCUMENT    | CONFIRMED |
| RECEIPT_FILE     | Receipt           | FILE   | RECEIPT     | CONFIRMED |
| MANUAL_FILE      | Manual            | FILE   | MANUAL      | CONFIRMED |
| WARRANTY_FILE    | Warranty Document | FILE   | WARRANTY    | CONFIRMED |
| CONTRACT_FILE    | Contract          | FILE   | CONTRACT    | CONFIRMED |
| CERTIFICATE_FILE | Certificate       | FILE   | CERTIFICATE | CONFIRMED |
| SOURCE_CODE_FILE | Source Code File  | FILE   | SOURCE_CODE | CONFIRMED |
| ARCHIVE_FILE     | Archive File      | FILE   | ARCHIVE     | CONFIRMED |

## Data tab

| Code              | Name              | Parent    | Subtype     | Date Behaviour | Status       |
| ----------------- | ----------------- | --------- | ----------- | -------------- | ------------ |
| DATASET           | Dataset           | DATA_ITEM | DATASET     | CREATED        | CONFIRMED    |
| DATABASE          | Database          | DATA_ITEM | DATABASE    | CREATED        | CONFIRMED    |
| TABLE_DEFINITION  | Table Definition  | DATA_ITEM | TABLE       | CREATED        | CONFIRMED    |
| SAVED_QUERY       | Saved Query       | DATA_ITEM | QUERY       | CREATED        | CONFIRMED    |
| MEASUREMENT_LOG   | Measurement Log   | LOG_ENTRY | MEASUREMENT | MEASUREMENT    | NEEDS_OBJECT |
| ACTIVITY_LOG      | Activity Log      | LOG_ENTRY | ACTIVITY    | OCCURRED       | NEEDS_OBJECT |
| IMPORT_DEFINITION | Import Definition | DATA_ITEM | IMPORT      | CREATED        | CONFIRMED    |

## Money tab

| Code               | Name               | Parent     | Subtype      | Date Behaviour | Status       |
| ------------------ | ------------------ | ---------- | ------------ | -------------- | ------------ |
| ACCOUNT            | Financial Account  | MONEY_ITEM | ACCOUNT      | CREATED        | NEEDS_OBJECT |
| BUDGET             | Budget             | MONEY_ITEM | BUDGET       | START_END      | NEEDS_OBJECT |
| TRANSACTION        | Transaction        | MONEY_ITEM | TRANSACTION  | OCCURRED       | NEEDS_OBJECT |
| BILL               | Bill               | MONEY_ITEM | BILL         | DUE            | NEEDS_OBJECT |
| SUBSCRIPTION       | Subscription       | MONEY_ITEM | SUBSCRIPTION | RECURRING      | NEEDS_OBJECT |
| INSURANCE_POLICY   | Insurance Policy   | MONEY_ITEM | INSURANCE    | START_END      | NEEDS_OBJECT |
| FINANCIAL_FORECAST | Financial Forecast | MONEY_ITEM | FORECAST     | START_END      | NEEDS_VIEW   |

## Apps tab

| Code                | Name                | Parent   | Subtype | Status    |
| ------------------- | ------------------- | -------- | ------- | --------- |
| DESKTOP_APPLICATION | Desktop Application | APP_ITEM | DESKTOP | CONFIRMED |
| MOBILE_APPLICATION  | Mobile Application  | APP_ITEM | MOBILE  | CONFIRMED |
| WEB_APPLICATION     | Web Application     | APP_ITEM | WEB     | CONFIRMED |
| COMMAND_LINE_TOOL   | Command-line Tool   | APP_ITEM | CLI     | CONFIRMED |
| ONLINE_SERVICE      | Online Service      | APP_ITEM | SERVICE | CONFIRMED |
| SOFTWARE_LICENSE    | Software Licence    | APP_ITEM | LICENCE | CONFIRMED |

## Media tab

| Code        | Name        | Parent     | Subtype    | Status    |           |
| ----------- | ----------- | ---------- | ---------- | --------- | --------- |
| PHOTO       | Photo       | MEDIA_ITEM | PHOTO      | CONFIRMED |           |
| VIDEO       | Video       | MEDIA_ITEM | VIDEO      | CONFIRMED |           |
| SCREENSHOT  | Screenshot  | MEDIA_ITEM | SCREENSHOT | CONFIRMED |           |
| ALBUM       | Album       | COLLECTION | ALBUM      | CONFIRMED |           |
| MEDIA_EVENT | Media Event | MEDIA_ITEM | EVENT      | OCCURRED  | CONFIRMED |

## Audio tab

| Code            | Name            | Parent     | Subtype   | Status    |
| --------------- | --------------- | ---------- | --------- | --------- |
| MUSIC_TRACK     | Music Track     | AUDIO_ITEM | MUSIC     | CONFIRMED |
| PODCAST_EPISODE | Podcast Episode | AUDIO_ITEM | PODCAST   | CONFIRMED |
| AUDIO_RECORDING | Audio Recording | AUDIO_ITEM | RECORDING | CONFIRMED |
| PLAYLIST        | Playlist        | COLLECTION | PLAYLIST  | CONFIRMED |

---

# 18. Suggested Area Mappings

Map sample content kinds to existing Areas where matching Areas exist.

Area names must be resolved case-insensitively where practical.

Do not automatically create missing Areas.

## Personal

```text
IDEA
JOURNAL_ENTRY
ANNUAL_REVIEW
APPOINTMENT
CHECKLIST
DOCUMENT_FILE
```

## Family

```text
FAMILY_MEMBER
BIRTHDAY
ANNIVERSARY
EMERGENCY_CONTACT
PHOTO
TRAVEL_PROJECT
```

## Friends

```text
FRIEND
BIRTHDAY
MEETING
GIFT_IDEA
```

Skip `GIFT_IDEA` if that content kind is not seeded.

## House

```text
REPAIR_PROJECT
RENOVATION_PROJECT
SHOPPING_LIST
MAINTENANCE_TASK
FURNITURE
APPLIANCE
TOOL
REPAIR_GUIDE
WARRANTY_FILE
WARRANTY_EXPIRY
```

## Food

```text
SHOPPING_LIST
RECIPE
CHECKLIST
APPLIANCE
```

## Health

```text
MEDICAL_APPOINTMENT
MEDICAL_CONTACT
MEASUREMENT_LOG
JOURNAL_ENTRY
QUESTIONS_LIST
DOCUMENT_FILE
```

## Vehicles

```text
VEHICLE
REPAIR_PROJECT
MAINTENANCE_TASK
RECEIPT_FILE
WARRANTY_FILE
APPOINTMENT
```

## Travel

```text
TRAVEL_PROJECT
TRAVEL_DESTINATION
TRAVEL_BOOKING
PACKING_LIST
PHOTO
JOURNAL_ENTRY
ROUTE
```

## Work

```text
MEETING_NOTE
MEETING
TASK
PROJECT
TECHNICAL_DESIGN
PROFESSIONAL_CONTACT
DATASET
SAVED_QUERY
```

## LifePIM

```text
SOFTWARE_PROJECT
CODE_REVIEW_NOTE
TECHNICAL_DESIGN
SOFTWARE_RUNBOOK
DEPLOYMENT_PROCEDURE
SOURCE_CODE_FILE
DATABASE
TABLE_DEFINITION
MOBILE_APPLICATION
DESKTOP_APPLICATION
```

## Computers

```text
DEVICE
SOFTWARE_PROJECT
BACKUP_PROCEDURE
RESTORE_PROCEDURE
SOFTWARE_RUNBOOK
DESKTOP_APPLICATION
COMMAND_LINE_TOOL
SOFTWARE_LICENSE
```

## Design

```text
BLENDER_MODEL
THREE_D_SCENE
DESIGN_CONCEPT
UE_OBJECT
THREE_D_SCAN
PHOTO
SOURCE_CODE_FILE
```

## Alrona

```text
FICTIONAL_PLACE
FICTIONAL_OBJECT
GAME_OBJECT
THREE_D_SCENE
DESIGN_CONCEPT
```

## Warcraft

```text
GAME_WORLD_PLACE
GAME_OBJECT
FICTIONAL_OBJECT
SCREENSHOT
ROUTE
```

## Finance

```text
ACCOUNT
BUDGET
TRANSACTION
BILL
SUBSCRIPTION
INSURANCE_POLICY
FINANCIAL_FORECAST
DOCUMENT_FILE
```

## Garden

```text
REPAIR_PROJECT
MAINTENANCE_TASK
HOWTO
PHOTO
MEASUREMENT_LOG
SHOPPING_LIST
```

Skip direct mapping of root `HOWTO` if root kinds are intended only as hierarchy nodes.

---

# 19. Sample Templates

Seed these templates.

## Blank Note

```text
template_code: BLANK_NOTE
name: Blank Note
template_type_code: NOTE
target_object_type: NOTE
target_tab_code: NOTES
template_content:
```

```markdown
# {{title}}

```

## Idea Note

```text
template_code: IDEA_NOTE
name: Idea
template_type_code: NOTE
target_object_type: NOTE
target_tab_code: NOTES
```

```markdown
# {{title}}

## Idea

## Why it may be useful

## Next step

```

## Journal Entry

```text
template_code: JOURNAL_ENTRY
name: Journal Entry
template_type_code: NOTE
target_object_type: NOTE
target_tab_code: NOTES
```

```markdown
# {{date}}

## What happened

## Thoughts

## Worth remembering

```

## Meeting Note

```text
template_code: MEETING_NOTE
name: Meeting Note
template_type_code: NOTE
target_object_type: NOTE
target_tab_code: NOTES
```

```markdown
# {{title}}

**Date:** {{date}}

## Attendees

## Discussion

## Decisions

## Actions

```

## Decision Note

```text
template_code: DECISION_NOTE
name: Decision
template_type_code: NOTE
target_object_type: NOTE
target_tab_code: NOTES
```

```markdown
# {{title}}

## Decision

## Context

## Options considered

## Reason

## Consequences

## Review date

```

## Code Review

```text
template_code: CODE_REVIEW_NOTE
name: Code Review
template_type_code: NOTE
target_object_type: NOTE
target_tab_code: NOTES
```

```markdown
# Code Review — {{title}}

## Purpose

## Files or components reviewed

## Findings

## Bugs or risks

## Suggested changes

## Verification

```

## Small Home Repair

```text
template_code: SMALL_HOME_REPAIR
name: Small Home Repair
template_type_code: PROJECT
target_object_type: PROJECT
target_tab_code: GOALS
```

```markdown
# {{title}}

## Problem

## Desired result

## Photos and measurements

## Tools and parts

## Tasks

- [ ] Inspect the problem
- [ ] Decide whether it is DIY or requires a tradesperson
- [ ] Obtain tools or parts
- [ ] Complete the repair
- [ ] Test the result
- [ ] Record cost and final notes

```

## Car Repair

```text
template_code: CAR_REPAIR
name: Car Repair
template_type_code: PROJECT
target_object_type: PROJECT
target_tab_code: GOALS
```

```markdown
# {{title}}

## Vehicle

## Problem or symptom

## Diagnosis

## Quotes

## Parts

## Tasks

- [ ] Record symptoms
- [ ] Take photos if useful
- [ ] Obtain diagnosis
- [ ] Approve or perform repair
- [ ] Record cost
- [ ] Record work completed
- [ ] Add future maintenance date

```

## Replace Ensuite

```text
template_code: REPLACE_ENSUITE
name: Replace Ensuite
template_type_code: MULTI_OBJECT
target_object_type: PROJECT
target_tab_code: GOALS
```

```markdown
# Replace Ensuite

## Requirements

## Measurements

## Budget

## Design decisions

## Quotes and contractors

## Fixtures and materials

## Work stages

- [ ] Finalise requirements
- [ ] Measure existing room
- [ ] Prepare budget
- [ ] Obtain quotes
- [ ] Select contractor
- [ ] Select fixtures
- [ ] Demolition
- [ ] Plumbing
- [ ] Electrical
- [ ] Waterproofing
- [ ] Tiling
- [ ] Installation
- [ ] Inspection
- [ ] Record warranties and receipts
- [ ] Take final photos

```

## Software Change

```text
template_code: SOFTWARE_CHANGE
name: Software Change
template_type_code: PROJECT
target_object_type: PROJECT
target_tab_code: GOALS
```

```markdown
# {{title}}

## Problem or goal

## Current behaviour

## Desired behaviour

## Acceptance criteria

## Design notes

## Implementation tasks

## Test plan

## Documentation

## Release and verification

```

## Trip

```text
template_code: TRIP_PROJECT
name: Trip
template_type_code: MULTI_OBJECT
target_object_type: PROJECT
target_tab_code: GOALS
```

```markdown
# {{destination}} — {{dates}}

## Purpose

## Dates

## Budget

## Bookings

## Itinerary

## Packing

## Home preparation

## Documents

## Places to visit

## Journal and photos

## Lessons for next time

```

## Food Shopping

```text
template_code: FOOD_SHOPPING_LIST
name: Food Shopping
template_type_code: LIST
target_object_type: LIST
target_tab_code: GOALS
```

```markdown
## Fruit and vegetables

## Bread and bakery

## Fridge

## Freezer

## Pantry

## Household

```

## Recipe

```text
template_code: RECIPE
name: Recipe
template_type_code: HOWTO
target_object_type: HOWTO
target_tab_code: HOW
```

```markdown
# {{title}}

## Serves

## Preparation time

## Ingredients

## Equipment

## Steps

## Notes and variations

```

## Backup Procedure

```text
template_code: BACKUP_PROCEDURE
name: Backup Procedure
template_type_code: HOWTO
target_object_type: HOWTO
target_tab_code: HOW
```

```markdown
# {{title}}

## Purpose

## Systems covered

## Backup destination

## Schedule

## Steps

## Verification

## Restore test

## Failure handling

```

---

# 20. Suggested Content Kind to Template Links

Create these initial mappings:

| Content Kind       | Template           | Default |
| ------------------ | ------------------ | ------- |
| NOTE               | BLANK_NOTE         | Yes     |
| IDEA               | IDEA_NOTE          | Yes     |
| JOURNAL_ENTRY      | JOURNAL_ENTRY      | Yes     |
| MEETING_NOTE       | MEETING_NOTE       | Yes     |
| DECISION_NOTE      | DECISION_NOTE      | Yes     |
| CODE_REVIEW_NOTE   | CODE_REVIEW_NOTE   | Yes     |
| REPAIR_PROJECT     | SMALL_HOME_REPAIR  | Yes     |
| REPAIR_PROJECT     | CAR_REPAIR         | No      |
| RENOVATION_PROJECT | REPLACE_ENSUITE    | Yes     |
| SOFTWARE_PROJECT   | SOFTWARE_CHANGE    | Yes     |
| TRAVEL_PROJECT     | TRIP_PROJECT       | Yes     |
| SHOPPING_LIST      | FOOD_SHOPPING_LIST | Yes     |
| RECIPE             | RECIPE             | Yes     |
| BACKUP_PROCEDURE   | BACKUP_PROCEDURE   | Yes     |

---

# 21. Sample Views

Seed these views.

## Recent Notes

```text
view_code: RECENT_NOTES
name: Recent Notes
tab_code: NOTES
view_type_code: LIST
```

```json
{
  "sort": "updated_at DESC"
}
```

## Journal Timeline

```text
view_code: JOURNAL_TIMELINE
name: Journal Timeline
tab_code: NOTES
view_type_code: TIMELINE
```

```json
{
  "date_field": "occurred_at",
  "sort": "occurred_at DESC",
  "group_by": "month"
}
```

## Decision Register

```text
view_code: DECISION_REGISTER
name: Decision Register
tab_code: NOTES
view_type_code: TABLE
```

```json
{
  "filter": {
    "subtype": "DECISION"
  },
  "sort": "occurred_at DESC"
}
```

## Active Projects

```text
view_code: ACTIVE_PROJECTS
name: Active Projects
tab_code: GOALS
view_type_code: BOARD
```

```json
{
  "filter": {
    "status": "ACTIVE"
  },
  "group_by": "area"
}
```

## Active Shopping Lists

```text
view_code: ACTIVE_SHOPPING_LISTS
name: Active Shopping Lists
tab_code: GOALS
view_type_code: LIST
```

```json
{
  "filter": {
    "subtype": "SHOPPING",
    "status": "ACTIVE"
  }
}
```

## Birthday Calendar

```text
view_code: BIRTHDAY_CALENDAR
name: Birthday Calendar
tab_code: CALENDAR
view_type_code: CALENDAR
```

```json
{
  "filter": {
    "event_type": "BIRTHDAY"
  },
  "calendar_mode": "YEAR"
}
```

## Upcoming Expiries

```text
view_code: UPCOMING_EXPIRIES
name: Upcoming Expiries
tab_code: CALENDAR
view_type_code: LIST
```

```json
{
  "filter": {
    "event_type": [
      "WARRANTY",
      "INSURANCE",
      "SUBSCRIPTION"
    ]
  },
  "sort": "event_date ASC"
}
```

## People Directory

```text
view_code: PEOPLE_DIRECTORY
name: People Directory
tab_code: PEOPLE
view_type_code: TABLE
```

```json
{
  "sort": "name ASC"
}
```

## Places Map

```text
view_code: PLACES_MAP
name: Places Map
tab_code: PLACES
view_type_code: MAP
```

```json
{
  "group_by": "source"
}
```

## Physical Assets

```text
view_code: PHYSICAL_ASSETS
name: Physical Assets
tab_code: 3D
view_type_code: TABLE
```

```json
{
  "filter": {
    "object_subtype": "PHYSICAL"
  },
  "group_by": "area"
}
```

## 3D Models Gallery

```text
view_code: THREE_D_MODELS
name: 3D Models
tab_code: 3D
view_type_code: GALLERY
```

```json
{
  "filter": {
    "object_subtype": [
      "BLENDER_MODEL",
      "UE_OBJECT",
      "SCAN"
    ]
  }
}
```

## Dataset Workspaces

```text
view_code: DATASET_WORKSPACES
name: Dataset Workspaces
tab_code: DATA
view_type_code: TABLE
```

```json
{
  "filter": {
    "subtype": "DATASET"
  }
}
```

## Accounts and Budgets

```text
view_code: ACCOUNTS_AND_BUDGETS
name: Accounts and Budgets
tab_code: MONEY
view_type_code: DASHBOARD
```

```json
{
  "include": [
    "ACCOUNT",
    "BUDGET"
  ]
}
```

## Application Inventory

```text
view_code: APPLICATION_INVENTORY
name: Application Inventory
tab_code: APPS
view_type_code: TABLE
```

```json
{
  "sort": "name ASC"
}
```

## Media Timeline

```text
view_code: MEDIA_TIMELINE
name: Media Timeline
tab_code: MEDIA
view_type_code: TIMELINE
```

```json
{
  "date_field": "captured_at",
  "group_by": "month"
}
```

## Audio Playlists

```text
view_code: AUDIO_PLAYLISTS
name: Audio Playlists
tab_code: AUDIO
view_type_code: LIST
```

```json
{
  "filter": {
    "collection_type": "PLAYLIST"
  }
}
```

---

# 22. Suggested Content Kind to View Links

| Content Kind    | View                  | Default |
| --------------- | --------------------- | ------- |
| NOTE            | RECENT_NOTES          | Yes     |
| JOURNAL_ENTRY   | JOURNAL_TIMELINE      | Yes     |
| DECISION_NOTE   | DECISION_REGISTER     | Yes     |
| PROJECT         | ACTIVE_PROJECTS       | Yes     |
| SHOPPING_LIST   | ACTIVE_SHOPPING_LISTS | Yes     |
| BIRTHDAY        | BIRTHDAY_CALENDAR     | Yes     |
| WARRANTY_EXPIRY | UPCOMING_EXPIRIES     | Yes     |
| PERSON          | PEOPLE_DIRECTORY      | Yes     |
| PLACE           | PLACES_MAP            | Yes     |
| PHYSICAL_ASSET  | PHYSICAL_ASSETS       | Yes     |
| BLENDER_MODEL   | THREE_D_MODELS        | Yes     |
| DATASET         | DATASET_WORKSPACES    | Yes     |
| ACCOUNT         | ACCOUNTS_AND_BUDGETS  | Yes     |
| BUDGET          | ACCOUNTS_AND_BUDGETS  | Yes     |
| APP_ITEM        | APPLICATION_INVENTORY | Yes     |
| MEDIA_ITEM      | MEDIA_TIMELINE        | Yes     |
| PLAYLIST        | AUDIO_PLAYLISTS       | Yes     |

---

# 23. Sample Content Patterns

Seed the following patterns.

| Pattern Code            | Name                    | Content Kind        | Default Area | Default Template   | Default View          |
| ----------------------- | ----------------------- | ------------------- | ------------ | ------------------ | --------------------- |
| PERSONAL_DAILY_JOURNAL  | Personal Daily Journal  | JOURNAL_ENTRY       | Personal     | JOURNAL_ENTRY      | JOURNAL_TIMELINE      |
| WORK_MEETING            | Work Meeting            | MEETING_NOTE        | Work         | MEETING_NOTE       | RECENT_NOTES          |
| LIFEPIM_CODE_REVIEW     | LifePIM Code Review     | CODE_REVIEW_NOTE    | LifePIM      | CODE_REVIEW_NOTE   | RECENT_NOTES          |
| FOOD_SHOPPING           | Food Shopping           | SHOPPING_LIST       | Food         | FOOD_SHOPPING_LIST | ACTIVE_SHOPPING_LISTS |
| HOUSE_SHOPPING          | Household Shopping      | SHOPPING_LIST       | House        | FOOD_SHOPPING_LIST | ACTIVE_SHOPPING_LISTS |
| SMALL_HOUSE_REPAIR      | Small House Repair      | REPAIR_PROJECT      | House        | SMALL_HOME_REPAIR  | ACTIVE_PROJECTS       |
| CAR_REPAIR              | Car Repair              | REPAIR_PROJECT      | Vehicles     | CAR_REPAIR         | ACTIVE_PROJECTS       |
| REPLACE_ENSUITE         | Replace Ensuite         | RENOVATION_PROJECT  | House        | REPLACE_ENSUITE    | ACTIVE_PROJECTS       |
| LIFEPIM_SOFTWARE_CHANGE | LifePIM Software Change | SOFTWARE_PROJECT    | LifePIM      | SOFTWARE_CHANGE    | ACTIVE_PROJECTS       |
| HOLIDAY_TRIP            | Holiday Trip            | TRAVEL_PROJECT      | Travel       | TRIP_PROJECT       | ACTIVE_PROJECTS       |
| FAMILY_BIRTHDAY         | Family Birthday         | BIRTHDAY            | Family       |                    | BIRTHDAY_CALENDAR     |
| FRIEND_BIRTHDAY         | Friend Birthday         | BIRTHDAY            | Friends      |                    | BIRTHDAY_CALENDAR     |
| HOME_APPLIANCE          | Home Appliance          | APPLIANCE           | House        |                    | PHYSICAL_ASSETS       |
| HOME_FURNITURE          | Home Furniture          | FURNITURE           | House        |                    | PHYSICAL_ASSETS       |
| BLENDER_DESIGN_ASSET    | Blender Design Asset    | BLENDER_MODEL       | Design       |                    | THREE_D_MODELS        |
| ALRONA_WORLD_OBJECT     | Alrona World Object     | FICTIONAL_OBJECT    | Alrona       |                    | THREE_D_MODELS        |
| WARCRAFT_LOCATION       | Warcraft Location       | GAME_WORLD_PLACE    | Warcraft     |                    | PLACES_MAP            |
| HEALTH_MEASUREMENT      | Health Measurement      | MEASUREMENT_LOG     | Health       |                    |                       |
| MONTHLY_BUDGET          | Monthly Budget          | BUDGET              | Finance      |                    | ACCOUNTS_AND_BUDGETS  |
| SOFTWARE_INVENTORY_ITEM | Installed Software      | DESKTOP_APPLICATION | Computers    |                    | APPLICATION_INVENTORY |

Where an Area does not exist, leave `default_area_id` null.

Where a template or view is intentionally absent, leave the foreign key null.

---

# 24. Seed Ordering

Seed in this order:

1. Root content kinds.
2. Child content kinds.
3. Templates.
4. Views.
5. Content-kind-to-template mappings.
6. Content-kind-to-view mappings.
7. Area mappings.
8. Patterns.

Resolve references by stable code rather than relying on generated numeric IDs.

---

# 25. Testing

Add automated tests consistent with the project’s existing test framework.

Minimum tests:

## Database

* Tables are created successfully.
* Unique codes are enforced.
* Parent-child content kinds work.
* A content kind can map to multiple Areas.
* Duplicate Area mappings are rejected.
* A content kind can map to multiple templates.
* A content kind can map to multiple views.
* Seed execution is idempotent.
* Existing edited seed rows are not overwritten.
* Invalid foreign keys are handled according to current SQLite foreign-key settings.

## Services

* Create and update content kind.
* Assign and remove Areas.
* Mark one Area as default.
* Assign templates and views.
* Mark one template and one view as default.
* Deactivate a record.
* Filter by Area, tab, object type, and mapping status.
* Reject duplicate codes.
* Reject invalid code format.
* Reject invalid JSON configuration.

## User interface

* Inline row creation works.
* Inline row editing works.
* Enter saves.
* Tab moves to the next field.
* Validation errors do not clear entered data.
* Search filters the rows.
* Summary cards apply filters.
* Area tags update the mapping table.
* Scroll position and active filters remain after save where practical.

---

# 26. Acceptance Criteria

The implementation is complete when:

1. Admin contains a visible **Content Catalog** entry.
2. Content Kinds, Patterns, Templates, and Views can all be created and edited.
3. The Version 1–3 database tables exist.
4. Content kinds can be hierarchical.
5. Content kinds can be assigned to multiple existing Areas.
6. Content kinds can have multiple templates and views.
7. Default mappings are supported.
8. The table editor supports fast inline entry.
9. The table editor is implemented as a reusable component rather than a one-off page.
10. Content Kinds can be filtered by tab, Area, object type, mapping status, and active status.
11. Summary counts are shown and can filter the grid.
12. JSON configuration fields are validated but not executed.
13. The supplied sample content kinds, templates, views, mappings, and patterns are seeded idempotently.
14. Missing sample Areas do not cause migration failure.
15. The implementation does not add a new normal top-level LifePIM tab.
16. No export functionality is required.
17. No automatic template suggestions are required.
18. No generic dynamic-view execution engine is required.
19. Existing LifePIM Areas, Projects, Notes, Collections, and tab functionality continue to work without regression.

---

# 27. Explicit Non-Goals

Do not implement the following in this change:

* Automatic selection of templates during content creation.
* Automatic creation of projects, tasks, notes, or events from templates.
* Dynamic execution of arbitrary filters stored in `view_config`.
* Arbitrary SQL stored in configuration.
* A new top-level Content Catalog tab.
* TSV, CSV, Markdown, or JSON export.
* A new Area table.
* A generic system-wide object relationship graph.
* Automatic creation of missing Areas.
* Renaming existing Area database tables.
* Reworking the current Collections engine.
* Replacing existing tab-specific storage tables.

The purpose of this change is to establish the Content Catalog’s full data model, sample configuration, and fast administration interface so it can be populated and used by later LifePIM features.
