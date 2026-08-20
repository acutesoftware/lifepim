# Codex Spec — LifePIM Note Templates and Important Notes

## Intent

Add a simple Note Template system to LifePIM using the existing Notes infrastructure.

A template is just a normal note with an `is_template` metadata flag. Templates use the existing note editor and storage model; do not introduce a separate template editor, template file type, form builder, or complex templating system.

Also add an `is_important` metadata flag to notes. Important notes should automatically sort before non-important notes everywhere the normal Notes list/grid sorting is used.

The primary initial template use case is a journal entry, for example:

```markdown
# Journal

{{date}} {{time}}

## Notes

```

When a new note is created from this template, `{{date}}` and `{{time}}` are replaced with the current local date and time.

---

# 1. Scope

Implement:

1. `is_template` metadata flag for notes.
2. `is_important` metadata flag for notes.
3. Editing these flags through the existing Note editor metadata/properties UI.
4. Important-note sort precedence.
5. Convert the existing **Add Note** action into a dropdown.
6. Add:

   * Add Blank Note
   * Add from Template
   * Add from Clipboard
7. Template selection dialog/list.
8. Creation of a normal note by copying a selected template.
9. Basic template variable substitution:

   * `{{date}}`
   * `{{time}}`

Do not build Task Templates or Project Templates as part of this work.

---

# 2. Design Principle

Keep templates deliberately simple.

A Note Template is:

> A normal LifePIM note whose content is copied when creating another note.

Templates should continue to use all existing note functionality:

* existing note editor
* existing note storage
* existing metadata system
* existing Markdown/text behaviour
* existing note naming
* existing folders/Areas/Projects where applicable

Do not create a separate template table unless the existing architecture absolutely requires it.

Prefer adding metadata fields to the existing note model.

---

# 3. Note Metadata Changes

Add two boolean metadata properties to notes:

```text
is_template
is_important
```

Default both to false.

Use the existing convention for boolean metadata fields within the Notes implementation.

Existing notes must continue to work without modification.

If a database migration/schema change is required, it must be backward-safe and initialize existing records as false.

Conceptually:

```text
is_template = false
is_important = false
```

Do not make either field mandatory in legacy note metadata files/records if the existing code supports missing metadata values.

Missing should be interpreted as `false`.

---

# 4. Note Editor — Metadata

Expose both properties in the existing Note editor's metadata/properties area.

Add controls equivalent to:

```text
[ ] Template
[ ] Important
```

Use labels consistent with the existing UI.

These are metadata controls only.

Do **not** add permanent "Template" or "Important" columns, badges, text, banners, or other visual clutter to the normal Notes list/grid.

The user should be able to open a note, edit its metadata, and mark or unmark it as:

* Template
* Important

The normal Save mechanism must persist both flags.

---

# 5. Important Notes — Sort Behaviour

`is_important = true` must take precedence over all existing normal note sort orders.

Conceptually, every normal Notes sort becomes:

```text
ORDER BY
    is_important DESC,
    <existing sort>
```

Examples:

If currently sorting by modified date descending:

```text
Important notes:
    existing modified-date sort

then

Normal notes:
    existing modified-date sort
```

If sorting alphabetically:

```text
Important notes alphabetically

then

Normal notes alphabetically
```

If sorting oldest first:

```text
Important notes oldest first

then

Normal notes oldest first
```

The important flag is therefore a **sort partition**, not a replacement sort order.

Do not change the secondary/current sort logic.

### Important rule

Important notes should be first wherever LifePIM presents the normal note collection and uses the standard Notes sort mechanism.

Avoid independently reimplementing this logic in several UI components if there is already a common note query/sorting layer.

Prefer applying the rule centrally.

---

# 6. Templates and Normal Note Views

A note marked:

```text
is_template = true
```

is still fundamentally a note, but it is primarily intended for template selection and management.

Templates should be accessible through the Notes interface without introducing a new application-level data type.

Add a **Templates** view/filter within Notes.

This should show notes where:

```text
is_template = true
```

If there are no templates, show an appropriate empty state.

Example:

```text
No note templates yet.
```

Provide a convenient way to create one using the existing editor.

Do **not** add Templates to the existing **View As** dropdown.

`View As` remains concerned with how the currently selected note is rendered/viewed.

---

# 7. Add Note Dropdown

Change the current **Add Note** control to a dropdown/button-menu.

Options:

```text
Add Blank Note
Add from Template...
Add from Clipboard
```

Keep the existing button placement and overall Notes UI style where practical.

---

# 8. Add Blank Note

**Add Blank Note** should perform the same behaviour as the existing Add Note operation.

This should be a minimal refactor rather than a rewrite.

No behavioural regression should occur.

---

# 9. Add from Clipboard

Add an **Add from Clipboard** action.

Behaviour:

1. Read plain-text content from the system/browser clipboard.
2. Create a new normal note.
3. Populate its body with the clipboard text.
4. Open it in the normal Note editor.
5. Allow the user to choose/edit the note name using the same new-note workflow already used elsewhere.

