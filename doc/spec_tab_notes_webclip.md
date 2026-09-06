
# LifePIM Desktop — New Note from Webpage

## Goal

Add a **New Note from Webpage** feature to LifePIM.

The user pastes a webpage URL. LifePIM retrieves the useful content, removes advertising/navigation/boilerplate where possible, converts the result to Markdown, and creates a normal LifePIM Note in the configured **default Area**.

The source URL must also be stored as an **Internet Place** in the existing Places database.

Do not create a separate Web Clippings subsystem or special web-note storage system.

The resulting Markdown note must remain an ordinary LifePIM note and ordinary filesystem file.

---

# 1. User workflow

Extend the existing **Add Note** UI with:

```text
Add Note
├── New Note
├── From Template
└── From Webpage
```

Selecting:

```text
Add Note → From Webpage
```

opens a dialog/page containing:

```text
URL:
[ https://example.com/article........................ ]

Method:
[ Auto ▼ ]

[ Fetch Page ]
```

Method dropdown:

```text
Auto
Reader / Article Extract
Rendered Page
Web Archive
```

Internally use these numeric method identifiers:

```python
WEB_METHOD_AUTO = 0
WEB_METHOD_READER = 1
WEB_METHOD_RENDERED = 2
WEB_METHOD_ARCHIVE = 4
```

Intentionally leave method `3` unused.

---

# 2. Default behaviour

Default method:

```text
Auto
```

Auto tries the available approaches in increasing order of complexity:

```text
1. Reader / Article extraction

if unsuccessful:

2. Rendered-page extraction

if unsuccessful:

4. Web Archive
```

Do not use browser rendering unless required.

Do not create a background service or queue system for this feature.

The operation can run synchronously from the UI with a loading indicator.

---

# 3. Method 1 — Reader / Article Extract

This is the preferred/default extraction method.

Use a Python article/content extraction library such as **Trafilatura**.

Process:

```text
URL
 ↓
HTTP fetch
 ↓
HTML
 ↓
Trafilatura
 ↓
main page/article content
 ↓
Markdown
```

Attempt to retrieve:

* page title
* main article/content
* headings
* paragraphs
* lists
* links
* tables where practical
* author if available
* publication date if available
* image references where practical
* site/domain

Remove where possible:

* advertisements
* navigation
* menus
* cookie banners
* related-story blocks
* sidebars
* footers
* social buttons
* repetitive site boilerplate

The goal is readable content, not pixel-perfect preservation.

---

# 4. Determine whether extraction succeeded

Do not treat HTTP 200 as successful extraction.

Create a small validation function, for example:

```python
is_web_content_useful(...)
```

The exact thresholds can be adjusted during implementation, but the test should consider:

* non-empty page title where available
* extracted text length
* paragraph count
* ratio of useful text to navigation/boilerplate
* extraction library result being non-null

A reasonable initial minimum is approximately:

```text
>= 200 characters of extracted body content
```

but do not reject genuinely short pages solely because they are short if the extractor reports valid structured content.

Return a structured result such as:

```python
WebClipResult(
    success=True,
    method_used=1,
    source_url=...,
    final_url=...,
    title=...,
    author=...,
    published_date=...,
    markdown=...,
    html=...,
    site_name=...,
    images=[...],
    warnings=[...],
)
```

Use a dataclass or equivalent rather than passing large unrelated dictionaries around the codebase.

---

# 5. Method 2 — Rendered Page

Some websites construct their content with JavaScript and therefore contain little useful article text in the original HTTP response.

For these pages use **Playwright** or an equivalent existing browser-rendering dependency if one already exists in the project.

Process:

```text
URL
 ↓
headless Chromium
 ↓
page executes JavaScript
 ↓
rendered DOM
 ↓
HTML
 ↓
Trafilatura
 ↓
Markdown
```

The rendered-page method is still an **article extraction method**.

Do not simply dump the entire HTML page into the note.

Suggested sequence:

```python
page.goto(url)
wait until DOM content is loaded
allow reasonable JS rendering time
get page.content()
run extracted HTML through normal article extractor
```

Use sensible timeouts so a broken page does not leave the UI hanging indefinitely.

Do not wait forever for `networkidle`; many modern pages continually make background network requests.

---

# 6. Method 4 — Web Archive

This mode is for difficult pages or when the user explicitly wants a preserved snapshot.

