# Admin Content Catalog

## Goal

The Content Catalog is where LifePIM decides where every kind of information belongs.

The goal is simple: any "thing" the user wants to keep should be able to be mapped, created, shown, and found again in a proper LifePIM place. A thing may be a note, task, project, list, contact, place, file, recipe, repair job, warranty, media item, dataset, account, 3D object, game-world object, or some future item type.

High-level process:

1. Decide what the thing is.
2. Give it a Content Kind.
3. Assign the tab where it naturally belongs.
4. Assign the Area or Areas that can own it.
5. Decide whether it needs a template for creating it.
6. Decide whether it needs a view for finding or reviewing it.
7. Add a pattern if users need a quick way to create or open that kind of thing.
8. Use Matrix and Report to check that every important kind of information has a clear place.

The catalog does not store the actual user information. It stores the setup rules that tell LifePIM how to classify, create, and display that information.

## The Four Tables

Use Admin > Content Catalog > Editor. The top row has:

```text
Showing : [quick filter]  Table: [Content Kinds | Patterns | Templates | Views]
```

Choose the table you want to work on, then use `+ Add Row`, Search, Save, and the row delete icon.

### Content Kinds

Content Kinds are the master list of things LifePIM understands.

Use this table to answer:

- What kind of thing is this?
- Which parent kind does it sit under?
- Which tab should it appear in?
- Which Area or Areas can it belong to?
- Is it complete, or does it still need a template, view, object/table, or decision?

Examples: Idea, Journal Entry, Meeting Note, Repair Project, Shopping List, Recipe, Person, Place, Warranty Expiry, Software Project, Physical Asset.

### Templates

Templates define starter content for new items.

Use this table when a Content Kind should start with headings, prompts, checklist items, or a standard structure. A template does not decide where an item belongs by itself. It gives the item a useful starting shape.

Examples: Idea Note, Meeting Note, Small Home Repair, Software Change, Trip Project, Food Shopping List, Recipe.

### Views

Views define how items are displayed, filtered, grouped, or reviewed.

Use this table when a Content Kind needs a useful way to find or inspect records. A view may be a list, table, board, timeline, calendar, gallery, map, dashboard, or detail page.

Examples: Recent Notes, Journal Timeline, Decision Register, Active Projects, People Directory, Places Map, Media Timeline.

### Patterns

Patterns are repeatable user-facing starting points.

Use this table when the user needs a quick action such as "New Work Meeting", "New Food Shopping List", "New Small House Repair", or "New LifePIM Software Change". A pattern links the Content Kind, default Area, default Template, and default View into one practical creation or navigation option.

Patterns are usually added after the Content Kind, Template, and View exist.

## Adding Content Kinds

### Example 1: Add A Recipe

Goal: make recipes sort into the HOW tab and Food Area.

1. Go to Editor.
2. Set `Table` to `Content Kinds`.
3. Click `+ Add Row`.
4. Fill in:

```text
Name: Recipe
Code: RECIPE
Parent: How-to
Object Type: HOWTO
Tab: HOW
Subtype: RECIPE
Date Behaviour: CREATED
Areas: Food
Default Area: Food
Mapping Status: NEEDS_TEMPLATE
Active: checked
Notes: Structured recipe instructions.
```

5. Click Save.
6. Later, after adding a recipe template and view, change `Mapping Status` to `CONFIRMED`.

Why this works: Recipe is a type of how-to content. It belongs in the HOW tab, but the Area is Food because that is where the user will expect to find it.

### Example 2: Add A Warranty Expiry

Goal: make warranty expiries sort into Calendar and show up for review.

1. Go to Editor.
2. Set `Table` to `Content Kinds`.
3. Click `+ Add Row`.
4. Fill in:

```text
Name: Warranty Expiry
Code: WARRANTY_EXPIRY
Parent: Event
Object Type: EVENT
Tab: CALENDAR
Subtype: WARRANTY
Date Behaviour: DUE
Areas: House, Vehicles, Computers
Default Area: House
Mapping Status: NEEDS_VIEW
Active: checked
Notes: Expiry date for appliance, vehicle, computer, and other warranties.
```

