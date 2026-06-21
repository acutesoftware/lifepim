# LifePIM Desktop Todo

Generated from a repository review on 2026-06-15.


#### REMINDER

- [ ] always launch LifePIM from Aggie > LifePIM (thise uses prod data)

- [ ] notes folders works old way, BUT you should use new side bar. The old notes DID get mapped, may need some tweaking but trust the new method!

- [ ] remember to run DEPLOY_TO_PROD.bat after ANY code change


## Privacy

- [ ] Run a dedicated secret scan before every public push. Initial text search did not find obvious committed passwords, tokens, or API keys, but use a tool such as `gitleaks` or `detect-secrets` to catch patterns missed by `rg`.
- [ ] Move personal machine paths out of code and into local configuration. `src/common/config.py` currently contains sample/local paths such as `D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data`, `E:\BK_fangorn\...`, `N:\...`, and `\\FANGORN\...`.
- [ ] Add a safe example config file and ignore real config. `logon_file` points to `configuration/lifepim.par`; document its format, ensure the real file is gitignored, and commit only a `.example` version.
- [ ] Decide whether LifePIM will store passwords at all. `doc/config_layout.md` lists password-related admin/web data; if implemented, use an encrypted vault design rather than ordinary database rows or markdown files.
- [ ] Review bundled CSV/sample data in `data/` and `tests/` for personal information before publishing releases. Contact, note, event, place, money, and file-path tables can easily contain private metadata.
- [ ] Avoid logging sensitive content. `common.data` and user-history logging can store before/after row snapshots; redact note text, contact details, file paths, password records, API keys, and other high-risk fields before writing `sys_user_log`.
- [ ] Add a privacy note to the README explaining what local metadata is collected, where it is stored, and what, if anything, is uploaded to lifepim.com.

## Security

- [ ] Add an explicit authentication/authorization boundary for the Flask app, even if intended for desktop-only use. `flask-httpauth` is listed in `setup.py`, but routes are currently unauthenticated.
- [ ] Disable debug mode for normal launches. `src/app.py` runs `app.run(debug=True)` when executed directly; make debug configurable and default it off.
- [ ] Bind only to localhost in all launch scripts and document the expected URL. Confirm no script starts Flask on `0.0.0.0` without authentication.
- [ ] Add CSRF protection for browser form actions and JSON mutation endpoints. The app has many POST/PUT/PATCH/DELETE endpoints and currently no visible CSRF mechanism.
- [ ] Convert GET delete routes to POST or DELETE with CSRF protection. Current examples include calendar, notes, tasks, contacts, places, files, apps, audio, data, goals, how, and 3D delete routes.
- [ ] Validate filesystem paths against configured allowed roots before reading, writing, importing, or serving files. Current import routes accept user-supplied folders/paths, and file-serving routes read paths from the database.
- [ ] Harden media/audio/note file serving. `send_file` is used for note assets, media files, and audio files; require allowed root checks and deny serving sensitive file types outside the LifePIM data area.
- [ ] Restrict note writes to project default folders. `api/create-note` does this, but edit/save paths still depend on the stored note path and should be checked before writing.
- [ ] Validate dynamic SQL identifiers. Several helpers interpolate table names, column names, and order clauses from metadata; keep these values allowlisted from known table definitions and never accept raw request values.
- [ ] Review admin undo operations. `src/modules/admin/routes.py` can insert, update, and delete arbitrary `entity_type` values from the user log; restrict to known LifePIM tables and columns.
- [ ] Add request size limits and upload validation for CSV imports. Imported files should have size limits, extension checks, and temporary-file cleanup.
- [ ] Add security tests for path traversal, unauthorized mutation, CSRF-sensitive forms, and dynamic SQL identifier allowlists.

## Development

- [ ] Update setup and run instructions. `README.md` still mentions `python web_server.py`, while the current entry point appears to be `src/app.py` / `src/RUN_DESKTOP.BAT`.
- [ ] Replace hardcoded config with environment or profile-based configuration. Include defaults for DB path, data root, upload temp folder, debug flag, port, and external API base URL.
- [ ] Finish project/tab mapping coverage. Existing notes in `doc/config_layout.md` call out mapping every CSV file and database table to a submenu/project.
- [ ] Complete the common task/table model from `doc/config_layout.md`: projects, tags, reminders, passwords/vault decision, budgets, expenses, incomes, checklists, recipes, shopping lists, fuel logs, medical info, warranties, licenses, manuals, bookmarks, journals, logs, meetings, and appointments.
- [ ] Standardize CRUD behavior across modules. Some modules have list/table/cards variants and POST actions, while others use simple GET deletes or direct generic data helpers.
- [ ] Add database migrations instead of ad hoc schema creation. Schema is currently spread across SQL files, `init_database.py`, `common/media_schema.py`, importer setup, and route-level ensure functions.
- [ ] Tighten importer workflows. Keep dry-run visible, report row-level errors, validate mapping choices, and protect against snapshot/authoritative imports tombstoning too much data.
- [ ] Expand automated tests beyond importer and basic modules. Add route tests for every blueprint, CRUD tests for shared `common.data`, and integration tests using a temporary SQLite database.
- [ ] Make search scalable. Full note content search and broad metadata scans should have indexing, pagination, and clear limits for large personal datasets.
- [ ] Clean encoding issues in docs/config comments. Several documents and comments display mojibake for icons; convert files consistently to UTF-8 and verify rendering.
- [ ] Decide module ownership for old scripts. `scripts/dev` and `scripts/prod` include legacy utilities; mark each as supported, migrated, or archived.
- [ ] Add linting/formatting/type checks to the developer workflow. Suggested baseline: `ruff`, `black`, and a small CI job that runs the unit tests.
- [ ] Review `tests/LOAD_TESTING.py`, which is currently modified in the worktree, before committing unrelated todo/doc changes.
