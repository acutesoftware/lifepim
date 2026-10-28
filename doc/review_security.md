# LifePIM Desktop security review

Review date: 2026-10-28 (Australia/Adelaide)  
Repository reviewed: `lifepim-desktop`, commit `70aa4a5`  
Overall result: **not ready for multi-user LAN exposure until the Important tasks below are completed**.

## Executive summary

LifePIM has a sound base in several areas: production Waitress is bound to loopback, Caddy provides LAN TLS, passwords use Argon2, CSRF protection is enabled for browser routes, Pocket tokens are stored as hashes, SQL values are generally parameterised, and the reviewed upload/path helpers often use containment checks.

The principal risk is that the application's trust model does not match its LAN deployment. Caddy exposes the whole authenticated UI to the LAN, but any authenticated role (including `guest`) can create and run shell commands, browse host paths, configure/read SQLite sources, and invoke desktop file openers. Imported and synchronised Markdown is also rendered with raw HTML and inserted using Jinja `|safe`, producing stored cross-site scripting (XSS). An XSS payload can act as the signed-in user and makes the command runner especially dangerous.

The audit found the following confirmed priority issues:

| ID | Severity | Finding |
|---|---:|---|
| SEC-01 | Critical | Stored XSS through raw Markdown/HTML and same-origin SVG/preview rendering |
| SEC-02 | Critical | Host command execution is available to every authenticated role; `shell=True` is used |
| SEC-03 | High | Server-side request forgery (SSRF) in webpage clipping and place URL metadata |
| SEC-04 | High | Multi-user authorisation is incomplete; some datasets are shared and Pocket exposes unowned legacy notes to every paired user |
| SEC-05 | High | Authenticated users can enumerate arbitrary host folders and catalogue arbitrary readable SQLite files |
| SEC-06 | High | Installed runtime contains known vulnerable image/network packages; Pillow is directly exposed to imported remote images |
| SEC-07 | Medium | State-changing operations use GET, bypassing meaningful CSRF protection |
| SEC-08 | Medium | Importers permit resource exhaustion, partial imports, unsafe active content, and inconsistent ownership |
| SEC-09 | Medium | Authentication hardening gaps: open redirect, no password policy, and long-lived non-rotating trusted-device tokens |
| SEC-10 | Medium | Browser security and supply-chain controls are incomplete (no CSP, runtime CDN module, no locked transitive dependencies) |

The application should be treated as a **single trusted-user application** until SEC-01 through SEC-06 are fixed. Folder ACLs alone do not solve this: the web process reads files under one Windows account, so every app user currently inherits that process account's effective access through the exposed features.

## Scope and method

The review covered all tracked Python, JavaScript, Jinja/HTML, SQL, PowerShell, batch, configuration, dependency, deployment, and test code under `src/`, `scripts/`, `tests/`, and the repository root. Generated data, image assets, the virtual environment's source, and external Caddy/Python implementations were not source-audited. Existing user folders were assumed to have appropriate operating-system ACLs as requested.

Checks performed:

- Manual review of authentication, authorisation, CSRF, session/cookie handling, file serving, process execution, SQL construction, inbound APIs, outbound HTTP, imports, uploads, archive handling, and deployment scripts.
- Route inventory and targeted searches for command execution, unsafe rendering, dynamic SQL, redirects, file reads/writes, network access, secrets, and deserialisation.
- Bandit 1.9.4 over `src/` and `scripts/`: 47,312 lines, 2 High, 277 Medium, and 141 Low heuristic findings. The two High findings are the two `shell=True` calls in SEC-02. Most dynamic-SQL warnings use internal or allow-listed identifiers and were not confirmed as injectable.
- OSV vulnerability query for every package installed in `.venv`, plus `pip list --outdated` against PyPI on 2026-10-28.
- `pip check`: no broken installed package metadata.
- Unit suite: 472 tests ran; 469 passed, 1 failed, and 2 skipped. The failure was `test_push_updates_existing_note_accepts_project_front_matter` (`area/front-matter` unexpectedly became `pers`).
- Live listener/config check: Waitress was on `127.0.0.1:9741`; Caddy was on ports 80/443; direct LAN access to `192.168.1.104:9741` failed; Caddy health access succeeded.

This was a source/configuration audit, not a destructive penetration test. It did not fuzz every parser, attempt password cracking, or exploit the live personal database.

## Detailed findings

### SEC-01 — Critical — stored XSS through rendered content