5. Click Save.
6. Add or link a view such as `Upcoming Expiries`.
7. Change `Mapping Status` to `CONFIRMED` when it has a useful view.

Why this works: a warranty expiry is date-driven, so Calendar is the natural tab. It can belong to several Areas depending on the object being covered.

## Adding Templates

### Example 1: Add A Recipe Template

Goal: make new recipes start with useful headings.

1. Set `Table` to `Templates`.
2. Click `+ Add Row`.
3. Fill in:

```text
Name: Recipe
Code: RECIPE
Template Type: HOWTO
Target Object: HOWTO
Target Tab: HOW
Content Kinds: Recipe
Default For Kind: Recipe
Active: checked
Description: Standard recipe structure.
```

4. In `Template Content`, enter:

```markdown
# {{title}}

## Serves

## Preparation time

## Ingredients

## Equipment

## Steps

## Notes and variations
```

5. Leave `Template Config` blank unless special behaviour is needed.
6. Click Save.
7. Return to Content Kinds and set Recipe to `CONFIRMED` if the view is also ready.

### Example 2: Add A Home Maintenance Template

Goal: make maintenance projects start with inspection, materials, tasks, and final notes.

1. Set `Table` to `Templates`.
2. Click `+ Add Row`.
3. Fill in:

```text
Name: Home Maintenance
Code: HOME_MAINTENANCE
Template Type: PROJECT
Target Object: PROJECT
Target Tab: GOALS
Content Kinds: Maintenance Task, Repair Project
Default For Kind: Maintenance Task
Active: checked
Description: Standard home maintenance project checklist.
```

4. In `Template Content`, enter:

```markdown
# {{title}}

## Problem or maintenance item

## Location

## Inspection notes

## Tools and parts

## Tasks

- [ ] Inspect
- [ ] Decide fix
- [ ] Buy parts
- [ ] Complete work
- [ ] Test result
- [ ] Record cost and notes
```

5. Click Save.

## Adding Views

### Example 1: Add An Upcoming Expiries View

Goal: show warranty, insurance, and subscription dates in one place.

1. Set `Table` to `Views`.
2. Click `+ Add Row`.
3. Fill in:

```text
Name: Upcoming Expiries
Code: UPCOMING_EXPIRIES
Tab: CALENDAR
View Type: LIST
Content Kinds: Warranty Expiry
Default For Kind: Warranty Expiry
Active: checked
Description: Expiry dates that need review before they pass.
```

4. In `View Config`, enter valid JSON:

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

5. Click Save.

### Example 2: Add A Recipe Index View

Goal: find recipes by name, Area, or tags.

1. Set `Table` to `Views`.
2. Click `+ Add Row`.
3. Fill in:

```text
Name: Recipe Index
Code: RECIPE_INDEX
Tab: HOW
View Type: TABLE
Content Kinds: Recipe
Default For Kind: Recipe
Active: checked
Description: Table of recipes for browsing and searching.
```

4. In `View Config`, enter:

```json
{
  "filter": {
    "subtype": "RECIPE"
  },
  "sort": "name ASC",
  "columns": [
    "name",
    "area",
    "tags",
    "updated_at"
  ]
}
```

5. Click Save.

## Adding Patterns

### Example 1: Add A Food Shopping Pattern

Goal: make a quick starting point for food shopping lists.

1. Make sure the `Shopping List` Content Kind exists.
2. Make sure the `Food Shopping` template exists.
3. Make sure the `Active Shopping Lists` view exists.
4. Set `Table` to `Patterns`.
5. Click `+ Add Row`.
6. Fill in:

```text
Name: Food Shopping
Code: FOOD_SHOPPING
Content Kind: Shopping List
Default Area: Food
Default Template: Food Shopping
Default View: Active Shopping Lists
Active: checked
Description: Create a food shopping list.
```

7. Leave JSON config fields blank unless special creation or view filters are needed.
8. Click Save.

Why this works: the user does not need to think about kind, Area, template, or view. The pattern joins those choices into one action.

### Example 2: Add A Work Meeting Pattern

Goal: make a quick starting point for work meeting notes.

