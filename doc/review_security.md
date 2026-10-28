# LifePIM Desktop security review

Review date: 2026-10-28 (Australia/Adelaide)

Repository baseline: `9ccdf5d` plus the changes listed in this report

Supported model: one trusted owner, browser UI on the same Windows computer,
loopback HTTP only

## Result

LifePIM is suitable for its stated **local, single-owner** model after the
important operational items at the end of this report are completed. It must
not be treated as a LAN service, public website, hostile multi-user boundary or
sandbox.

The earlier review incorrectly treated LifePIM's ability to run owner-supplied
commands, arbitrary SQL and filesystem operations as vulnerabilities. They are
intentional core capabilities. This revision preserves them and instead
protects their browser entry points from LAN exposure, cross-site requests and
untrusted imported markup.

The principal implemented protections are:

- normal startup is loopback-only and rejects wildcard/LAN bind addresses;
- Caddy/LAN startup was removed, companion/public APIs default to disabled, and
  the live LifePIM Caddy process was stopped;
- local Host validation, CSRF, cross-origin mutation rejection and security
  response headers are enforced centrally;
- Markdown/HTML is sanitized at the render boundary; SVG note assets download
  instead of executing in the application origin; Mermaid is self-hosted and
  uses strict mode;
- destructive/launch actions no longer mutate on GET;
- import size/row/field/recurrence limits were added;
- vulnerable packages identified during the review were updated and a fresh
  dependency audit found no known vulnerabilities.

Two old LifePIM Caddy firewall allow rules still require an elevated shell to
remove. They have no listener after Caddy was stopped, but should not remain.
The currently running Waitress process is loopback-only; restart LifePIM once
to load the new application code.

## Scope and method

The review covered application and test code, templates, browser JavaScript,
launch/deployment scripts, importers, database access, authentication,
filesystem operations, process execution, network clients and documentation.
The mechanically enumerated scope was 440 relevant source/test/script files and
approximately 82,526 lines. Generated/vendor code such as the Mermaid bundle
was treated as a dependency rather than manually line-reviewed.

Methods used:

- route and template review for authentication, CSRF, methods and escaping;
- searches for subprocesses, shell execution, SQL construction, filesystem
  access, uploads/imports, outbound network clients and external assets;
- dependency inventory, `pip check`, and `pip-audit` against the installed
  environment;
- isolated in-memory SQLite and temporary-directory tests;
- live Windows listener, process and LifePIM firewall-rule inspection.

This is a point-in-time code audit, not proof that every parser or dependency is
defect-free. Folder ACLs were assumed correct as requested.

## Trust boundary and intentional powers

The owner and the owner-authored LifePIM records are trusted. The following are
preserved by design and are **not findings** in this deployment:

- command actions use `subprocess.Popen(..., shell=True)` where shell syntax is
  required;
- app/task actions can launch executables, files, URLs and scripts;
- the data catalogue can open configured SQLite databases and run arbitrary
  owner-entered SQL;
- the UI can browse/open configured filesystem paths;
- imports and jobs can create, update or delete the owner's data when the owner
  requests it.

These features are equivalent to actions the signed-in Windows owner could
perform directly. LifePIM is not a security sandbox around them. The safety
requirements are therefore: only the owner can reach the UI; another website
cannot submit actions; imported content cannot become application script; and
the browser cannot mutate state merely by loading a link.

## Findings and disposition