Evidence:

- `src/utils/markdown_utils.py:335-345` defaults `allow_html=True` and passes content to Python-Markdown without sanitisation.
- Note, notebook, card, preview, pop-out, and public-note templates render this output using `|safe`, including `src/modules/public/templates/public_note.html:12`.
- Browser preview code assigns returned HTML to `innerHTML` (`src/static/note_editor.js:569` and `src/static/note_popout.js:93`).
- Note uploads allow `.svg` and serve attachments from the LifePIM origin without a sandbox (`src/modules/notes/routes.py:123` and `:2987`).
- Content can arrive from CSV/folder imports, Pocket sync, webpage clipping, or ordinary editing. A public note makes the payload reachable without login; a signed-in browser still sends its LifePIM cookies to the same origin.

Impact: arbitrary JavaScript in the LifePIM origin can read displayed private data, obtain CSRF tokens, modify records, and invoke privileged application features. Combined with SEC-02, stored XSS can become host command execution.

Required fix:

1. Sanitize generated HTML with an allow-list sanitizer such as Bleach, including strict URI-scheme and attribute rules. Default to escaped HTML for imported/mobile/web content.
2. Remove `|safe` except for a single audited sanitized-HTML type/path.
3. Serve SVG and archived HTML as downloads or from an isolated origin; alternatively reject SVG uploads. Add `X-Content-Type-Options: nosniff` at the Flask layer too.
4. Add regression tests using `<script>`, event handlers, `javascript:` links, malicious SVG, malformed tags, and public/shared notes.

### SEC-02 — Critical — command execution is not privileged

Evidence:

- `/apps/launch/*` and `/apps/action/*` are protected only by global login, not an admin/capability check (`src/modules/apps/routes.py:348-465`).
- Any authenticated user can create an app/action and choose `COMMAND`.
- `src/modules/apps/schema.py:1534` and `:1581` concatenate target/arguments and invoke `subprocess.Popen(..., shell=True)`.
- The separate Tasks run feature can trigger stored app actions. The `agent_allowed` and `requires_confirmation` fields do not form a server-side authorisation boundary for manual routes.

Impact: any authenticated user, compromised account, or stored-XSS payload can execute commands with the full Windows identity of LifePIM, bypassing per-user folder assumptions.

Required fix:

- Restrict app creation/edit/run, task action execution, path openers, and run-log access to an explicit `host_operator`/admin capability. Do not grant it to `user` or `guest` by default.
- Remove `shell=True`. Store executable and argument arrays separately and invoke with `shell=False`. If shell scripts are an essential feature, make them pre-registered, admin-owned, immutable to ordinary users, and require re-authentication/confirmation.
- Enforce owner checks on actions and run logs and record an immutable audit event for each launch.

### SEC-03 — High — SSRF in user-supplied URLs

Evidence:

- `src/modules/notes/web_clip.py:48-91` accepts any HTTP(S) hostname and follows redirects. It does not reject loopback, private, link-local, multicast, or cloud-metadata addresses, nor revalidate every redirect target.
- Rendered/archive modes pass the URL to Playwright, giving browser-capable access to internal services.
- `src/modules/places/routes.py:287-331` performs the same kind of unrestricted server-side URL lookup.

Impact: an authenticated LAN user can probe or read services reachable from the desktop (routers, NAS admin panels, loopback services, and cloud metadata if applicable). Response content can then be persisted as a note.

Required fix: resolve DNS, reject all non-public IP ranges (IPv4 and IPv6), pin the resolved address for the connection, re-check every redirect, reject credentials and unusual ports unless explicitly allowed, limit redirects/content types, and apply the same policy to Playwright subresources or remove rendered fetching. Consider a dedicated outbound proxy with an allow-list.

### SEC-04 — High — incomplete object and tenant authorisation

Evidence:

- Notes, projects, areas, collections, and portions of media/apps have owner-aware code, but contacts, places, money, audio, files, calendar projections, and several supporting tables are shared across all authenticated users.
- `core/security.py:543-546` maps only user/security management to admin; other sensitive permissions reduce to “logged in”.
- `src/modules/pocket_api/routes.py:545-558` intentionally selects `(owner_user_id = ? OR owner_user_id IS NULL/empty/0)`. Therefore every paired user can receive all unowned legacy notes.
- `can_view_record()` treats all media as visible to any authenticated user (`src/core/security.py:613-614`), regardless of owner/visibility.