1. Make sure the `Meeting Note` Content Kind exists.
2. Make sure the `Meeting Note` template exists.
3. Make sure the `Recent Notes` view exists.
4. Set `Table` to `Patterns`.
5. Click `+ Add Row`.
6. Fill in:

```text
Name: Work Meeting
Code: WORK_MEETING
Content Kind: Meeting Note
Default Area: Work
Default Template: Meeting Note
Default View: Recent Notes
Active: checked
Description: Create a meeting note for Work.
```

7. Optional `Creation Config`:

```json
{
  "default_tags": [
    "meeting",
    "work"
  ]
}
```

8. Click Save.

## Checking Completeness

The catalog is useful when every important thing can be answered clearly:

- What is it?
- Which tab owns it?
- Which Area or Areas can it belong to?
- Does it have a template if users create it often?
- Does it have a view if users need to find or review it?
- Is the mapping confirmed, or is there a known reason it is incomplete?

Use these checks regularly.

### Matrix

Use Matrix to answer: "Can everything be sorted into a place?"

Rows are Areas. Columns are main tabs. A filled cell means there are Content Kinds mapped to that Area and tab.

Check for:

- Empty Areas that should have content.
- Important tabs with very few mapped kinds.
- Unexpected mappings, such as a finance item under Notes when it belongs in Money.
- Undecided items.
- Items that need templates, views, objects, or tables.

Useful controls:

- `Showing`: quick filter for status, inactive rows, or tab.
- `Status`: filter by mapping status.
- `Object Type`: filter by object family.
- `Active`: inspect inactive records.
- `Search`: find names, codes, descriptions, notes, and table names.
- `Include root kinds`: include broad parent kinds such as Note, Task, Project, Event, and File.
- `Include inactive`: include inactive Content Kinds.

### Report

Use Report to review the catalog in readable groups.

Report modes:

- By Tab: confirms that each LifePIM tab has the right kinds of content.
- By Area: confirms that each Area has the right content mapped to it.
- By Object Type: confirms that similar storage/object families are handled consistently.
- Coverage Gaps: shows what still needs work.

Coverage Gaps is the main completeness report. Work through each section:

- Needs Templates: add or link templates, or decide that no template is needed.
- Needs Views: add or link views, or decide that normal browsing is enough.
- Needs Objects: add object/table support before confirming the kind.
- Undecided: make a placement decision or mark as external/do not store.
- Missing Canonical Table: decide where the real item is stored.
- No Area Mapping: assign one or more Areas.
- No Template: check whether a template should exist.
- No View: check whether a view should exist.

### Editor Search

Use Editor Search when cleaning up rows directly:

- Search by name, code, notes, description, or table name.
- Use the delete icon for rows that are wrong and unused.
- If a Content Kind is referenced by child kinds or patterns, deletion may deactivate it rather than hard-delete it.

## Practical Completion Rule

Treat a Content Kind as complete when:

1. It has a clear name and code.
2. It has the right parent, object type, tab, and Area mapping.
3. Its mapping status is no longer `UNDECIDED`.
4. It has a template if users need structured starter content.
5. It has a view if users need a special way to find, browse, group, or review it.
6. It has a pattern if users need a quick creation or navigation action.
7. It appears in the expected Matrix cell and the Report does not show it as a gap.

Some kinds can be complete without a template or view. If that is intentional, add a note explaining why.

## TODO

- Link Content Catalog templates to the actual creation screens for Notes, Goals, How-to, Calendar, and other tabs.
- When creating a new item, offer matching templates based on selected Content Kind, Area, and tab.
- Show Content Kind, Template, View, and Pattern names in search results so users can understand why a result appears.
- Include template names in normal content search results when the item was created from a template.
- Include pattern names in search results when an item was created through a pattern.
- Add a way to preview Template Content from the Content Catalog without opening the full editor row.
- Add a report section for "Template exists but is not linked to any Content Kind".
- Add a report section for "View exists but is not linked to any Content Kind".
- Add a report section for "Pattern has no default template or view".
- Add clearer linking from Matrix and Report rows directly into the filtered Editor table.
