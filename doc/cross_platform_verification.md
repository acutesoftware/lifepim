# Cross-Platform Verification

Last verified: 2026-08-17

## Scope

This check covers path values persisted in configuration and SQLite, path values entered through admin/area/note/app workflows, and imports or process launch code that can fail when run on Windows or Linux.

Path values stored in config or SQLite should remain in the style the user configured:

- Windows examples such as `N:\duncan\LifePIM_Data\DATA` stay Windows-style.
- POSIX examples such as `/home/alice/LifePIM/DATA` stay POSIX-style.
- Code that compares, joins, or derives roots from paths must handle either separator style without rewriting persisted values to the current host OS.

## Regression Tests

Run the focused cross-platform checks with:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cross_platform
```

The test module verifies:

- `common.user_paths.normalize_path` preserves Windows and POSIX path style.
- User root subpaths are joined with the configured root's separator style.
- Windows configured roots do not become mixed paths on Linux, such as `N:\base/alice`.
- Existing note root detection works for both `...\DATA\notes\...` and `.../DATA/notes/...`.
- Area path validation accepts absolute paths from either platform without forcing `os.path.abspath`.
- Admin username placeholder replacement preserves separator style.
- App open-file actions use the cross-platform system opener instead of unguarded `os.startfile`.

## Broader Verification

Run the full test suite with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Current result on 2026-08-17:

```text
Ran 342 tests in 10.290s
OK
```

## Audit Notes

- Windows-only imports found in `modules.apps.importers.windows_shortcuts` are guarded and fall back to PowerShell shortcut parsing.
- `os.startfile` calls should only appear inside Windows platform branches or behind `hasattr(os, "startfile")`.
- Legacy ETL/file-listing scripts still contain Windows-specific defaults and path aliases. Those values are treated as user/environment configuration and should not be rewritten by shared application path helpers.
