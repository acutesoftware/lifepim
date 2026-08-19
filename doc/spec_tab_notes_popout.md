# LifePIM Codex Spec: Pop-Out Notes

## Goal

Add a simple **Pop Out** capability to LifePIM Notes.

From any note, the user should be able to open that note in a separate small browser window for quick viewing and editing.

The pop-out is deliberately simple:

* it is just another browser client displaying the existing LifePIM note;
* it uses the existing LifePIM note read/save mechanisms;
* it does **not** require a popup manager, database tracking, background process, or special window lifecycle management;
* closing a pop-out must have no effect on the underlying note;
* multiple different notes may be popped out at the same time.

The priority is **simplicity and reliability**.

---

# 1. Add `Pop Out` to Notes

Add a **Pop Out** action to the existing Note UI.

Place it somewhere appropriate alongside the existing note actions such as View/Edit.

When selected, open the current note in a separate browser window using `window.open()`.

Conceptually:

```javascript
window.open(
    "/notes/<note_id>/popout",
    "lifepim-note-<note_id>",
    "width=600,height=700,resizable=yes"
);
```

Exact dimensions may be adjusted to suit the existing LifePIM UI.

The pop-out should:

* open as a normal independent browser window;
* be resizable;
* be movable by the operating system;
* not require the main LifePIM browser window to remain open.

Do not implement custom drag/drop window behaviour inside LifePIM.

---

# 2. Pop-Out URL

Add an appropriate route for displaying a note in pop-out mode.

Preferred form:

```text
/notes/<note_id>/popout
```

Reuse the existing LifePIM note loading infrastructure wherever possible.

Do not duplicate note lookup or storage logic unnecessarily.

The pop-out route should retrieve exactly the same canonical note as the standard Notes UI.

---

# 3. Browser Window Title

The HTML/browser window title must be:

```text
LifePIM Note : <note name>
```

Example:

```text
LifePIM Note : Book Ideas
```

If the note name changes during editing and the existing application architecture makes it easy to update dynamically, update the browser title accordingly.

Otherwise updating it after reload is acceptable for the initial implementation.

---

# 4. Simplified Pop-Out UI

The pop-out must intentionally use a greatly simplified interface.

Do not display the normal LifePIM:

* top-level navigation;
* sidebar;
* Notes list;
* Areas navigation;
* footer/navigation controls;
* unrelated actions.

The window should contain essentially:

```text
LifePIM Note : Book Ideas

View | Edit | Save | Close

---------------------------------

note content/editor

---------------------------------
```

Exact styling should reuse existing LifePIM styling where practical.

Do not create a separate visual design system.

---

# 5. Pop-Out Toolbar

The pop-out toolbar/menu must contain exactly these primary actions:

```text
View | Edit | Save | Close
```

## View

Switch the note to its normal rendered/view mode.

This should use the same Markdown rendering rules as the existing LifePIM Note Viewer.

Do not create a second Markdown renderer.

## Edit

Switch the note into the normal editable Markdown/source mode.

Reuse the existing note editor component or editing behaviour wherever practical.

Editing should operate on the canonical LifePIM note.

## Save

Explicitly save the current edited note.

Reuse the existing LifePIM note-save API/backend logic.

Do not create a separate filesystem-writing implementation specifically for pop-outs.

After a successful save, provide a small unobtrusive confirmation such as:

```text
Saved
```

Do not use blocking browser alerts for normal successful saves.

If save fails, clearly indicate the failure and **do not discard the editor contents**.

## Close

Close the browser pop-out:

```javascript
window.close();
```

Close must not perform destructive actions.

If there are known unsaved edits, warn the user before allowing the window to close.

---

# 6. Saving Architecture

A pop-out note is only another UI onto the existing LifePIM note.

The architecture should remain:

```text
Pop-out browser
       |
       | existing LifePIM request/API
       v
LifePIM backend
       |
       v
existing note-save logic
       |
       v
canonical Markdown file
```

Do **not** allow browser JavaScript to directly write files.

Do not introduce a second save path for pop-outs.

Wherever possible, standard Note editing and pop-out Note editing should eventually execute the same backend save function.

---

# 7. File Safety

Reliability is more important than clever behaviour.

Preserve whatever safe file-writing mechanisms LifePIM currently uses.

