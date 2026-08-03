# Admin Content Catalog

## Intent

The Content Catalog is a planning list for things that need a home in LifePIM.
It does not create Notes, Goals, Files, Calendar items, or other records.

Each Catalog Item answers four questions:

- Name: what is the item?
- Area: which LifePIM Area is it associated with?
- Tab: which LifePIM tab should contain it?
- Comment: is any explanation needed?

Examples include Backup sources in Computers > Files, Backup schedule in
Computers > Goals / Tasks, Bone health injection in Health > Calendar, and
Recipes in Food > How.

## Matrix

The Matrix shows Areas as rows and LifePIM tabs as columns. Each filled cell
shows up to five Catalog Item names, plus a `+ N more` indicator when the cell
contains more.

Available filters:

- Area
- Tab
- Search

Click a filled cell to open the drawer with all Catalog Items in that Area and
Tab. The drawer can open the filtered Editor for quick edits.

## Report

The Report has two modes:

- By Area: Area sections containing tab groups.
- By Tab: Tab sections containing Area groups.

The summary shows simple coverage counts: total items, complete items, missing
Area, missing Tab, and missing both.

## Editor

Use Editor > Catalog Items to add or edit the main catalog rows. The only
visible fields are:

- Name
- Area
- Tab
- Comment

`content_kind_id` remains hidden. Area and Tab may be blank while an idea is
still being classified.

Templates, Views, and Patterns remain available in the table selector. They
still link to Catalog Items by `content_kind_id`, but they are not redesigned by
the simplified catalog change.