| ID | Original issue | Local-model disposition | Status |
|---|---|---|---|
| SEC-01 | Stored XSS in Markdown, raw HTML, SVG and previews | A real boundary violation because imported content could act as the owner | **Fixed/mitigated**: Bleach render-boundary allowlist, CSP, strict self-hosted Mermaid, SVG attachment download |
| SEC-02 | Authenticated shell execution | Intentional owner capability, not a vulnerability in the supported model | **Preserved**; POST + authentication + CSRF required from the browser |
| SEC-03 | SSRF in URL clipping/place metadata | Owner initiates the fetch, but a malicious redirect can still probe loopback/private services | **Remaining**; see Important tasks |
| SEC-04 | Incomplete per-user ownership | Multi-user access is outside the model; mobile/public surfaces are disabled | **Deferred by design**; must be fixed before any multi-user/LAN mode |
| SEC-05 | Arbitrary folder/SQLite access | Intentional owner capability | **Preserved**; no LAN/public access supported |
| SEC-06 | Vulnerable image/network packages | Real risk while processing remote/imported data | **Fixed for known advisories**; packages updated and audited |
| SEC-07 | State changes over GET | Real cross-site/accidental activation risk | **Fixed** for identified delete, launch, logout and template-create routes |
| SEC-08 | Import exhaustion/active content/partial imports | Real availability and content-boundary risk | **Mitigated** with limits and sanitization; parser/transaction limitations remain |
| SEC-09 | Login/open redirect/password/trusted-token hardening | Low exposure on loopback, but still defence in depth | **Partly remaining/optional** |
| SEC-10 | Missing CSP, CDN code and dependency drift | Real imported-content/supply-chain risk | **Fixed/mitigated**: CSP, local Mermaid, bounded version constraints |
| SEC-11 | LAN Caddy and firewall exposure | Critical mismatch with the actual local-only model | **Code fixed; live Caddy stopped; elevated firewall cleanup pending** |

### Residual security limitations

1. URL fetch SSRF: reader-mode clipping follows HTTP redirects through
   `requests`; place-title lookup uses `urlopen`; Playwright loads pages and
   subresources. A malicious public page can redirect to a private or loopback
   address. This does not provide an unauthenticated remote path—the owner must
   request the URL—but it crosses the imported-content boundary. Central DNS/IP
   validation, per-redirect revalidation and Playwright request interception
   should reject loopback, link-local, private, multicast and reserved targets.

2. CSP currently permits `'unsafe-inline'` for script and style because the
   existing templates contain substantial inline code. Sanitization is the
   primary XSS control. Moving inline scripts to static files and adopting
   nonces/hashes would make CSP independently stronger.

3. Any process running as the same Windows user can connect to loopback, read
   browser/session state, or modify the owner's files. This is inherent in the
   desktop model; OS account security, malware protection and disk/file ACLs
   remain required.

4. Legacy public, logger and Pocket API code remains in the repository behind
   default-off feature flags. Enabling it exits the reviewed threat model. The
   older multi-user authorization findings then become relevant again.

5. Long-lived trusted-device tokens and the login `next` redirect deserve
   stricter lifetime/rotation and same-origin validation. Their risk is reduced,
   not eliminated, by loopback-only access.

## Network and LAN review

### Code/configuration result

- `RUN_DESKTOP.BAT` starts only Waitress and validates `LIFEPIM_HOST` as
  `127.0.0.1`, `localhost` or `::1`.
- `run_waitress.py` independently rejects a non-loopback host.
- direct `app.py` startup uses no debug/reloader and rejects a non-loopback
  configured host.
- `ProxyFix` was removed, so untrusted forwarded headers are not used.
- requests with a non-local `Host` header are rejected with 400.
- public note, Pocket and logger endpoints return 404 by default.
- normal startup no longer starts or regenerates Caddy.

### Live check on 2026-10-28

Before remediation, Caddy PID 22624 listened on `:::80` and `:::443`, and
Waitress listened on `127.0.0.1:9741`. Caddy used
`C:\apps\caddy\Caddyfile`, the LifePIM configuration. The review stopped that
Caddy instance. A repeat check showed only `127.0.0.1:9741` listening among
ports 80, 443 and 9741.

The following enabled inbound rules remain because the current shell was not
elevated:

```text
LifePIM Caddy HTTP LAN   Private, Public
LifePIM Caddy HTTPS LAN  Private, Public
```

Run the repository cleanup script as Administrator. It removes only these
LifePIM-specific names (and a legacy `LifePIM Waitress` rule if present).

A second-device test cannot be performed from this development shell. After
restart, manually confirm from a phone/other computer that the desktop LAN IP
does not answer on 9741, 80 or 443.

## Browser and request security

- Login remains required for private routes.
- Flask-WTF CSRF is active for browser POSTs. Layout JavaScript inserts the
  token in POST forms and same-origin fetch calls.
- cross-site mutation requests are rejected using `Origin` and
  `Sec-Fetch-Site` checks;
- cookies are HttpOnly and SameSite=Lax. Secure cookies default off because the
  supported endpoint is loopback HTTP; enable them only with intentional
  loopback HTTPS;
- response headers include CSP, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, no-referrer and a restrictive Permissions-Policy;
- identified delete, logout, run/launch and template-create links now submit
  POST forms. GET remains only for displaying forms/confirmation pages.

