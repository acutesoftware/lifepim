# Admin Content Catalog

## Intent

The Content Catalog is the place where LifePIM decides where every kind of information belongs.

The goal is to find a clear home for all information. A note, task, project, list, event, file, recipe, contact, place, media item, data item, or future object should have an agreed place in the system: which main tab it belongs to, which Area it belongs to, what template should create it, and what view should show it.

Use the Content Catalog when the system needs an explicit answer to questions like:

- What kind of information is this?
- Which LifePIM tab should it appear under?
- Which Area can own it?
- Is it already supported, or does it still need a template, a view, or an object/table?
- What should be created when the user starts a new item of this type?

The catalog is not meant to store the actual user information. It stores the structure that tells LifePIM how to classify, create, and display information.

## User Process

1. Start in the Matrix.

   The Matrix gives the quickest overview of what LifePIM already understands. It shows Areas down the side and tabs across the top. Each filled cell means that one or more Content Kinds are mapped to that Area and tab.

2. Look for gaps.

   Use the Matrix filters and summary buttons to find inactive items, undecided items, missing templates, missing views, or content that has not yet been assigned to a clear Area or tab.

3. Open a Matrix cell when you want detail.

   Clicking a cell opens the drawer with the Content Kinds in that Area and tab. From there, open the filtered Editor when you need to update the records.

4. Use the Report when reviewing coverage.

   The Report is better for checking groups of records: by tab, by Area, by object type, or by coverage gaps. Use it to decide what still needs work.

5. Use the Editor to make changes.

   The Editor is where you add, update, remove, or deactivate records. Work from left to right:

   - Define the Content Kind first.
   - Add or confirm Patterns that create or classify that kind of content.
   - Add Templates for creating the content.
   - Add Views for displaying or filtering the content.

6. Save each changed row.

   After editing text, choices, checkboxes, or popup selections in a row, click Save at the start of that row.

7. Remove rows carefully.

   The `x` button at the end of a row removes that row. For Content Kinds that are still referenced by child kinds or patterns, LifePIM deactivates the row instead of hard-deleting it so existing references are not broken.

## Matrix

The Matrix shows the catalog as an Area by tab grid.

Use it to answer: "Do we have a place for this type of information?"

Rows are Areas from the normal LifePIM Areas sidebar. Inactive, archived, deleted, and old legacy Areas are excluded by default. Legitimate active Areas can appear even when they currently have no Content Catalog mappings.

Columns are the main LifePIM tabs such as Notes, Goals, Calendar, People, Places, Files, Data, Money, Apps, Media, Audio, and other supported tabs.

Each filled cell shows how many Content Kinds match that Area and tab. When status counts are enabled, the cell also shows compact counts for confirmed items and items that still need templates, views, objects, or decisions.

Available controls:

- Status: filter by mapping status.
- Object Type: filter by the type of object LifePIM expects.
- Active: show active or inactive records.
- Search: search catalog names, codes, descriptions, notes, and table names.
- Show status counts: show or hide the compact counts inside Matrix cells.
- Include root kinds: include high-level parent kinds such as Note, Task, Project, Event, and File.
- Include inactive: include inactive Content Kinds in the Matrix.

Click a filled Matrix cell to open the drawer. The drawer lists the Content Kinds in that Area and tab, including their code, parent, object type, default template, and default view.

## Report

The Report shows the same catalog records in review-friendly groups.

Use it when you want to audit the catalog rather than edit one row at a time.

Report views:

- By Tab: groups Content Kinds under their canonical LifePIM tab.
- By Area: groups Content Kinds under their assigned Areas, then by tab.
- By Object Type: groups Content Kinds by the object type they create or represent.
- Coverage Gaps: groups records that still need work, such as missing templates, missing views, missing object support, undecided mappings, missing canonical tables, or no Area mapping.

The Report is mainly for inspection. Use the Editor when you need to change records.

## Editor

The Editor is where catalog records are maintained. It has four tabs: Content Kinds, Patterns, Templates, and Views.

Common row controls:

- Save: saves the current row.
- `x`: removes the row. If a Content Kind is still referenced, it is deactivated instead.
- Active: controls whether the record is active.
- Search: filters the rows in the current editor table.
- Add: creates a new row at the top of the table.

Popup selection fields use a `...` button. Click it to open the checkbox list, tick the values that apply, then save the row.

Text fields in the editor are compact by default. Longer text boxes start at one-row height and can be resized when you need more room.

## Editor: Content Kinds

Content Kinds are the main catalog entries. A Content Kind describes a type of information LifePIM can store, classify, create, or show.

Enter one row for each meaningful type of information, such as Idea, Meeting Note, Repair Project, Shopping List, Recipe, Contact, Place, Warranty Document, or Financial Account.

Fields:

- Name: the user-friendly name.
- Code: the stable catalog code. Use uppercase words separated by underscores.
- Parent: the broader Content Kind. For example, Meeting Note can have Note as its parent.
- Object Type: the LifePIM object family, such as NOTE, TASK, PROJECT, LIST, EVENT, PERSON, PLACE, FILE, DATA, MONEY, APP, MEDIA, or AUDIO.
- Tab: the main LifePIM tab where this kind should normally appear.
- Canonical Table: the database table or main storage location when known.
- Subtype: a more specific subtype code when the object type has variants.
- Date Behaviour: how date fields should be understood, such as created date, due date, occurred date, start/end date, or recurring date.
- Areas: click `...` and tick every Area this Content Kind can belong to.
- Default Area: the most likely Area for this kind, when one should be preferred.
- Mapping Status: the current catalog status.
- Active: tick when this Content Kind should be used.
- Notes: short internal notes about the decision.

Mapping Status values:

- CONFIRMED: this mapping is accepted and ready to use.
- NEEDS_TEMPLATE: the kind exists but needs a template.
- NEEDS_VIEW: the kind exists but needs a view.
- NEEDS_OBJECT: the kind exists conceptually but needs object or table support.
- EXTERNAL_SYSTEM: the information belongs mainly in another system.
- DO_NOT_STORE: LifePIM should not store this kind of information.
- UNDECIDED: the correct handling has not been decided yet.

## Editor: Patterns

Patterns describe a repeatable way that a Content Kind is created, classified, or opened.

Use Patterns when the user needs a recognizable starting point, such as "New Idea", "Small Home Repair", "Trip Project", or "Recipe".

Fields:

- Name: the user-friendly pattern name.
- Code: the stable pattern code. Use uppercase words separated by underscores.
- Content Kind: the Content Kind this pattern creates or represents.
- Default Area: the Area normally used by this pattern.
- Default Template: the template used when creating from this pattern.
- Default View: the view normally used after creation or when browsing this pattern.
- Active: tick when the pattern should be available.
- Notes: short internal notes.
- Description: a short single-line explanation.
- Creation Config: optional JSON configuration for creation behaviour.
- View Filter Config: optional JSON configuration for filtering the view.

Keep Creation Config and View Filter Config as valid JSON when they are used. Leave them blank when no special configuration is needed.

## Editor: Templates

Templates define the starting content for new items.

Use Templates when a Content Kind should open with headings, checklist items, prompts, or a standard structure.

Fields:

- Name: the user-friendly template name.
- Code: the stable template code. Use uppercase words separated by underscores.
- Template Type: the kind of template, such as NOTE, PROJECT, LIST, EVENT, HOWTO, OBJECT, or MULTI_OBJECT.
- Target Object: the object type this template creates.
- Target Tab: the tab where the created item belongs.
- Content Kinds: click `...` and tick every Content Kind that can use this template.
- Default For Kind: the Content Kind this template should be the default for, when applicable.
- Active: tick when the template should be available.
- Notes: short internal notes.
- Description: a short description of what the template is for.
- Template Content: the actual starter content, headings, prompts, or checklist text.
- Template Config: optional JSON configuration for template behaviour.

Template Content and Template Config start as one-line fields in the table. Resize them when editing longer content.

## Editor: Views

Views define how content should be displayed, grouped, filtered, or reviewed.

Use Views when a Content Kind needs a specific list, table, board, calendar, timeline, gallery, map, tree, dashboard, or detail view.

Fields:

- Name: the user-friendly view name.
- Code: the stable view code. Use uppercase words separated by underscores.
- Tab: the LifePIM tab where the view belongs.
- View Type: the display style, such as TABLE, LIST, TIMELINE, CALENDAR, BOARD, GALLERY, MAP, TREE, DASHBOARD, or DETAIL.
- Content Kinds: click `...` and tick every Content Kind that can use this view.
- Default For Kind: the Content Kind this view should be the default for, when applicable.
- Active: tick when the view should be available.
- Notes: short internal notes.
- Description: a short description of what the view is for.
- View Config: optional JSON configuration for filtering, grouping, columns, sorting, or display behaviour.

View Config must be valid JSON when used. Leave it blank when the default view behaviour is enough.

## Practical Working Pattern

When adding a new information type, use this order:

1. Add or confirm the Content Kind.
2. Assign the correct Area or Areas.
3. Set the canonical tab and object type.
4. Decide the Mapping Status.
5. Add a Template if the user needs starter content.
6. Add a View if the user needs a specific way to see the records.
7. Add a Pattern if the user needs a shortcut or repeatable creation flow.
8. Return to the Matrix and confirm the item appears in the right Area and tab.

The catalog is complete when every important type of information has a clear Content Kind, a sensible Area and tab, and enough template/view support for the user to create and find it again.