If the current implementation does not already protect against interrupted writes, it is acceptable to improve the shared save routine so that writes use a temporary file followed by replacement/rename where practical.

For example:

```text
note.md
   ↓

write note.md.tmp
   ↓
close/flush
   ↓
replace note.md
```

However:

**Do not redesign the Notes persistence subsystem solely for this feature.**

Prefer reuse of the current proven save path.

---

# 8. Multiple Pop-Out Notes

Users must be able to open several different notes simultaneously.

For example:

```text
LifePIM Note : Book Structure
LifePIM Note : Chapter Ideas
LifePIM Note : Backup Research
LifePIM Note : TODO
```

Each window operates independently and simply communicates with the LifePIM backend.

There is deliberately **no requirement** for the main LifePIM window to maintain a list of open pop-outs.

Do not add:

* `lp_popout_windows`;
* persistent popup state;
* popup registration APIs;
* popup heartbeat logic;
* BroadcastChannel management;
* WebSocket window tracking;
* a popup daemon.

These may be considered separately in the future if required.

---

# 9. Reopening the Same Note

Use a deterministic browser window name such as:

```text
lifepim-note-<note_id>
```

where practical.

This means selecting **Pop Out** for the same note again may focus/reuse the existing browser window rather than creating endless duplicates.

If browser behaviour prevents this in some cases, opening another window is acceptable.

Do not build complicated duplicate-window detection.

---

# 10. Concurrent Edit Safety

A note may potentially be open in:

```text
Main LifePIM editor
+
pop-out window
```

or in multiple browser sessions.

Do not silently overwrite newer changes if the existing note system already has version/conflict protection.

If LifePIM currently has no concurrency detection, add lightweight protection if it can be implemented safely without broad architectural changes.

Suitable mechanisms include:

```text
file modified timestamp
```

or preferably:

```text
content/version hash
```

When the note is loaded, remember the version.

When saving, if the on-disk version has changed since the editor loaded it, do not silently overwrite it.

Present an understandable error such as:

```text
This note has changed since it was opened.

Your edits have not been overwritten or discarded.
Reload the latest version before saving.
```

The user's unsaved editor content must remain available.

Avoid automatic merge logic in this implementation.

If implementing conflict detection would require invasive changes to the existing Notes subsystem, keep it outside the initial change and document that limitation clearly rather than introducing risky code.

---

# 11. Unsaved Changes

Track whether the editor differs from its last successfully loaded/saved state.

If the user selects **Close** while edits are unsaved, request confirmation.

Also use `beforeunload` where appropriate so manually closing the browser window can produce the normal browser unsaved-changes warning.

However:

**Do not rely on `beforeunload` as a save mechanism.**

Never assume JavaScript will successfully save during window shutdown.

---

# 12. Autosave

Do **not** add autosave as part of this initial implementation unless LifePIM Notes already autosave.

For the first implementation, preserve the existing Note save semantics.

The explicit:

```text
Save
```

button must always work.

This keeps the initial feature small and predictable.

Autosave can be considered separately later.

---

# 13. Keyboard Behaviour

Where consistent with existing LifePIM behaviour:

```text
Ctrl+S
```

should trigger Save while editing.

Prevent the browser's normal "Save webpage" behaviour when the LifePIM editor has focus and Ctrl+S is used.

Other existing editor keyboard shortcuts should continue to work.

---

# 14. Rendering

Pop-out **View** mode must use the same rendering capabilities as the normal LifePIM Note Viewer.

For example, if standard Notes already support:

* Markdown;
* links;
* headings;
* tables;
* code blocks;
* images;
* special Note viewer functionality;

the pop-out should reuse that existing rendering component rather than independently recreating it.

The purpose of this feature is essentially:

```text
Existing Note Viewer/Editor
+
minimal chrome
+
separate browser window
```

---

# 15. Security

The pop-out must run within the same normal authenticated LifePIM session.

Do not create special unauthenticated popup URLs.

Normal note access permissions must still apply.

A user should not gain access to a note through:

```text
/notes/<id>/popout
```

unless they would normally have permission to access that note.

All note IDs and file paths must continue to be validated by the backend.

Never accept an arbitrary filesystem filename supplied by the browser as the save destination.

---

# 16. Future Compatibility

