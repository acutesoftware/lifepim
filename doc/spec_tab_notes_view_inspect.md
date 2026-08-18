# Codex Spec — Add Note Viewer “Inspect” Mode

## Goal

Add a new Note Viewer mode called **Inspect** to the existing **View As** dropdown.

The purpose of Inspect mode is to make unusual Unicode, invisible characters, control characters, and potentially corrupted text immediately visible while still keeping the note readable.

This is primarily a diagnostic view for answering:

> “What characters are actually stored in this file?”

Inspect mode must be read-only and must not modify, normalise, clean, re-encode, or otherwise alter the source file.

---

## Existing UI

The Note Viewer already contains a dropdown labelled:

**View As**

Add the new option:

**Inspect**

Do not replace or substantially change any existing viewing modes.

Expected concept:

```text
View As:
  Rendered
  Text
  Inspect
  ...
```

Use the existing naming and ordering conventions in the current codebase.

---

## Inspect Mode Behaviour

When **Inspect** is selected:

1. Load the note as safely as possible while preserving information about the original file contents.
2. Display the text in a plain/raw text-style viewer.
3. Do not render Markdown.
4. Preserve whitespace and line breaks.
5. Highlight unusual characters according to severity.
6. Make normally invisible/problematic characters visible.
7. Allow the user to inspect the Unicode details of highlighted characters.
8. Never alter the file.

The normal text should remain easy to read.

Inspect is not intended to be a traditional hex editor.

---

# Character Classification

Use three broad classifications.

## 1. Normal

Normal printable ASCII characters should display normally with no highlighting.

This includes approximately:

```text
U+0020 through U+007E
```

Examples:

```text
A-Z
a-z
0-9
ordinary punctuation
ordinary ASCII space
```

Normal line endings and tabs should not be treated as errors.

---

## 2. Unusual but Valid

Valid printable Unicode characters that are not ASCII should receive a gentle highlight.

Suggested appearance:

**pale yellow background**

Examples include:

```text
é
ç
£
€
°
—
–
“
”
‘
’
→
✓
```

These characters are not errors.

The highlight merely tells the user:

> This character is not ordinary ASCII.

The viewer must not imply that valid Unicode is corrupt or unsafe.

---

## 3. Suspicious / Problematic

Characters likely to cause parsing, comparison, database, search, display, or interoperability problems should receive much stronger highlighting.

Suggested appearance:

* orange for suspicious whitespace/invisible Unicode
* red for control characters, corruption, malformed encoding, or particularly dangerous invisible characters

Examples include:

### Unicode whitespace

Examples:

```text
U+00A0 NO-BREAK SPACE
U+2000..U+200A unusual Unicode spaces
U+202F NARROW NO-BREAK SPACE
U+205F MEDIUM MATHEMATICAL SPACE
U+3000 IDEOGRAPHIC SPACE
```

These should be visibly represented rather than appearing as an ordinary blank space.

Example display:

```text
hello⟦NBSP⟧world
```

---

### Zero-width characters

Examples:

```text
U+200B ZERO WIDTH SPACE
U+200C ZERO WIDTH NON-JOINER
U+200D ZERO WIDTH JOINER
U+2060 WORD JOINER
U+FEFF ZERO WIDTH NO-BREAK SPACE / BOM
```

Render these explicitly.

Example:

```text
customer⟦ZWSP⟧name
```

These should normally be orange or red.

---

### Bidirectional text controls

Highlight Unicode bidi control characters strongly.

Examples include:

```text
U+202A LEFT-TO-RIGHT EMBEDDING
U+202B RIGHT-TO-LEFT EMBEDDING
U+202C POP DIRECTIONAL FORMATTING
U+202D LEFT-TO-RIGHT OVERRIDE
U+202E RIGHT-TO-LEFT OVERRIDE
U+2066 LEFT-TO-RIGHT ISOLATE
U+2067 RIGHT-TO-LEFT ISOLATE
U+2068 FIRST STRONG ISOLATE
U+2069 POP DIRECTIONAL ISOLATE
```

Render these explicitly and highlight red.

Example:

```text
filename⟦RLO U+202E⟧txt
```

---

### Control characters

Unexpected control characters should be displayed explicitly and highlighted red.

Examples:

```text
U+0000 NUL
U+0001 through U+0008
U+000B
U+000C
U+000E through U+001F
U+007F DELETE
C1 controls U+0080 through U+009F
```

Do not flag expected newline and tab handling as errors.

Example:

