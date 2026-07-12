# Search

LifePIM has two global search modes: Metadata and Note Content.

## Metadata

Metadata is the default search mode. It searches the structured fields stored in
the database, such as file names, paths, titles, media types, artists, albums,
event text, and dates.

Metadata search does not read markdown note bodies. For notes, it searches the
note file name and note path.

## Note Content

Note Content searches inside markdown note bodies. It uses the cached
`lp_note_search_index` table rather than opening every markdown file during each
search.

Build or refresh this index from:

`Settings -> Notes -> Rebuild note search index`

If the note index has not been built yet, Note Content search may return no
matches even when matching text exists in markdown files.

This probably should not be a problem - for recently edited notes appear on the top of the list in Notes tab or overview tab so you should not really have any problems searching for them - they are right there!

Later, will need to work on a better solution


## Current Tab Results

Search results are affected by the tab you search from.

If you search from a specific tab, matches from that tab are shown first under
the current-context results. Matches from other tabs are shown separately as
other matches.

For example:

- Searching from Notes prioritizes note matches.
- Searching from Media prioritizes media matches and can show the media search
  layout.
- Searching from Audio prioritizes audio matches and can show the audio search
  layout.
- Searching from Home searches across areas without a tab-specific priority.

## Project Filtering

If you are already filtered to a project, search keeps that project context.

Project matches should come first. Results are treated as current-context
matches when they match the selected project or the current tab. Other matches
are still shown, but lower down.

This means a search while viewing a project should surface that project's
records before unrelated records.

## More Matches

Search intentionally caps results from each area so global searches stay quick.
When more results exist for a table, the page shows a More matches link. Use
that link to rerun the same query focused on that table.

## Technical Details

The global search route is `/search`, implemented in `src/app.py`.

The shared search implementation is in `src/common/search.py`.

Metadata search uses partial matching with SQL `LIKE`:

```sql
lower(column) LIKE '%term%'
```

Multiple search terms are combined with `AND`. A record must match every term,
but each term may match any configured column for that record type.

The metadata fields are configured in `SEARCH_SPECS` in `src/common/search.py`.
Current searched areas include:

- Notes: `file_name`, `path`
- Data: `name`, `description`, `tbl_name`, `col_list`
- Audio: `file_name`, `path`, `artist`, `album`, `song`
- Media: `filename`, `path`, `ext`, `media_type`
- How: `title`, `description`
- Calendar: `title`, `content`, `event_date`

Metadata search uses caps:

- Current tab: up to 100 results
- Other areas: up to 20 results per area

The note content index is managed by `src/common/note_search_index.py`.

The index table is:

```sql
lp_note_search_index
```

It stores:

- `note_id`
- `file_path`
- `file_mtime`
- `file_size`
- `title`
- `content_text`
- `indexed_at`

Note Content search queries `lp_note_search_index.content_text` with the same
partial `LIKE '%term%'` behavior as metadata search. It does not read markdown
files during the search request.

The index is rebuilt on demand from Settings. Rebuilding deletes existing rows
from `lp_note_search_index`, reads current markdown files referenced by
`lp_notes`, and inserts fresh cached text.