Build the implementation so the general concept can later be reused for things such as:

```text
Timer pop-outs
Task pop-outs
Calendar event pop-outs
```

but **do not build a generic pop-out framework now unless one naturally falls out of the implementation.**

Avoid prematurely creating:

```text
PopupManager
PopupRegistry
PopupService
Popup database tables
```

A small reusable template/layout such as:

```text
popout_base.html
```

is reasonable if it simplifies future pop-out pages.

The important architectural principle is:

> A pop-out is a disposable browser view of LifePIM-managed state.

For Notes, the markdown file remains the canonical state.

For future Timers, the timer record/state should similarly remain canonical rather than the browser window itself owning the timer.

---

# 17. Suggested File/Layout Structure

Fit this into the existing LifePIM structure rather than forcing these exact names.

A reasonable shape might be:

```text
templates/
    notes/
        note.html
        note_popout.html

static/
    js/
        notes.js
        note_popout.js
```

or reuse the existing Note components if the project already has a component/template structure.

Prefer:

```text
shared viewer
shared editor
shared save API
```

over:

```text
normal note implementation
+
copied pop-out implementation
```

---

# 18. Visual Design

Keep the pop-out intentionally sparse.

Example layout:

```text
┌─────────────────────────────────────────────┐
│ View   Edit   Save   Close                  │
├─────────────────────────────────────────────┤
│                                             │
│ # Book Ideas                                │
│                                             │
│ Some notes here...                          │
│                                             │
│                                             │
│                                             │
├─────────────────────────────────────────────┤
│ Saved                                       │
└─────────────────────────────────────────────┘
```

The content/editor should use most of the available window area.

The toolbar should remain visible and compact.

Do not reproduce the full LifePIM application navigation.

---

# 19. Error Handling

Failures must favour preserving user work.

Examples:

### Note cannot be loaded

Display a clear error.

Do not display a blank editable note that could accidentally overwrite the real file.

### Save fails

Keep all editor content intact.

Display:

```text
Save failed
```

plus useful detail where appropriate.

### File changed externally

Do not automatically overwrite the newer file.

Keep the current editor contents available and report the conflict.

### Note deleted elsewhere

Do not silently recreate it unless that is already the established LifePIM behaviour.

Inform the user clearly.

---

# 20. Scope Boundaries

This change should **not** implement:

* persistent pop-out layouts;
* remembering window screen coordinates;
* always-on-top behaviour;
* global close-all-popouts;
* popup lists;
* inter-window BroadcastChannel messaging;
* WebSockets;
* drag/drop between note windows;
* docking;
* split-screen management;
* timer functionality;
* autosave unless already standard;
* collaborative editing;
* automatic content merging.

Those are explicitly outside the scope of this first implementation.

---

# 21. Definition of Done

The feature is complete when:

* [ ] Any existing LifePIM note has a **Pop Out** action.
* [ ] Pop Out opens the note in a separate browser window.
* [ ] The browser title is exactly `LifePIM Note : <note name>`.
* [ ] The pop-out has the simplified toolbar `View | Edit | Save | Close`.
* [ ] View shows the existing LifePIM rendered note view.
* [ ] Edit exposes the existing Markdown editing capability.
* [ ] Save writes through the existing LifePIM note-save backend.
* [ ] Save success/failure is clearly shown.
* [ ] Closing a pop-out cannot delete or otherwise damage the note.
* [ ] Unsaved changes are protected with a close warning where practical.
* [ ] Multiple different notes can be open simultaneously.
* [ ] A pop-out remains usable even if the main LifePIM browser page is closed or refreshed.
* [ ] No persistent popup/window management subsystem has been added.
* [ ] Existing normal Note behaviour remains unchanged.
* [ ] Existing tests continue to pass.
* [ ] Appropriate tests are added for the new pop-out route and save behaviour.

---

# 22. Implementation Principle

Keep this implementation deliberately boring.

The feature should amount to:

```text
existing LifePIM Note
       +
minimal browser page
       +
window.open()
```

The pop-out window does not own the document and does not require coordination with the primary LifePIM window.

The canonical Markdown file and existing LifePIM backend remain responsible for the note.

This keeps the feature useful while preserving LifePIM's priority of simple, dependable, long-lived data.