## Imported data and content

### Protections added

- Markdown output is always cleaned with a maintained HTML sanitizer. Script,
  event-handler and unsafe URL-protocol attributes are removed while safe
  tables, code and Mermaid classes remain.
- note SVG assets are attachments with sandbox/nosniff headers rather than
  active same-origin documents;
- upload/import maximum defaults to 20 MiB, CSV fields to 1 MiB, imports to
  100,000 rows and previews to 500 rows (environment-configurable downward or
  for an informed owner);
- ICS expansion is capped at 100,000 events;
- web fetches already have response byte and timeout bounds; Pillow was updated
  before further remote-image processing;
- templates found joining table names as trusted HTML now render each name via
  normal Jinja escaping.

### Remaining import risks

- compressed XLSX/other archives can expand far beyond their upload size and
  some pandas/openpyxl paths materialize data before the row limit applies;
- not every multi-row importer wraps all writes in one transaction, so an
  error can leave a partial import;
- CSV cells beginning with spreadsheet formula characters can be dangerous if
  later exported and opened in Excel; export paths should prefix/escape them;
- filename extensions and parser exceptions are not a substitute for content
  signatures. Malformed files can still consume CPU/memory or exercise parser
  bugs;
- filesystem containment checks may need explicit junction/symlink testing for
  every configurable Windows root;
- URL-import SSRF remains as described above.

These are primarily local availability/integrity risks because importing is an
owner action. Use backups and import unfamiliar bulk data into a disposable
test data root first.

## Outbound and API calls

No cloud service is required for core startup, login, notes, tasks, commands,
SQL or normal local file use. Browser `fetch()` calls used by the UI are
relative/same-origin and fail only the corresponding interactive feature if the
local endpoint is unavailable.

| Destination/API | Trigger and purpose | Data/effect | If unavailable |
|---|---|---|---|
| User-supplied HTTP/HTTPS URL (`requests`, `urlopen`, Playwright) | Web clipping, rendered/archive capture, place-page title lookup | Sends normal HTTP metadata and downloads page/resources; may store extracted text/images | Clip/title lookup fails or falls back; core app works |
| Nominatim / OpenStreetMap | Place search and reverse geocoding | Address/search text or coordinates plus client IP/User-Agent | Geocoding fields are not filled; places remain manually editable |
| Geofabrik Australia download | Explicit local-map data download | Downloads public OSM extract | Offline/local map data cannot be refreshed |
| Yahoo Finance chart endpoint | Explicit quote/history refresh | Requested ticker, date/range parameters and client IP | Market data is stale/unavailable; stored money data remains |
| South Australian Department for Education pages | Explicit school-term import | Standard GET metadata | School-term import fails; manual/calendar data remains |
| Google Maps/OpenStreetMap links | Owner clicks an external map link | Browser opens coordinates/search query | External map does not open |
| Local `127.0.0.1:9741/login` | Deployment readiness probe | No external data; loopback request only | Deployment script reports startup failure |

Legacy inbound APIs:

- `/api/pocket/v1/*`: mobile pairing/sync; disabled by default and unnecessary.
- `/api/logger/v1/*`: logger ingestion/file opening; disabled by default and
  unnecessary.
- `/public/*`: unauthenticated publication routes; disabled by default.

Enabling any of them requires a new threat-model and authorization review.

## Dependency inventory

The direct runtime dependencies declared in `requirements.txt` are:

| Dependency | Purpose |
|---|---|
| Flask, Werkzeug, Jinja2, MarkupSafe, blinker, click, colorama, itsdangerous | Web framework, routing, templates, signing and CLI/runtime support |
| Flask-Login | Owner session authentication |
| Flask-WTF, WTForms (transitive) | CSRF and forms |
| argon2-cffi | Password hashing |
| waitress | Production loopback WSGI server |
| Markdown, Bleach | Markdown conversion and safe HTML allowlisting |
| pandas, numpy | Tabular processing/imports |
| openpyxl, xlrd | Excel workbook imports |
| python-dateutil, pytz, tzdata, six | Dates, recurrence/time-zone compatibility |
| requests, urllib3, certifi | HTTPS fetching and certificate verification |
| trafilatura, soupsieve | Web article extraction and HTML selection |
| Pillow | Imported/remote image processing |
| Playwright | Optional rendered web clips and browser PDF capture |