Use **SingleFile** or another suitable standalone-page archiving mechanism.

Prefer the official SingleFile command-line/browser-engine approach rather than writing a custom recursive webpage downloader.

The resulting filesystem structure should be approximately:

```text
web_snip_example_com_long_page_name_20260906.md
web_snip_example_com_long_page_name_20260906.archive.html
```

The `.archive.html` file should be as self-contained as practical.

The Web Archive method must **also create the normal Markdown Note**.

Process:

```text
URL
 ↓
render/archive webpage
 ↓
standalone archived HTML
 ↓
extract readable content from archived/rendered HTML
 ↓
Markdown note
```

Therefore:

```text
Method 4 produces:

1. Markdown note
2. HTML archive
```

The HTML archive is supplementary preservation material, not the primary LifePIM note.

If the archive succeeds but Markdown extraction still cannot identify meaningful article content, create a minimal note containing:

```markdown
# Page title

The webpage was archived but readable article content could not be automatically extracted.

Source: https://example.com/...

Archived copy: ./web_snip_example_com_....archive.html
```

This is preferable to losing the successful archive.

---

# 7. Auto mode

Implement the Auto sequence explicitly and visibly in code rather than hiding multiple fallbacks inside unrelated library calls.

Conceptually:

```python
def fetch_web_note(url):

    result = extract_reader(url)

    if result.success:
        return result

    result = extract_rendered(url)

    if result.success:
        return result

    result = archive_webpage(url)

    return result
```

Retain warnings/errors from earlier attempts for logging/debugging.

For example:

```text
Reader extraction: insufficient content
Rendered extraction: successful
```

The UI should show:

```text
Extracted using: Rendered Page
```

before the user saves the note.

---

# 8. Explicit method selection

If the user explicitly chooses:

```text
Reader / Article Extract
```

only run method `1`.

If the user explicitly chooses:

```text
Rendered Page
```

only run method `2`.

If the user explicitly chooses:

```text
Web Archive
```

only run method `4`.

Only `Auto` performs the fallback chain.

This is useful for testing as well as for pages the user already knows behave badly.

---

# 9. Preview before save

Do **not** immediately save a note after pressing Fetch Page.

After successful extraction open the extracted Markdown in the existing Note editor.

Show at least:

```text
Title: <detected title>

Source:
https://example.com/...

Extracted using:
Reader / Rendered / Web Archive
```

Allow the user to inspect and edit the Markdown before saving.

Use the normal existing Note save mechanism wherever possible.

Do not create a second editor specifically for web clips.

---

# 10. Note filename

Automatically generate the note filename using:

```text
web_snip_[site]_[page_name_very_long]_[yyyymmdd].md
```

Example:

```text
web_snip_bbc_com_why_old_computer_files_are_disappearing_20260906.md
```

Another example:

```text
web_snip_lifepim_com_what_software_will_you_trust_when_you_get_senile_20260906.md
```

## Site component

Derive `[site]` from the hostname.

Example:

```text
https://www.example.com/article
```

becomes:

```text
example_com
```

Prefer removing a leading:

```text
www.
```

Sanitise according to LifePIM's existing filename/path safety rules.

Convert unsuitable filename characters to `_`.

---

# 11. Page-name component

Derive `[page_name_very_long]` from the detected webpage title.

Keep a relatively long descriptive title.

Do not reduce it to a tiny slug.

For example:

```text
Why Your Old Computer Files May Be Hard to Read in Forty Years
```

could become:

```text
why_your_old_computer_files_may_be_hard_to_read_in_forty_years
```

Apply existing LifePIM filename rules.

Collapse repeated separators:

```text
___
```

to:

```text
_
```

Remove leading/trailing separators.

The entire filename must remain within safe filesystem limits.

Prefer preserving as much of the title as possible before truncation.

If truncation is required, truncate the page-name component, not:

```text
web_snip_
```

or:

```text
_yyyymmdd.md
```

---

# 12. Duplicate filenames

A page may be clipped more than once on the same day.

Never overwrite an existing note.

If:

```text
web_snip_example_com_some_page_20260906.md
```

already exists, create:

```text
web_snip_example_com_some_page_20260906_02.md
```

then:

```text
web_snip_example_com_some_page_20260906_03.md
```

etc.

---

# 13. Note location

Save the note into the configured **default Area location**.

Reuse the existing LifePIM Area/default-location resolution code.