```text
hello⟦NUL U+0000⟧world
```

---

### Unicode replacement character

Treat:

```text
U+FFFD REPLACEMENT CHARACTER
```

as strongly suspicious.

Display it with red highlighting and identify it as:

```text
REPLACEMENT CHARACTER
U+FFFD
```

Its presence may indicate that a previous decoding operation already replaced invalid bytes.

---

# UTF-8 / Raw File Handling

Inspect mode should retain enough information to identify malformed UTF-8 rather than hiding it.

Do **not** simply perform:

```python
data.decode("utf-8", errors="replace")
```

and then inspect the resulting string.

Doing so destroys information about invalid bytes.

Preferred approach:

1. Read the original file as bytes.
2. Attempt strict UTF-8 decoding.
3. If decoding succeeds, inspect the resulting Unicode text.
4. If decoding fails, preserve the location and value of the invalid byte sequence.
5. Continue displaying as much of the document as safely possible.
6. Show invalid byte sequences explicitly in the Inspect view.

For example:

```text
hello⟦INVALID UTF-8: FF⟧world
```

or:

```text
⟦INVALID UTF-8: C3 28⟧
```

Highlight invalid byte sequences red.

The exact internal decoding implementation is left to Codex, but it must not silently discard or replace malformed bytes.

---

# Safety

Inspect mode is explicitly read-only.

Opening a file in Inspect mode must never:

* rewrite the file;
* normalise Unicode;
* convert line endings;
* remove control characters;
* replace malformed UTF-8;
* change encoding;
* save automatically;
* update file modification timestamps unnecessarily.

Reading the source file as raw bytes is acceptable and preferred.

Avoid loading arbitrary files as unrestricted binary blobs if the existing Notes viewer has file-type or size safeguards.

Reuse existing Note Viewer safety/size restrictions where appropriate.

If the file is too large to safely inspect, show the same sort of user-friendly error or limit currently used by the Note Viewer rather than attempting an unbounded browser render.

---

# Display

Inspect mode should visually resemble the existing plain-text/raw Note Viewer rather than the rendered Markdown view.

Use a monospace font.

Preserve:

* spaces;
* tabs;
* newlines;
* indentation;
* line wrapping behaviour consistent with the existing Text view.

Highlighted characters should not significantly disrupt text layout.

---

# Highlighting

Suggested severity styles:

### Normal

No special style.

### Valid non-ASCII

Pale yellow background.

Examples:

```text
é
£
—
“
”
```

### Suspicious Unicode / unusual whitespace

Pale orange background.

Examples:

```text
NBSP
ZWSP
WORD JOINER
unusual spaces
```

### Dangerous / malformed / control

Pale red/red-accent background.

Examples:

```text
NUL
control characters
bidi overrides
U+FFFD
invalid UTF-8
```

Use existing LifePIM CSS variables/theme conventions where possible rather than introducing hard-coded colours that conflict with dark mode.

The exact colour values are not important; the distinction between the three classes is.

---

# Invisible Character Rendering

Invisible characters must not merely receive a background colour because there may be nothing visible to colour.

Render them using a compact marker.

Examples:

```text
⟦NBSP⟧
⟦ZWSP⟧
⟦NUL⟧
⟦RLO⟧
```

For especially uncommon characters it is acceptable to include the code point:

```text
⟦U+2060 WORD JOINER⟧
```

Keep the main document readable.

Do not turn every highlighted character into a long label.

---

# Character Details

Highlighted characters should expose details on hover, click, or both.

At minimum provide:

```text
Character
Unicode code point
Unicode name
UTF-8 byte representation
line
column
```

Example:

```text
Character: ’
Unicode: U+2019
Name: RIGHT SINGLE QUOTATION MARK
UTF-8: E2 80 99
Line: 14
Column: 32
```

For invisible characters, the character itself may be represented by its label.

For invalid UTF-8 sequences show:

```text
Type: Invalid UTF-8
Bytes: C3 28
Line/offset: ...
```

A simple browser tooltip is sufficient initially if there is already a suitable tooltip mechanism in LifePIM.

Do not build a complicated side panel unless the existing UI architecture naturally supports it.

---

# Optional Summary

If straightforward within the current Note Viewer architecture, add a small summary at the top of Inspect mode such as:

```text
ASCII: 1,824
Non-ASCII: 14
Suspicious: 3
Errors: 1
```

This is useful but secondary.

Do not add substantial complexity solely for this summary.

The core requirement is the annotated text itself.

---

# Line and Column Tracking

