# LifePIM Content Catalog — Interface Upgrade Spec

## Goal

Replace the current Content Catalog landing page, which looks primarily like a database editor, with a visual summary of how LifePIM content kinds map across **Areas** and **top-level tabs**.

Retain the existing inline editor, but move it into a dedicated **Editor** mode.

---

## 1. Main navigation

Add three modes at the top of the Content Catalog:

```text
[ Matrix ] [ Report ] [ Editor ]
```

The default mode must be:

```text
Matrix
```

Suggested routes or query parameters:

```text
/admin/content-catalog?mode=matrix
/admin/content-catalog?mode=report
/admin/content-catalog?mode=editor
```

Preserve the selected mode, filters and scroll position where practical.

---

## 2. Matrix mode

Display a matrix with:

* **Areas as rows**
* **LifePIM top-level tabs as columns**
* The number of matching content kinds in each cell

Example:

```text
                    Notes  Goals  Calendar  How  Files  People  Places  Data  3D
Personal               8      4       3       1      2      1       0      2    0
Family                 3      2       8       1      4      5       2      0    1
House                  2     11       4       6      7      2       3      1   12
Travel                 5      7       8       2      6      3      11      1    2
LifePIM                9     10       3       8      7      2       1     12    5
Design                 4      5       2       3      8      1       4      3   17
Unassigned             3      1       0       2      4      0       1      2    4
```

### Required behaviour

* Sticky Area column.
* Sticky tab headings.
* Horizontal and vertical scrolling.
* Totals row and totals column.
* Include an `Unassigned` Area row.
* Include a `No Tab` column.
* Hide root hierarchy kinds such as `NOTE`, `PROJECT` and `EVENT` by default.
* Provide an `Include root kinds` toggle.
* Empty cells should be visually quiet.

### Cell status summary

Each populated cell should show:

* Total content kinds.
* Confirmed count.
* Needs Template count.
* Needs View count.
* Needs Object count.
* Undecided count.

Example:

```text
┌──────────┐
│    8     │
│ ✓5 T2 V1 │
└──────────┘
```

Suggested status abbreviations:

```text
✓ Confirmed
T Needs Template
V Needs View
O Needs Object
? Undecided
```

---

## 3. Matrix cell details

Clicking a matrix cell must open a right-side drawer.

Example:

```text
House → 3D

12 content kinds

Physical Asset          NEEDS_OBJECT
Furniture               NEEDS_OBJECT
Appliance               NEEDS_OBJECT
Tool                    NEEDS_OBJECT
3D Scan                 CONFIRMED
Design Concept          CONFIRMED

[Open Filtered Editor]
```

Each item should show:

* Name
* Code
* Parent
* Object type
* Mapping status
* Default template
* Default view

Clicking an item should open its editable details in the drawer or open the existing editor filtered to that record.

The user must be able to close the drawer and return to the same matrix position.

---

## 4. Matrix filters

Add compact filters above the matrix:

```text
Status
Object Type
Active State
Search
```

Add toggles:

```text
Show status counts
Include root kinds
Include inactive
```

Clicking summary cards such as `Need Objects` should filter or highlight the relevant cells.

---

## 5. Report mode

Add a readable documentation-style report view.

Provide four report groupings:

```text
[ By Tab ] [ By Area ] [ By Object Type ] [ Coverage Gaps ]
```

### By Tab

Example structure:

```text
Notes

Idea
- Code: IDEA
- Parent: Note
- Object type: Note
- Canonical table: lp_notes
- Areas: Personal, Work, LifePIM
- Mapping status: Confirmed
- Templates: Idea Note
- Views: Recent Notes
```

### By Area

Example structure:

```text
House

Goals
- Repair Project
- Renovation Project
- Maintenance Task

Calendar
- Warranty Expiry
- Maintenance Schedule

3D
- Physical Asset
- Furniture
- Appliance
```

### Coverage Gaps

Show sections for:

```text
Needs Templates
Needs Views
Needs Objects
Undecided
Missing Canonical Table
No Area Mapping
No Template
No View
```

The report should be generated from current database content.

Markdown export is not required in this change, but the report model should be suitable for a later `Copy Markdown` or `Download Markdown` action.

---

## 6. Editor mode

Retain the existing inline table editor.

Replace the large full-width blue navigation bars with compact tabs:

```text
[ Content Kinds ] [ Patterns ] [ Templates ] [ Views ]
```

Keep existing functionality:

* Summary counts.
* Search and filters.
* Add Row.
* Inline editing.
* Save.
* Deactivate.
* Area assignment.
* JSON configuration editing.

Matrix and Report views should include `Open in Editor` actions that preserve relevant filters.

Example:

```text
/admin/content-catalog?mode=editor&entity=kinds&area_id=4&tab=3D
```

---

## 7. Summary cards

Show summary cards above the selected mode:

```text
125 Content Kinds
186 Area Mappings
87 Confirmed
14 Need Templates
6 Need Views
17 Need Objects
1 Undecided
```

Also show counts by top-level tab where space permits.

Clicking a card should apply the appropriate filter.

---

## 8. Counting rule

One content kind may be mapped to multiple Areas.

Therefore, display both:

```text
125 unique content kinds
186 Area–Tab mappings
```

Do not treat the sum of all matrix cells as the number of unique content kinds.

Matrix cells represent mappings between:

```text
Area × Canonical Tab
```

---

## 9. Performance

The matrix should initially load aggregated counts only.

Load the full list of content kinds for a cell only when the cell is opened.

The interface must remain responsive with at least:

```text
1,000 content kinds
Several thousand Area mappings
```

Reuse the existing Content Catalog services where possible.

---

## 10. Acceptance criteria

The interface change is complete when:

1. Matrix, Report and Editor modes are available.
2. Matrix is the default Content Catalog view.
3. Areas appear as rows and top-level tabs as columns.
4. Cells show counts and mapping-status summaries.
5. Clicking a cell shows its content kinds in a side drawer.
6. The drawer can open a filtered editor.
7. Report mode supports By Tab, By Area, By Object Type and Coverage Gaps.
8. The existing fast editor remains available.
9. Content Kinds, Patterns, Templates and Views use compact editor tabs.
10. Root kinds and inactive records can be included or excluded.
11. Unique-kind totals are distinguished from Area–Tab mapping totals.
12. Existing Content Catalog CRUD behaviour continues to work.
