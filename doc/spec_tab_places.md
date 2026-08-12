# Codex Spec — Extend LifePIM Places for Earth, Virtual Worlds and Internet URLs

## Intent

Extend the existing **Places** functionality so that a LifePIM Place means:

> **Somewhere the user can navigate to.**

A Place may therefore represent:

* a real-world Earth location
* a location inside a virtual/game world
* an Internet location identified by a URL

Do **not** create separate Links, Bookmarks, Game Locations, or URL subsystems.

Keep Places as the single concept and keep all records in the **existing Places table** for now.

Different Place types simply use different optional columns.

The Places tab should become a useful generic browser for:

```text
Places
├── All
├── Earth
├── Virtual World #1
├── Virtual World #2
└── Internet
```

The exact virtual-world names should come from the data/current LifePIM configuration where possible rather than embedding names into the UI unnecessarily.

---

# 1. Preserve the Existing Places Functionality

Start by inspecting the current Places implementation and schema.

Do not unnecessarily redesign or replace existing functionality.

Existing:

* Place records
* Earth/GPS locations
* existing virtual/game-world coordinates
* Areas / Projects / Collections integration
* existing Place details
* existing navigation/routes
* existing database conventions

should continue to work.

This change should be an **extension of Places**, not a replacement.

---

# 2. Single Places Table

Continue using one Places table.

Do not introduce tables such as:

```text
lp_urls
lp_bookmarks
lp_virtual_places
lp_place_types
```

for this implementation.

Add optional columns to the current Places table as required.

Use the project's current naming conventions rather than blindly using the names below.

Conceptually the table needs to support fields similar to:

```text
id

title
description

place_type

# Earth
address_line_1
address_line_2
suburb
state
postcode
country
latitude
longitude

# Virtual worlds
virtual_world
coord_x
coord_y
coord_z
coord_region
coord_notes

# Internet
url

# existing LifePIM metadata
area_id
project_id
favourite
sort_order
created_at
updated_at
...
```

Not every field needs to be populated.

That is intentional.

For example:

```text
title       = Adelaide Botanic Garden
place_type  = address
latitude    = -34.917...
longitude   = 138.611...
url         = NULL
```

versus:

```text
title         = My Base
place_type    = virtual
virtual_world = Alrona
coord_x       = 1534
coord_y       = 829
coord_z       = NULL
url           = NULL
```

versus:

```text
title       = ChatGPT
place_type  = url
url         = https://chatgpt.com/
latitude    = NULL
longitude   = NULL
```

---

# 3. Place Type

Every Place must have a type.

The **first field** when creating a new Place must therefore be:

```text
Type
```

The available choices shown to the user should conceptually be:

```text
Address
URL
Virtual: <World #1>
Virtual: <World #2>
...
```

However, avoid hard-coding separate database `place_type` values for every game world if possible.

Prefer storing:

```text
place_type = virtual
virtual_world = <world name/id>
```

while presenting them in the UI as convenient choices such as:

```text
Alrona
World of Warcraft
Minecraft
```

This allows another virtual world to be added later without requiring another schema change.

At minimum support:

```text
address
virtual
url
```

Existing records must be migrated/backfilled sensibly.

---

# 4. Add Place UI

Change **Add Place** so that it is type-driven.

Initially show only the small set of common fields:

```text
Type *
Title
Description
```

Selecting the Type then exposes fields appropriate to that Place.

Do not present the user with every possible Place column simultaneously.

---

# 5. Add Place — Address

Example:

```text
Add Place

Type: Address
```

Selecting Address should expose:

```text
Title
Description

Address
Suburb / City
State / Region
Postcode
Country

Latitude
Longitude
```

Use whatever address fields already exist in LifePIM rather than unnecessarily duplicating them.

Latitude and longitude remain optional.

A user should be able to enter:

* just a name
* just GPS coordinates
* just an address
* address + coordinates

depending on what information they have.

Do not require geocoding for this change.

---

# 6. Add Place — URL

Example:

```text
Add Place

Type: URL
```

Selecting URL should expose:

```text
URL *
Title
Description
```

The intended interaction is:

1. User selects `URL`.
2. User pastes:

```text
https://chatgpt.com/
```

3. LifePIM attempts to discover the page title.
4. Title becomes:

```text
ChatGPT
```

5. The user may edit or completely replace that title.
6. Save normally.

The URL itself is the Internet equivalent of coordinates.

---

# 7. URL Title Auto-Population

When a URL is entered, attempt to populate the title automatically.

Prefer:

1. HTML `<title>`
2. OpenGraph title if the existing libraries make that straightforward
3. hostname as a fallback

For example:

```text
https://docs.python.org/3/
```

could become:

```text
Python 3 Documentation
```

This must be **best effort only**.

Requirements:

* use a short timeout
* do not make saving dependent on the remote server
* handle redirects
* handle invalid URLs cleanly
* handle sites that reject automated requests
* do not crash or display a server error if title lookup fails
* do not use an external metadata API/service

LifePIM can directly request the supplied URL if necessary.

If lookup fails, fall back to something useful such as:

```text
docs.python.org
```

Most importantly:

> Once the user edits the Title manually, subsequent URL processing must not overwrite their chosen title unexpectedly.

A simple implementation is sufficient. Do not build a complex metadata scraping subsystem.

---

# 8. URL Validation

Perform lightweight URL validation.

Accept normal URLs such as:

```text
https://example.com
http://192.168.1.99
https://example.com/some/page
```

LifePIM is commonly used with local services, so URLs must **not** be restricted to public Internet domain names.

Local addresses such as:

```text
http://treebeard:8080
https://192.168.1.99/
http://localhost:5000/
```

must be valid.

If the user enters:

```text
example.com
```

it is reasonable to normalise this to:

```text
https://example.com
```

if that can be done safely and predictably.

---

# 9. Add Place — Virtual World

Selecting a virtual world should expose fields appropriate to virtual coordinates.

Example:

```text
Type: Alrona
```

then:

```text
Title
Description

X
Y
Z
Region / Zone
Coordinate notes
```

All coordinate components should be optional because different games use different coordinate systems.

For example some games may use:

```text
X / Y
```

while others use:

```text
X / Y / Z
```

or:

```text
Zone + X + Y
```

Do not build game-specific coordinate engines as part of this work.

The objective is simply to allow LifePIM to represent them cleanly.

---

# 10. Places Main Screen

Update the Places screen so the different Place realms/types are easy to browse.

Provide filters/tabs/chips equivalent to:

```text
All
Earth
Internet
<virtual world #1>
<virtual world #2>
```

Use existing LifePIM UI conventions rather than introducing a completely different navigation style.

The filters should be generated from available Place types/worlds where practical.

For example, if the user has no Minecraft locations, there is no need to show an empty Minecraft filter unless the existing design already expects this.

---

# 11. Internet Places Grid

Internet Places should have a useful **clickable grid view**.

This replaces the user's current manually maintained browser page containing approximately 40 frequently used URLs.

A URL tile should contain approximately:

```text
┌─────────────────────────────┐
│ ChatGPT                     │
│ chatgpt.com                 │
│                             │
│ AI assistant                │
└─────────────────────────────┘
```

The entire primary tile/title area should be clickable.

Clicking it should open the URL using the normal system/browser behaviour.

Do not create a special hard-coded "My Links" page.

This must be a generic rendering of:

```text
Places where place_type = url
```

---

# 12. Internet Place Display

For each URL Place, show at least:

* title
* hostname or abbreviated URL
* optional description

If easy using existing functionality, a favicon may also be shown.

However:

**favicon support is optional and must not expand the scope of this work significantly.**

A clean grid using text alone is perfectly acceptable for the initial implementation.

---

# 13. Grid and List Behaviour

If Places already supports multiple presentation modes, extend those rather than replacing them.

Ideally Places can support:

```text
Grid
List
```

For Internet Places, Grid should be the useful default.

For Earth or Virtual Places, retain whatever display currently makes the most sense.

Do not build separate independent pages for each type.

They should share the overall Places infrastructure with type-specific rendering.

---

# 14. Editing Places

Editing an existing Place must use the same conditional form logic.

For example an Internet Place should show:

```text
Type: URL

URL
Title
Description
...
```

and should not clutter the screen with:

```text
Latitude
Longitude
X
Y
Z
```

unless the user changes the type.

---

# 15. Changing Place Type

Allow the Place type to be changed.

For example:

```text
Address -> URL
```

Do not automatically destroy the old values while the edit form is still open.

On save it is acceptable either to:

### Option A — retain irrelevant values

Keep them in the database but ignore them while another type is active.

or:

### Option B — clear irrelevant values

Explicitly clear fields belonging to the previous type.

Prefer whichever approach best fits existing LifePIM patterns.

The important thing is that the UI only interprets fields relevant to the currently selected type.

---

# 16. Existing Records / Migration

Existing Place records must remain valid.

Migration should infer their type conservatively.

For example:

```text
existing GPS/address record
    -> place_type = address

existing game/world coordinates
    -> place_type = virtual
```

Do not delete or recreate the Places table.

Use the project's normal database migration / `ALTER TABLE` mechanism.

Avoid requiring users to rebuild LifePIM data.

---

# 17. Areas, Projects and Collections

Places of all types should continue to behave as normal LifePIM content.

An Internet Place should therefore be usable anywhere another Place can be used.

For example:

```text
Area: Development
Place: GitHub

Area: Finance
Place: Internet Banking

Project: Rome 2027
Place: Hotel Website

Collection: Daily
Place: ChatGPT
Place: GitHub
Place: LifePIM
```