Do not create another configuration value specifically for web clips if the application already knows which Area is the default.

Conceptually:

```python
default_area = get_default_area()
target_folder = get_area_notes_path(default_area)
```

Then save the generated note using the ordinary Notes save path.

If no default Area exists, show a useful error rather than silently choosing an arbitrary filesystem location.

For example:

```text
No default Area is configured. Set a default Area before saving this webpage.
```

---

# 14. Save URL into Places

Every successfully accepted/saved webpage clip must also create or reuse a corresponding entry in the existing **Places** database.

Use the existing Internet/URL Place type.

Do not create another URLs table.

Expected conceptual data:

```text
type        = Internet
title       = webpage title
url         = pasted URL
```

Use the actual existing Places schema and models.

Do not invent a parallel schema if field names differ.

---

# 15. URL duplicate handling

Before creating a new Place, check whether that URL already exists.

Preserve the exact URL pasted by the user as the stored URL.

For duplicate comparison, modest normalisation is acceptable, such as:

* case-insensitive hostname
* ignoring a trailing `/`
* ignoring URL fragments such as `#section`

Do not aggressively strip query parameters because some URLs rely on them.

If the URL already exists:

```text
reuse existing Place
```

rather than create another record.

If the existing Place has a user-edited title, do not overwrite that title automatically.

If its title is empty, the extracted page title may populate it.

---

# 16. Link Note and Place

Where the existing LifePIM schema supports relationships between entities, link the new Note to its Internet Place.

Prefer an existing generic relationship/linking mechanism if one is already implemented.

Do not create a large new relationship subsystem solely for this feature.

At minimum ensure that the source URL is retained in the note's normal database metadata so that the Note can be associated with the Place later.

Do **not** add YAML/frontmatter metadata to the Markdown file merely to achieve this.

---

# 17. Source information inside the Markdown note

The Markdown file should also remain understandable outside LifePIM.

Therefore append a simple human-readable source line to the clipped content.

Example:

```markdown
# Why Your Old Computer Files May Be Hard to Read

...article content...

---

Source: https://example.com/article
Captured: 2026-09-06
```

This is content/provenance, not hidden application metadata.

Do not add LifePIM-specific YAML such as:

```yaml
---
source_place_id: 123
web_method: 2
---
```

to the note.

Application metadata belongs in SQLite.

---

# 18. Images

Where practical, locally preserve article images used by the extracted Markdown.

For a note:

```text
web_snip_example_com_article_20260906.md
```

create:

```text
web_snip_example_com_article_20260906.assets/
```

Example:

```text
web_snip_example_com_article_20260906.assets/
    image_001.jpg
    image_002.png
```

Rewrite Markdown image references to relative paths:

```markdown
![Example](web_snip_example_com_article_20260906.assets/image_001.jpg)
```

Do not download:

* tracking pixels
* icons
* tiny decorative graphics
* obvious advertisements where identifiable

Image failure must not cause the entire clip operation to fail.

Record a warning instead.

Example:

```text
Article saved successfully.
2 of 3 images downloaded.
```

---

# 19. Archive file location

For method `4`, store the archive beside the Markdown note.

Example:

```text
web_snip_example_com_article_20260906.md
web_snip_example_com_article_20260906.archive.html
web_snip_example_com_article_20260906.assets/
```

Use a relative link to the archive from the Markdown note when an archive exists.

Example:

```markdown
Archived copy: [web_snip_example_com_article_20260906.archive.html](web_snip_example_com_article_20260906.archive.html)
```

---

# 20. Temporary files

Extraction/rendering may require temporary HTML or downloaded resources.

Use the system/application temporary directory.

Clean temporary material after:

* success
* extraction failure
* user cancellation where practical

Do not leave Chromium profiles, temporary HTML or intermediate assets inside the user's Notes folders.

Only final accepted content belongs there.

---

# 21. URL validation

Allow only web URLs:

```text
http://
https://
```

Reject unsupported schemes such as:

```text
file://
ftp://
javascript:
data:
```

Do not pass URL strings directly into shell commands.

When invoking an external archiver, use a subprocess argument list rather than constructing shell strings.

Example conceptually:

```python
subprocess.run([
    singlefile_executable,
    url,
    output_file,
])
```

rather than:

```python
os.system("singlefile " + url)
```

---

# 22. Local websites

Do not deliberately block private/local network URLs.

LifePIM is a local personal-data application and the user may legitimately want to clip content from:

```text
http://localhost/
http://192.168.x.x/
http://my-nas/
```

Still restrict schemes to HTTP/HTTPS.

---

# 23. Redirects

Follow normal HTTP redirects.

Record both:

```text
source_url
final_url
```

internally where practical.

The Place should preserve the URL the user supplied.

The final URL may be useful metadata for debugging or future provenance.

---

# 24. Errors

Return human-readable errors.

Examples:

```text
Could not connect to webpage.
```

```text
The webpage returned HTTP 404.
```

```text
Reader extraction could not identify useful page content.
```

```text
Rendered page timed out.
```

```text
Web Archive support is not installed.
```

```text
The webpage was retrieved but no readable content could be extracted.
```

Do not expose raw Python exceptions to the normal UI.

Write detailed technical information to the existing LifePIM logging mechanism.

---

# 25. External dependencies

Prefer keeping dependencies isolated behind small adapter modules.

Suggested architecture:

```text
web_clip/
    __init__.py
    models.py
    fetch.py
    extract_reader.py
    extract_rendered.py
    archive.py
    images.py
    filename.py
```

Adapt this to the existing LifePIM structure rather than creating directories simply because this spec names them.

Potential dependencies:

```text
requests/httpx
trafilatura
playwright
SingleFile
```

Reuse existing project HTTP libraries where available.

---

# 26. Keep optional heavy dependencies isolated

Method `1` should work without Chromium.

Methods `2` and `4` may require browser support.

Therefore importing the application must not fail merely because Playwright/SingleFile is missing.

Detect availability when the method is requested.

For Auto:

```text
Reader fails
 ↓
Rendered support installed?
   yes → try Rendered
   no  → record warning and continue
 ↓
Archive support installed?
   yes → try Archive
   no  → return useful failure
```

A missing optional dependency must not break ordinary LifePIM Notes.

---

# 27. Backend API

Use the existing LifePIM routing/API pattern.

A conceptual API could be:

```text
POST /api/notes/web/fetch
```

Input:

```json
{
  "url": "https://example.com/article",
  "method": 0
}
```

Output conceptually:

```json
{
  "success": true,
  "method_used": 2,
  "title": "Example article",
  "markdown": "...",
  "author": "...",
  "published_date": "...",
  "site": "example.com",
  "suggested_filename": "web_snip_example_com_example_article_20260906.md",
  "warnings": []
}
```

This endpoint performs preview/extraction only.

The existing Note Save flow should perform final persistence.

Do not write the final note merely because `/fetch` succeeded.

---

# 28. Save transaction

When the user presses normal Save after reviewing the clip:

1. Resolve default Area.
2. Generate/finalise collision-safe filename.
3. Save Markdown note.
4. Save downloaded/local assets.
5. Save archive HTML if method 4 produced one.
6. Create/update the normal LifePIM note DB record.
7. Find or create Internet Place for URL.
8. Associate Note with Place where supported.
9. Store web capture metadata in SQLite.
10. Refresh the normal Notes UI.

Avoid leaving a half-created Places record when the user fetched a page but then cancelled instead of saving.

**The Place should be created when the clip is saved, not merely when it is previewed.**

---

# 29. Suggested note metadata

Use existing metadata mechanisms and schema conventions.

Useful fields include:

```text
source_type        webpage
source_url
source_final_url
source_place_id
web_capture_method
web_capture_date
web_author
web_published_date
web_archive_path
```

Do not blindly add every field as a physical column if LifePIM already has an appropriate generic metadata mechanism.

Inspect the current Notes schema first and make the smallest sensible schema change.

---

# 30. UI result

After fetching, show something similar to:

```text
--------------------------------------------------
New Note from Webpage

https://example.com/article

Extracted using: Rendered Page

Title:
Why Old Files Become Difficult to Read

Filename:
web_snip_example_com_why_old_files_become_difficult_to_read_20260906.md

[ article Markdown shown in existing editor ]

Warnings:
1 image could not be downloaded.

                         [Cancel] [Save]
--------------------------------------------------
```

The user must be free to:

* edit the title
* edit article content
* remove unwanted extraction junk
* add their own comments
* then save normally

The generated filename does not need to dynamically change after every title edit unless the existing Note editor already behaves this way.

---

# 31. Logging

Use the existing LifePIM logging system.

Useful log events:

```text
WEB_CLIP_FETCH_STARTED
WEB_CLIP_READER_FAILED
WEB_CLIP_RENDER_STARTED
WEB_CLIP_RENDER_FAILED
WEB_CLIP_ARCHIVE_STARTED
WEB_CLIP_EXTRACT_SUCCESS
WEB_CLIP_SAVE_SUCCESS
WEB_CLIP_SAVE_FAILED
```

Include:

* URL
* method requested
* method actually used
* elapsed operation stage where existing logging supports it
* extracted character count
* image count
* archive path where applicable

Do not log the full page contents.

---

# 32. Tests

Add focused unit/integration tests.

## Filename tests

Input:

```text
https://www.example.com/my/page
Title = "This is a Very Long: Page / Name?"
Date = 2026-09-06
```

Expected form:

```text
web_snip_example_com_this_is_a_very_long_page_name_20260906.md
```

Verify illegal path characters are removed.

Verify filename collision suffix:

```text
_02
_03
```

---

## Reader extraction test

Use a fixed local HTML fixture containing:

* header
* navigation
* advert
* article
* footer

Verify the resulting Markdown predominantly contains the article and excludes obvious boilerplate.

Do not make normal automated tests depend on an external live website.

---

## Rendered page test

Use a local test page where JavaScript inserts the article body.

Verify:

```text
Reader → fails/insufficient
Rendered → succeeds
```

---

## Auto fallback test

Mock the extraction layers.

Verify order:

```text
1 → 2 → 4
```

Verify processing stops after the first successful method.

---

## Explicit method tests

Verify:

```text
method=1
```

never invokes method 2 or 4.

Verify:

```text
method=2
```

never invokes method 1 or 4.

Verify:

```text
method=4
```

never invokes method 1 or 2.

---

## Places test

Save a clip for:

```text
https://example.com/article
```

Verify an Internet Place is created.

Save the same URL again.

Verify a duplicate Place is not created.

---

## Save/cancel test

Fetch and preview a webpage.

Cancel.

Verify:

* no Note created
* no Place created
* no final asset directory created

---

## Archive test

Verify method `4` produces:

```text
.md
.archive.html
```

and the Markdown contains a relative archive link.

---

# 33. Manual acceptance test

The feature is complete when the following can be demonstrated:

### Normal article

Paste a normal news/blog/article URL.

Expected:

```text
Auto chooses Reader
```

Readable Markdown appears.

Ads/navigation largely absent.

Save creates:

```text
web_snip_<site>_<page>_<date>.md
```

in the default Area.

An Internet Place exists for the URL.

---

### JavaScript page

Paste a test page whose body requires JavaScript.

Expected:

```text
Reader fails
Rendered succeeds
```

UI reports:

```text
Extracted using: Rendered Page
```

---

### Archive

Choose:

```text
Web Archive
```

Expected files:

```text
web_snip_....md
web_snip_....archive.html
```

Both work independently from the LifePIM UI.

---

# 34. Out of scope for this version

Do not attempt to implement:

* browser extensions
* automatic monitoring of webpages
* scheduled clipping
* paywall bypassing
* CAPTCHA bypassing
* login/password automation
* cookie synchronisation with the user's normal browser
* website-specific scrapers
* full website mirroring
* recursive link crawling
* webpage change detection
* cloud synchronisation
* background clipping services
* a new Web Clips database

Keep this feature a straightforward extension of **Notes + Places**.

---

# 35. Important implementation principle

A clipped webpage must not become dependent on LifePIM.

The important output is:

```text
ordinary Markdown
ordinary images
optional ordinary HTML archive
```

LifePIM provides organisation, extraction and provenance around those files, but the saved data must still be usable directly from the filesystem.

Final data flow:

```text
                    ┌─ Reader extraction ──────────┐
                    │                              │
URL → Web Clip UI ──┼─ Rendered extraction ───────┼→ Markdown
                    │                              │
                    └─ Web Archive ─→ HTML ───────┘
                                      │
                                      ↓
                           Default Area filesystem
                                      │
                        ┌─────────────┴─────────────┐
                        ↓                           ↓
                  normal Note                 archive/assets
                        │
                        ↓
                    LifePIM DB
                        │
                        ↓
               Internet Place for URL
```

Do the implementation by reusing the existing Note editor, Area path resolution, Places model/API, logging system and Note save functions wherever possible.

Avoid duplicate infrastructure.