Do not attempt:

* rich HTML clipboard parsing
* image import
* file import
* formatting conversion

Plain text is sufficient for this implementation.

If clipboard access is denied or unavailable, handle it gracefully and show a normal user-facing message rather than failing silently.

---

# 10. Add from Template

Selecting:

```text
Add from Template...
```

must display a simple template chooser.

The chooser lists notes where:

```text
is_template = true
```

Use the note title/name as the primary label.

No advanced template catalogue UI is required.

If there are no templates, show an empty state and provide a convenient route to create a template.

Example:

```text
No note templates have been created yet.

[Create Template]
```

---

# 11. Creating a Note from a Template

When the user selects a template:

1. Read the selected template note.
2. Copy its note content.
3. Process supported template variables.
4. Create a **new normal note**.
5. Open the new note in the existing Note editor.

The original template must never be modified by this operation.

The new note must have:

```text
is_template = false
```

regardless of the source template's metadata.

The new note should otherwise behave exactly like any other newly created note.

Do not create a live relationship where later edits to the template affect existing notes.

This is a one-time copy.

---

# 12. Template Metadata Copying

Do not blindly duplicate the complete source note record.

Only copy information appropriate to the new note.

At minimum copy:

```text
note body/content
```

Where existing Notes architecture has useful structural metadata such as an appropriate parent folder, notebook, Area, Project, or content format, retain it only if this matches existing new-note behaviour and is clearly safe.

Explicitly do **not** copy:

```text
note ID
created timestamp
modified timestamp
is_template
```

The new note gets its own normal identifiers and timestamps.

### `is_important`

Do not automatically copy `is_important` from the template.

A template being important is metadata about the template itself, not necessarily about every note created from it.

New notes created from templates should therefore default to:

```text
is_template = false
is_important = false
```

---

# 13. Template Variables

For V1 support only:

```text
{{date}}
{{time}}
```

Variable replacement occurs when the note is created from the template.

Do not dynamically re-evaluate variables when subsequently viewing or editing the note.

---

# 14. `{{date}}`

Replace every occurrence of:

```text
{{date}}
```

with the user's/local machine current date at note creation time.

Use the application's normal local timezone.

Use an unambiguous, stable date representation.

Preferred default:

```text
YYYY-MM-DD
```

Example:

```text
2026-08-20
```

If LifePIM already has a consistent configurable/display date format used for generated content, reuse that rather than introducing another date-format implementation.

Do not use UTC unless the existing application specifically requires it.

---

# 15. `{{time}}`

Replace every occurrence of:

```text
{{time}}
```

with the current local time when the note is created.

Preferred format:

```text
HH:MM
```

24-hour time.

Example:

```text
15:54
```

Seconds are unnecessary.

Again, if LifePIM already has a common local-time formatting helper, use it.

---

# 16. Example Journal Template

A user may create a note named:

```text
Journal Entry
```

with:

```markdown
# Journal

Date: {{date}}
Time: {{time}}

## Notes

```

and mark:

```text
Template = true
```

Selecting:

```text
Add Note
  → Add from Template
  → Journal Entry
```

at 15:54 on 20 August 2026 would create a normal note containing:

```markdown
# Journal

Date: 2026-08-20
Time: 15:54

## Notes

```

The cursor should then be available in the normal editor so the user can immediately type.

---

# 17. Unsupported Template Syntax

Do not create a general template language.

For V1 only recognize exact tokens:

```text
{{date}}
{{time}}
```

Unknown tokens such as:

```text
{{weather}}
{{person}}
{{project}}
```

should be left untouched.

This allows future variables to be added without breaking notes containing similar text.

Do not introduce:

* Jinja
* Mustache library dependencies
* JavaScript expression evaluation
* Python expression evaluation
* conditional blocks
* loops
* executable template content

Simple string substitution is sufficient.

---

# 18. Template Editing

Opening a template from the Templates view should simply open it in the existing Note editor.

The user can:

* edit text
* rename it
* change normal note metadata
* set/unset Important
* unset Template
* save

If `is_template` is cleared, the note should cease appearing in the Templates filter immediately after normal refresh/save behaviour.

No special "template editor" is required.

---

# 19. Template Creation

From the Templates empty state or Templates view, creating a template may reuse the normal new-note workflow.

The only difference is that the newly created note should start with:

```text
is_template = true
```

It then opens in the existing Note editor.

The user can give it a title and body normally.

---

# 20. Search and Existing Notes Functionality

Do not unnecessarily exclude templates from LifePIM's general note storage or search engine.

They remain normal notes.

However, if there is an existing primary Notes listing intended to show the user's working notes, it is acceptable/preferred to avoid clutter by having the normal Notes view default to non-template notes:

```text
is_template = false
```

with the separate **Templates** view exposing:

```text
is_template = true
```

Follow the structure of the current Notes interface rather than introducing duplicate navigation.