Impact: one LifePIM user can view or alter another user's records, or receive legacy notes through Pocket. This contradicts the presence of user/guest roles and per-user paths.

Required fix: define a written access-control matrix for every domain and operation, add `owner_user_id` consistently, enforce it in every SELECT/UPDATE/DELETE and file-serving route, and migrate unowned rows to one explicit owner. Do not use “unowned means visible to every Pocket user.” Add two-user negative tests for every route and API object.

### SEC-05 — High — arbitrary filesystem and SQLite discovery

Evidence:

- `/files/tree` and `/files/list` accept arbitrary `drive`, `base`, and `dir` values. `_safe_join()` at `src/modules/files/routes.py:112` normalises but does not enforce containment; `base` itself is client-controlled.
- File records can be added/edited/deleted by any authenticated user and have no owner enforcement.
- Data-source routes let any authenticated user register and scan arbitrary folder paths/SQLite databases. SQLite preview is correctly opened read-only, but its contents and schema can still be disclosed.

Impact: users can enumerate paths readable by the LifePIM process and read any readable SQLite database through the catalogue. SEC-02 provides an even broader read path.

Required fix: admin/capability-gate these features, use configured per-user roots rather than client-supplied absolute bases, resolve symlinks/reparse points, enforce `commonpath()` containment, and deny UNC/device paths unless deliberately configured.

### SEC-06 — High — vulnerable installed dependencies

OSV reported the following runtime vulnerabilities in the reviewed `.venv`:

| Package installed | Required/fixed version | Relevance |
|---|---:|---|
| Pillow 12.2.0 | **13.0.0** | Numerous 2026 image-parser memory-safety/DoS issues, including an FPX heap overflow and Ghostscript argument injection. LifePIM decodes remote/imported images. Current requirement `Pillow>=11,<13` prevents the complete fix. |
| Werkzeug 3.1.6 | **3.1.9** | Windows special-device-name issue in `safe_join`. `requirements.txt` already pins 3.1.9, but the live venv is stale. |
| urllib3 2.7.0 | **2.8.0** | HTTPS proxy configuration bypass plus response-stream memory/CPU DoS advisories; used through Requests/web clipping. |
| certifi 2026.6.17 | **2026.10.19 or later** | Bundled compromised emSign intermediate trust material. |
| soupsieve 2.8.4 | **2.9.0** | Two polynomial ReDoS issues; transitive content-processing dependency. |