Do not create a separate categorisation mechanism specifically for URLs.

Use LifePIM's existing organisational mechanisms.

---

# 18. Conceptual Rule

Keep this rule visible in code comments/documentation where useful:

> A LifePIM Place is somewhere the user can navigate to.

The addressing system depends upon the Place type:

```text
Earth       -> address / latitude / longitude
Virtual     -> world / virtual coordinates
Internet    -> URL
```

This is the reason URLs belong under Places rather than becoming a new top-level content system.

---

# 19. Avoid Overengineering

Explicitly do **not** add:

* browser bookmark synchronisation
* Chrome/Firefox import
* browser history
* website monitoring
* website screenshots
* page archiving
* web scraping infrastructure
* bookmark folders
* link-specific taxonomy
* URL health checking
* metadata crawler
* separate Links top-level tab
* separate URL database/table

Those can be considered later.

This implementation is simply about making Internet locations another valid kind of Place.

---

# 20. Suggested Implementation Structure

Follow the current LifePIM structure, but conceptually the implementation will likely involve:

```text
Places model/database
    add place_type
    add URL field
    ensure virtual-world fields exist
    ensure Earth/address fields exist

Places routes/API
    support new fields
    URL metadata/title endpoint or equivalent

Places Add/Edit UI
    type selector first
    conditional field groups

Places index
    type/world filters
    type-aware display

Internet renderer
    clickable URL cards/grid
```

Reuse existing components and patterns wherever practical.

---

# 21. URL Title Lookup API

If client-side form behaviour needs a backend call, a small endpoint is sufficient, conceptually:

```text
POST /places/url-metadata
```

Input:

```json
{
  "url": "https://chatgpt.com/"
}
```

Response:

```json
{
  "url": "https://chatgpt.com/",
  "title": "ChatGPT",
  "hostname": "chatgpt.com"
}
```

On failure:

```json
{
  "url": "https://example.com/",
  "title": "example.com",
  "hostname": "example.com"
}
```

Use the project's existing API/route conventions if they differ.

Do not introduce a new framework or service simply for this.

---

# 22. UX Examples

## Add Earth Place

```text
Add Place

Type
[ Address ▼ ]

Title
[ Adelaide Botanic Garden ]

Description
[                       ]

Address
[ North Terrace         ]

Suburb
[ Adelaide              ]

State
[ SA                    ]

Postcode
[ 5000                  ]

Country
[ Australia             ]

Latitude
[ -34.917...            ]

Longitude
[ 138.611...            ]

[Save]
```

---

## Add Internet Place

```text
Add Place

Type
[ URL ▼ ]

URL
[ https://chatgpt.com/  ]

Title
[ ChatGPT               ]

Description
[ AI assistant          ]

[Save]
```

---

## Add Virtual Place

```text
Add Place

Type
[ Alrona ▼ ]

Title
[ Main Base             ]

Description
[                       ]

X
[ 1250                  ]

Y
[ 642                   ]

Z
[                       ]

Region
[ Northern Forest       ]

Notes
[ Near the river        ]

[Save]
```

---

# 23. Acceptance Criteria

The implementation is complete when:

* Existing Places continue to work.
* Places remain stored in a single table.
* Every Place has a type.
* **Type is the first field in Add Place.**
* Selecting Address exposes Earth/address/GPS fields.
* Selecting URL exposes URL/title/description fields.
* Selecting a Virtual world exposes virtual-coordinate fields.
* Irrelevant fields remain hidden.
* URL is stored directly on the Place record.
* Entering a URL attempts to populate Title automatically.
* Auto-populated Title can be overridden by the user.
* Failed URL metadata lookup does not prevent saving.
* Local/private-network URLs are supported.
* Internet Places are clickable.
* Internet Places have a useful grid view.
* Places can be filtered by Earth, Internet and individual virtual worlds.
* Existing virtual Place data continues to work.
* Existing Earth Place data continues to work.
* Areas/Projects/Collections continue to work with all Place types.
* No separate Links/Bookmarks subsystem is introduced.
* No existing unrelated functionality is broken.

---

# 24. Definition of Done

A user should be able to replace a manually maintained page containing commonly used URLs by simply adding those URLs as Places.

They should then be able to go to:

```text
Places → Internet
```

and see a clean clickable grid such as:

```text
ChatGPT        GitHub         LifePIM
Python Docs    Fabric         DBT Docs
Bank           Weather        News
...
```

At the same time, Places should continue to represent physical and virtual locations naturally:

```text
Places → Earth
Places → Alrona
Places → <other virtual world>
Places → Internet
```

No special-purpose page should be necessary.

The resulting model should remain simple:

> **One Places system, one table, multiple ways of expressing where a place is.**