Character positions shown to the user should use normal human-readable numbering:

```text
Line 1
Column 1
```

not zero-based numbering.

For malformed UTF-8 where character position cannot be determined cleanly, a byte offset is acceptable.

Example:

```text
Byte offset: 4821
```

---

# Architecture

Keep this feature local to the Note Viewer where practical.

Prefer a clean separation such as:

```text
read file bytes
    ↓
inspect/decode
    ↓
classified character/token stream
    ↓
Inspect renderer
```

Avoid scattering Unicode classification logic throughout templates or JavaScript.

Create a reusable helper/module for character classification if appropriate.

For example, conceptually:

```python
inspect_note_bytes(...)
classify_character(...)
unicode_character_details(...)
```

Names should follow existing project conventions.

---

# Performance

The Inspect viewer must remain practical for normal note-sized files.

Do not generate a separate DOM element for every ordinary ASCII character if that would cause excessive browser overhead.

Prefer grouping consecutive normal text into spans/text nodes and only producing special markup around highlighted characters.

For example:

```text
normal ASCII run
special character
normal ASCII run
special character
```

rather than one element per character.

---

# HTML Safety

The Inspect renderer must escape file contents before inserting them into HTML.

A note containing:

```html
<script>alert("x")</script>
```

must appear literally as text.

Inspect mode must never execute HTML, JavaScript, Markdown, or embedded content from the note.

This is particularly important because Inspect intentionally displays raw file contents.

---

# Existing Modes

Do not change the behaviour of existing Note Viewer modes.

The implementation should only:

* add **Inspect** to View As;
* add the required backend/frontend handling;
* add minimal styling/helpers necessary for inspection.

Avoid unrelated Note Viewer refactoring.

---

# Tests

Add focused tests for the inspection/classification logic.

At minimum test:

### Plain ASCII

Input:

```text
Hello world
```

Expected:

* no warnings;
* text unchanged.

### Printable Unicode

Input:

```text
François paid £20 — Tuesday
```

Expected:

* `ç`, `£`, and `—` classified as valid non-ASCII;
* no error classification.

### NBSP

Input containing:

```text
hello world
```

with `U+00A0`.

Expected:

* NBSP classified suspicious;
* displayed visibly.

### Zero-width space

Input:

```text
customer​name
```

Expected:

* U+200B detected;
* visible marker rendered.

### NUL

Bytes containing:

```text
hello\x00world
```

Expected:

* NUL detected;
* red/error classification;
* visible marker.

### Replacement character

Input containing:

```text
U+FFFD
```

Expected:

* suspicious/error classification.

### Bidi override

Input containing:

```text
U+202E
```

Expected:

* strongly flagged;
* explicitly visible.

### Invalid UTF-8

Example bytes:

```text
48 65 6C 6C 6F FF 57 6F 72 6C 64
```

Expected:

* surrounding valid text remains viewable;
* `FF` represented as invalid UTF-8;
* source file is not changed.

### HTML safety

Input:

```html
<script>alert("test")</script>
```

Expected:

* displayed literally;
* never executed.

---

# Definition of Done

This work is complete when:

* **Inspect** appears in the existing **View As** dropdown.
* Selecting Inspect opens the note as plain/raw text rather than rendered Markdown.
* Ordinary ASCII remains visually normal.
* Printable non-ASCII characters are gently highlighted.
* unusual Unicode spaces and invisible characters are clearly visible.
* zero-width characters are detected and labelled.
* NUL and other unexpected control characters are detected and strongly highlighted.
* Unicode bidi controls are strongly highlighted.
* U+FFFD is detected and highlighted.
* malformed UTF-8 can be identified without silently replacing or discarding the original bytes.
* highlighted characters provide useful Unicode/byte information.
* raw file contents are HTML-escaped and cannot execute.
* Inspect mode is strictly read-only.
* existing Note Viewer modes continue to work unchanged.
* focused automated tests cover the important classifications.
* implementation stays scoped to this feature and avoids unrelated refactoring.

## Implementation Principle

Keep the first version deliberately simple.

The feature is a **diagnostic text viewer**, not a full encoding editor or hex editor.

Its job is to make this sort of problem obvious at a glance:

```text
This looks like normal text
```

versus:

```text
This⟦NBSP⟧looks normal
customer⟦ZWSP⟧name
hello⟦NUL⟧world
```

while still treating perfectly legitimate Unicode such as:

```text
François paid £20 — Tuesday
```

as valid text that is merely worth visually identifying.