Representative advisories: [Pillow advisories](https://github.com/python-pillow/Pillow/security/advisories), [Werkzeug GHSA-g6x2-hccm-hh4m](https://github.com/advisories/GHSA-g6x2-hccm-hh4m), [urllib3 advisories](https://github.com/urllib3/urllib3/security/advisories), and [OSV](https://osv.dev/).

Required fix: change the Pillow constraint to permit/pin 13.0.0 after compatibility tests, rebuild the venv from a reviewed lock, and verify the resulting environment with `pip-audit`. Do not regard the current `pip check` success as a vulnerability check.

### SEC-07 — Medium — mutations through GET

Confirmed GET-capable state changes include app launch, app-action launch, logout/device revocation, and delete routes for 3D items, contacts/facts, files, goals, notes, places, and audio. Flask-WTF CSRF checks unsafe HTTP methods; a GET link/image/navigation can therefore trigger these actions without a CSRF token.

Required fix: make every mutation POST/PUT/PATCH/DELETE only, retain CSRF for browser calls, and add route tests asserting GET returns 405. Command launch must never be GET.

### SEC-08 — Medium — data import and upload weaknesses

Positive controls include random temporary upload names, temp-folder containment, parameterised row inserts, Pocket attachment size/extension checks, logger path validation, and single-member ZIP extraction without `extractall()`.

Remaining issues:

- Global request size is 100 MiB; CSV preview builds all rows in memory, CSV import has no row/field/count limit, ICS parsing reads the whole file and expands recurrence rules without an occurrence cap, and folder/database scans can traverse very large trees.
- Generic CSV imports commit per record through generic data helpers, so malformed input can leave partial imports. Contacts similarly update/insert row by row without an import transaction or dry-run rollback.
- Generic note/calendar imports do not consistently set `owner_user_id`, validation rules, or provenance. Unowned rows then behave inconsistently between web and Pocket access.
- Imported Markdown/HTML and SVG can carry active content (SEC-01). Image files are trusted mainly by extension; Pocket base64 attachments and note uploads are not decoded/verified before storage.
- Spreadsheet/CSV/SQLite imports trust complex third-party parsers. They must be treated as untrusted, particularly while Pillow and transitive packages are outdated.
- The test suite connected to and enumerated configured real databases and paths. This is unsuitable for CI and creates leakage/accidental-mutation risk.
- The current suite has one Pocket metadata regression: project front matter was overwritten by the derived `pers` area.

Required fix: add per-format byte/row/column/field/recurrence limits; stream previews; transact and roll back the whole import on error; enforce owner/provenance at ingestion; validate image magic and decode in a resource-limited worker; make duplicate policy explicit; and force tests to fail closed unless a temporary test database/root is configured.

### SEC-09 — Medium — authentication/session hardening

- `/login?next=...` is redirected without validating that it is a same-origin relative path (`src/modules/auth/routes.py:12-39`), enabling an open redirect after login.
- User creation, password changes, and admin resets accept any non-empty password; no minimum length or compromised-password guidance is enforced.
- Trusted-device cookies have a five-year browser lifetime and database rows normally have no `expires_at`; the token is not rotated on successful restoration. Cookie flags are otherwise good in production (`Secure`, `HttpOnly`, `SameSite=Lax`).
- Login rate limiting is database-backed but keyed by a proxy-derived IP and has no record cleanup shown; this can grow indefinitely and can cause shared-NAT lockouts.
- The logger shared token is stored in plaintext settings and compared with ordinary string comparison. Prefer per-device hashed tokens and `secrets.compare_digest()` where a shared secret remains.

Required fix: validate `next` locally, enforce a sensible password minimum (for example 12+ characters while permitting passphrases), shorten/expire and rotate trusted tokens, add login-attempt retention, and migrate logger authentication to revocable hashed per-device tokens.

### SEC-10 — Medium — browser and supply-chain hardening

- Caddy supplies `nosniff`, frame denial, referrer, and permissions headers, but no Content-Security-Policy or HSTS. Flask does not apply the headers when reached outside Caddy.
- `src/static/mermaid_render.js:21` imports Mermaid 12.0.0 at runtime from jsDelivr. This is a runtime availability/privacy/supply-chain dependency and prevents a strict offline CSP.
- `requirements.txt` pins many direct dependencies but leaves transitive dependencies unlocked and unhashed. Installed Werkzeug already drifted from the declared pin.
- `setup.py` is obsolete and contradictory: it declares old Flask, `nose`, `AIKIF`, Flask-HTTPAuth, and Flask-RESTful requirements and package names that do not describe the current application. `src/requirements.txt` is empty.
- No committed automated dependency/security scan was found.

Required fix: self-host a pinned Mermaid bundle, introduce a nonce/hash-based CSP after removing unsafe inline content, add HSTS on the LAN TLS endpoint if operationally appropriate, generate a hash-locked deployment file, remove/update obsolete packaging metadata, and run tests plus `pip-audit`/Bandit in CI.

## Dependency inventory

The deploy script installs the root `requirements.txt`. The table below lists every declared direct dependency and its purpose.

| Dependency | Declared version/range | Purpose and update assessment (2026-10-28) |
|---|---:|---|
| Flask | 3.1.3 | Web framework; current in checked index. |
| Werkzeug | 3.1.9 | Routing/request/file helpers; required security version, but installed venv is 3.1.6 and must be rebuilt. |
| Jinja2 | 3.1.6 | HTML templates; current. Unsafe output is caused by application `|safe` use, not Jinja escaping. |
| MarkupSafe | 3.0.3 | Template escaping; 3.0.4 available, optional update. |
| itsdangerous | 2.2.0 | Flask session signing; current. |
| click | 8.3.1 | Flask/CLI support; 8.5.0 available, routine update. |
| blinker | 1.9.0 | Flask signals; current. |
| colorama | 0.4.6 | Windows CLI colour support; current. |
| Flask-Login | 0.6.3 | Browser session authentication; current. |
| Flask-WTF | 1.2.2 | CSRF protection; 1.3.0 available, test then update. |
| argon2-cffi | 23.1.0 | Password hashing; 25.1.0 available, recommended update/rehash-on-login test. |
| waitress | 3.0.2 | Production WSGI server; current. |
| Markdown | 3.10 | Markdown conversion; 3.11.2 available. Updating does not sanitize raw HTML. |
| requests | >=2.32,<3 | Web clipping/school-term HTTP; installed 2.34.2. Lock it and urllib3/certifi. |
| trafilatura | >=2.2,<3 | Article extraction; installed 2.2.0, 2.3.1 available. |
| Pillow | >=11,<13 | Remote/imported image processing; **must move to 13.0.0** for current fixes. |
| pandas | 2.3.3 | CSV/Excel/data catalogue and scripts; 3.1.0 is a major update, optional after compatibility work. |
| numpy | 2.4.1 | pandas/numeric support; 2.5.4 available. |
| openpyxl | 3.1.5 | `.xlsx` import via pandas; current. |
| xlrd | 2.0.2 | legacy `.xls` import; current. |
| python-dateutil | 2.9.0.post0 | recurrence/date parsing; 3.0.0 major update available, defer until tested. |
| pytz | 2025.2 | timezone compatibility; 2026.5 available. Prefer standard `zoneinfo` over time. |
| tzdata | 2025.3 | Windows timezone database; 2026.6 available and recommended. |
| six | 1.17.0 | transitive/legacy compatibility; current, likely removable as a direct dependency. |

Optional browser rendering/PDF code imports Playwright, but Playwright is not declared. The reviewed venv happened to contain 1.62.0 (1.64.1 available). Either declare and lock it—including the browser binary—or disable those features with an explicit message. BeautifulSoup/lxml/soupsieve and other extraction packages arrive transitively through Trafilatura and should be present in the lock and vulnerability scan.

## Network, LAN, and API review

### Observed LAN state

At review time:

| Listener/test | Result |
|---|---|
| `127.0.0.1:9741` | Waitress, loopback only — correct. |
| LAN `:9741` | Connection failed — correct; no direct Waitress LAN exposure observed. |
| ports 80/443 | Caddy listening on all local address families; Windows firewall allows `LocalSubnet` on Private and Public profiles. |
| Caddy hosts | `192.168.1.99` and `192.168.1.104`; generated from fixed plus active private adapters. |
| HTTP Pocket health | Proxied directly over HTTP by design. Other HTTP paths redirect to HTTPS. |
| HTTPS | Reverse proxies the **entire LifePIM UI and both APIs**, not only Pocket. |

The loopback/ProxyFix architecture is correct only while Waitress remains loopback-only and Caddy overwrites forwarded headers. Add a startup assertion that production host is loopback, keep port 9741 out of the firewall, and consider limiting Caddy routes to Pocket/logger APIs if full desktop UI access from LAN is not required. The live generated Caddyfile also lacks the `request_body max_size 10MB` documented in `doc/network.md`; the effective Flask default is 100 MiB.

### Inbound APIs

| API | Why it exists | Authentication | Effect if unavailable |
|---|---|---|---|
| `/api/pocket/v1/health` | Pocket discovery/health | Public | Pocket cannot verify the desktop endpoint; desktop UI still works. |
| Pocket registration/login/pairing | Exchange desktop credentials or one-time pairing for a device token | Public endpoint with credential/code verification and rate limiting | New Pocket devices cannot pair/login; existing desktop use unaffected. |
| Pocket manifest/item/push/logout | Bidirectional note/mobile-file sync | Hashed bearer token plus device ID | Mobile sync stops; desktop data remains local. |
| `/api/logger/v1/status`, `/upload` | Receive logger JSON/JSONL files | Shared logger token or matching Pocket device token; feature can be disabled | Mobile logger ingestion stops; other LifePIM features continue. |
| Browser JSON APIs (`/links/api`, projects, notes, places, admin, money, etc.) | Same-origin UI interactions | Global login; unsafe methods normally CSRF-protected | The related UI action fails; core server remains available. |

The API logging deliberately records whether an Authorization header exists but not its value, which is good. Network logs do record paths, query strings, filenames/destinations, usernames, device IDs, IPs, and errors; treat `lp_network.log` and logger/admin logs as sensitive and add rotation/retention.

### Outbound/runtime calls

| Destination/call | Why it is needed | Effect if blocked or absent |
|---|---|---|
| Arbitrary HTTP(S), Requests/Playwright (`notes/web_clip.py`) | Webpage Notes extraction, images, rendered page/archive capture | Web clipping/render/archive fails; ordinary notes work. Must be SSRF-hardened. |
| Arbitrary HTTP(S), `places/routes.py` | Fetch a title for a user-entered virtual place URL | Title remains hostname/manual; places otherwise work. Must be SSRF-hardened. |
| `nominatim.openstreetmap.org` | Address geocoding/reverse geocoding | Automatic coordinates/address lookup fails; manual fields/local map remain. |
| `download.geofabrik.de` | Download Australian offline map GeoPackages | Offline street-map packs cannot be installed/refreshed; bundled Natural Earth map remains. |
| South Australia Department for Education | Import school-term dates | School-term preview/import fails; manual/calendar CSV/ICS remains. |
| `query1.finance.yahoo.com` | Refresh share/watchlist quotes | Prices stop refreshing; stored/manual finance data remains. |
| `cdn.jsdelivr.net` | Runtime Mermaid 12 browser module | Mermaid diagrams do not render. Self-host this dependency. |
| `raw.githubusercontent.com/nvkelso/...` (build script only) | Build/update bundled Natural Earth map JSON | Map-data rebuild fails; already committed map assets continue working. |
| User-configured URLs via `webbrowser.open` | Open app/place links in the desktop browser | Only the convenience launch fails. Validate schemes to HTTP(S). |

LifePIM otherwise remains local-first; no mandatory cloud API was found for startup or normal CRUD operation.

## SQL and secrets review

No committed live password, API key, bearer token, private key, or Flask secret was found in the tracked source search. Production correctly refuses to start without `LIFEPIM_SECRET_KEY`; development falls back to the known `dev-only-change-me` key and must never be LAN-exposed.

Most SQL values use placeholders. Dynamic table/column/order expressions are generally derived from static table definitions, explicit allow-lists, or generated placeholder counts. No confirmed unauthenticated SQL injection was found. This conclusion does not make the generic admin/data catalogue safe for ordinary users: those features intentionally expose broad database capabilities and need authorisation as described above.

## Prioritised security tasks

### Important — complete before multi-user LAN use

- [ ] Fix SEC-01: sanitize Markdown/HTML, isolate or reject SVG/HTML, remove unaudited `|safe`, add XSS tests.
- [ ] Fix SEC-02: capability-gate all host execution/open features and remove `shell=True`.
- [ ] Fix SEC-03: centralise SSRF-safe outbound fetching and apply it to Requests, urllib, redirects, images, and Playwright.
- [ ] Fix SEC-04/05: implement the access-control matrix, migrate unowned data, enforce owner/root containment, and add two-user denial tests.
- [ ] Upgrade/rebuild dependencies: Pillow 13.0.0, Werkzeug 3.1.9, urllib3 2.8.0, certifi >=2026.10.19, soupsieve >=2.9.0; run the full suite and `pip-audit` on the built environment.
- [ ] Convert every mutation/launch/logout/delete route to non-GET and require CSRF or API bearer authentication as appropriate.
- [ ] Put import limits, validation, ownership, provenance, and transaction rollback in a shared ingestion layer.
- [ ] Fix the failing Pocket front-matter/area test and isolate all tests from real configured databases and folders.
- [ ] Decide whether the desktop UI should be LAN-accessible. If not, restrict Caddy to the required Pocket/logger paths; keep Waitress loopback-only in all production launch modes.

### Optional/recommended hardening

- [ ] Add a nonce/hash CSP, HSTS where safe for the local CA workflow, Flask-layer security headers, and a strict allowed-host policy.
- [ ] Self-host pinned Mermaid; declare/lock Playwright or remove the optional paths.
- [ ] Generate hash-locked dependencies and add Bandit, `pip-audit`, secret scanning, and dependency update checks to CI.
- [ ] Enforce password length, safe local redirects, trusted-token expiry/rotation, logger token hashing, and auth-log retention.
- [ ] Reduce body/attachment defaults to feature-appropriate limits and align the live Caddy config with documentation.
- [ ] Rotate and retain network/audit logs; redact sensitive query/path values where they are not needed.
- [ ] Remove or modernise `setup.py`, the empty `src/requirements.txt`, legacy scripts, and unused direct dependencies to reduce supply-chain surface.
- [ ] Add backup/restore verification, database integrity checks, and documented incident recovery for device/token revocation.

## Final assessment

LifePIM is reasonably protected against unauthenticated direct access in its current loopback-plus-Caddy deployment, and its Pocket token/path handling contains several good defensive controls. The current authenticated boundary is nevertheless too broad: a low-privilege account or imported active-content payload can reach capabilities equivalent to the desktop user. After the Important tasks are completed, the remaining risks are conventional hardening and maintainability work rather than fundamental trust-boundary failures.
