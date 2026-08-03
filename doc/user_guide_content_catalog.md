# Admin Content Catalog

The Content Catalog is a simple planning and coverage list. It records things
that need a home in LifePIM; it does not create the actual Notes, Goals, Files,
Calendar items, or other data.

Each Catalog Item has:

- Name
- Area
- Tab
- Comment

Area and Tab can be blank while you are still deciding where an item belongs.

## Adding Items

Open Admin > Content Catalog > Editor and select `Catalog Items`.

Use `+ Add Row` for quick entry:

```text
 Add Row     Search ______________________

Name                  Area          Tab             Comment
Backup sources        Computers     Files           Folders to back up
Backup destinations   Computers     Files           NAS and external disk
Backup schedule       Computers     Goals / Tasks   Run each backup set
```

Save each row after editing.

## Matrix

Matrix is the quickest coverage view.

- Rows are Areas.
- Columns are LifePIM tabs.
- Cells show Catalog Item names.

Each cell shows up to five names and `+ N more` when more items exist. Click a
cell to open all matching items in the drawer, then open the filtered Editor
when you need to make changes.

## Report

Report has two modes:

- By Area
- By Tab

Use it to review the same Catalog Items in a readable grouped form.

## Summary

The coverage summary counts:

- Total items
- Items with both Area and Tab
- Missing Area
- Missing Tab
- Missing both

## Related Tables

Templates, Views, and Patterns are still available from the table selector.
They keep their existing schemas and continue to link to Catalog Items by
`content_kind_id`.