Search should still be capable of finding template content unless there is a compelling existing architectural reason otherwise.

---

# 21. Important + Template Combination

Allow both flags to exist independently.

A note may legally be:

```text
is_template = true
is_important = true
```

This should not cause errors.

Within the Templates view, important templates should follow the same important-first sort precedence.

Do not add validation preventing this combination.

---

# 22. Data/API Layer

Where Notes are loaded or saved through an API/service layer, ensure both fields are supported end-to-end:

```text
is_template
is_important
```

This includes, as applicable:

* database/storage model
* ORM/model objects
* serializers
* API responses
* create endpoints
* update endpoints
* front-end note model/state
* editor save/load behaviour

Avoid front-end-only flags that fail to persist.

---

# 23. Backward Compatibility

Existing notes with no values for the new metadata fields must behave as:

```text
is_template = false
is_important = false
```

Do not require manual migration of individual notes.

Do not change:

* existing note content
* existing IDs
* existing timestamps
* existing links between notes
* existing file paths
* existing View As functionality
* existing Inspect/raw/render modes

---

# 24. UI Constraints

Keep this change small and consistent with the current LifePIM UI.

Avoid:

* new large toolbar sections
* template thumbnails
* template categories
* template marketplaces
* template icons on every note
* important icons/banners throughout the UI
* complex form builders
* separate template database screens

The two flags belong primarily in note metadata.

The creation dropdown and Templates view are the only major visible UI changes required.

---

# 25. Suggested Internal Helper

Prefer a small reusable helper for template processing rather than embedding replacements in the UI event handler.

Conceptually:

```python
def render_note_template(content, now=None):
    ...
```

Behaviour:

```text
{{date}} -> local date
{{time}} -> local time
```

Allowing `now` to be passed explicitly will make unit testing deterministic.

Use equivalent structure appropriate to the project's language/framework.

---

# 26. Tests

Add or update tests appropriate to the existing project test structure.

At minimum verify:

### Metadata

* Existing note defaults `is_template` to false.
* Existing note defaults `is_important` to false.
* Flags save correctly.
* Flags reload correctly.

### Template filtering

Given:

```text
Note A is_template=false
Note B is_template=true
Note C is_template=true
```

Templates view returns:

```text
Note B
Note C
```

and not Note A.

### Template copy

Creating from template:

```text
Template content:
Date: {{date}}
Time: {{time}}
```

with a fixed test datetime produces the expected replacements.

Verify source template remains unchanged.

Verify new note:

```text
has a different ID
is_template=false
is_important=false
has new creation metadata
```

### Unknown variables

Input:

```text
{{date}}
{{something_else}}
```

must produce:

```text
<resolved date>
{{something_else}}
```

### Important sorting

Given normal alphabetical sort:

```text
Bravo        important=false
Zulu         important=true
Alpha        important=false
Charlie      important=true
```

result should be:

```text
Charlie
Zulu
Alpha
Bravo
```

The current secondary sort remains intact within each important grouping.

Test at least one other existing sort order if sorting logic is centralized.

### Clipboard

Verify clipboard-created note contains the supplied plain text.

Handle unavailable/denied clipboard cleanly.

---

# 27. Definition of Done

This work is complete when:

* Notes support persisted `is_template` metadata.
* Notes support persisted `is_important` metadata.
* Both flags can be changed from the existing Note editor metadata UI.
* Existing notes safely default both values to false.
* Important notes sort ahead of normal notes while preserving the selected secondary sort.
* The existing Add Note button is a dropdown.
* Dropdown contains:

  * Add Blank Note
  * Add from Template
  * Add from Clipboard
* Add Blank Note retains current behaviour.
* Add from Clipboard creates an editable note from clipboard plain text.
* Add from Template lists only notes where `is_template=true`.
* Choosing a template creates a completely separate normal note.
* The source template remains unchanged.
* New template-derived notes start with:

  * `is_template=false`
  * `is_important=false`
* `{{date}}` resolves at creation time.
* `{{time}}` resolves at creation time.
* Template notes can be created and edited using the existing Note editor.
* Notes has a Templates view/filter rather than adding Template to the View As list.
* Existing Note Viewer modes and note behaviour continue to work.
* No Task Template, Project Template, form-builder, or general scripting/template engine is introduced.

---

# 28. Out of Scope / Future Work

Do not implement these now, but keep the implementation simple enough that they could be added later:

```text
{{title}}
{{datetime}}
{{area}}
{{project}}
{{person}}
```

Possible future functionality:

* Task Templates
* Project Templates
* Project templates creating both tasks and notes
* user-defined template variables
* template categories
* default journal template
* "New Journal Entry" shortcut
* automatic title generation such as:
  `Journal - 2026-08-20`
* recurring generation of journal/daily notes

These should not influence or complicate the V1 implementation.

The goal of this change is intentionally narrow:

> **Templates are normal notes that can be copied, with simple date/time substitution.**