The browser also vendors Mermaid 12.0.0 as `src/static/mermaid.min.js`; it is
loaded locally rather than from a runtime CDN.

Updates made during this review:

- Werkzeug 3.1.6 -> 3.1.9
- argon2-cffi 23.1.0 -> 25.1.0
- Pillow 12.2.0 -> 13.0.0
- urllib3 2.7.0 -> 2.8.0
- certifi 2026.6.17 -> 2026.10.23
- soupsieve 2.8.4 -> 3.0.4 (constraint `>=2.9,<4`)
- Bleach 6.4.0 added for output sanitization
- Playwright 1.62.0 added to requirements because runtime code imports it

`pip check` reported no broken requirements. `pip-audit 2.10.1 --local` on the
updated environment reported **no known vulnerabilities** on the review date.
This is not a future guarantee: repeat the audit during every update. Packages
installed in the developer virtual environment but not imported by LifePIM
(for example test/experimental packages) are not application dependencies.

## Verification performed

```text
python -m compileall -q src tests                         PASS
python -m pip check                                      PASS
python -m pip_audit --local --progress-spinner off       PASS, no known vulnerabilities
tests.test_local_security + test_caddy_lan_hosts +
tests.test_auth_routes                                   13 passed
tasks/apps, data catalogue, importer and Markdown tests  26 passed
test_notes_webclip with tests/src on PYTHONPATH           23 passed, 2 skipped
git diff --check                                         PASS (line-ending notices only)
```

The isolated tests cover loopback host validation, hostile Host rejection,
authentication redirect, cross-site mutation rejection, missing CSRF,
default-off companion endpoints, executable-markup stripping, safe Markdown
features, Caddy loopback generation, logout method, harmless mocked command
launch, in-memory SQL/data operations and web-clipping fixtures.

The prior full-suite baseline executed 472 tests with one unrelated existing
front-matter expectation failure and two skips. It was not repeated because
some legacy tests discover configured real data paths, contrary to the
requirement to keep verification isolated from owner data.

## Required tasks

### Important

1. **Restart LifePIM** using the updated `src\RUN_DESKTOP.BAT`, then verify only
   `127.0.0.1:9741` listens. The currently running process predates these code
   changes.
2. **Remove legacy firewall rules from an elevated PowerShell:**
   `powershell -ExecutionPolicy Bypass -File scripts\prod\allow_lifepim_caddy_firewall.ps1`.
3. **Test from a second device** that the desktop LAN IP is unreachable on
   ports 9741, 80 and 443. Confirm no scheduled task/service restarts Caddy.
4. **Add central SSRF protection** for all user-URL fetchers: resolve and reject
   non-public IP ranges, revalidate every redirect, pin the validated address
   where practical, and intercept Playwright subresource requests.
5. **Create and prove a recovery set** using `doc/user_guide_backup.md`: offline
   restore, `PRAGMA integrity_check`, representative note/attachment opens and
   recorded restore revision/date.
6. Keep `LIFEPIM_ENABLE_PUBLIC_NOTES`, `LIFEPIM_ENABLE_POCKET_API` and
   `LIFEPIM_ENABLE_LOGGER_API` unset/false.

### Optional defence in depth

1. Move inline JavaScript/styles to static assets and replace CSP
   `'unsafe-inline'` with nonces or hashes.
2. Validate login `next` targets as same-origin; shorten/rotate trusted-device
   credentials and add a password-quality check.
3. Add decompressed-size/complexity limits for XLSX and make bulk imports
   atomic; add CSV formula neutralization to every spreadsheet export.
4. Add Windows junction/symlink containment tests for each file-serving root.
5. Generate a hash-locked requirements file and software bill of materials for
   releases; schedule `pip-audit` and vendored-JavaScript review.
6. Remove legacy Pocket/logger/public code entirely if it will never be used.

## Change summary

Security-sensitive changes span startup/deployment (`src/RUN_DESKTOP.BAT`,
`src/run_waitress.py`, `src/app.py`, production scripts), central request
security (`src/core/security.py`), rendering/imports (`markdown_utils.py`,
`importer.py`, calendar limits, SVG/Mermaid handling), mutating routes and their
templates, dependencies, tests, and the deployment/network/backup documents.
Use `git diff --stat` and `git diff` for the authoritative file-by-file patch.
