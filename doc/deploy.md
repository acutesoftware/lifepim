# LifePIM Desktop deployment

This deployment is for one trusted owner on one Windows desktop. LifePIM is not
a LAN service, public website or multi-user security boundary.

## Install

From the repository root:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

Chromium is needed only for rendered web clipping and browser-based PDF
features. The rest of LifePIM continues to work if the browser install is
omitted; those features report an error.

Set a persistent random Flask secret, then reopen the terminal:

```bat
setx LIFEPIM_SECRET_KEY "replace-with-a-long-random-value"
```

The secret signs login sessions and CSRF tokens. Keep it out of Git and include
it in the private recovery record. Changing it safely invalidates existing
sessions.

Create the initial owner account if required:

```bat
.venv\Scripts\python.exe scripts\create_admin.py
```

## Start

Run:

```bat
src\RUN_DESKTOP.BAT
```

Then browse to `http://127.0.0.1:9741`. The launcher sets production mode,
binds Waitress to loopback, does not start Caddy, and refuses a non-loopback
`LIFEPIM_HOST`. Debug and the Flask reloader are disabled.

Optional overrides are limited to a different port or loopback spelling:

```bat
set LIFEPIM_HOST=127.0.0.1
set LIFEPIM_PORT=9741
src\RUN_DESKTOP.BAT
```

Do not use `0.0.0.0`, a LAN address, a reverse proxy, port forwarding or a
public tunnel. See `doc/network.md` for listener verification.

## Feature flags

Public note routes, Pocket/mobile endpoints and logger API endpoints default to
disabled. Their opt-in environment variables are retained only for legacy
compatibility and are outside the supported security model. Do not enable them
for this deployment.

## Updates and checks

After updating source:

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m compileall -q src tests
.venv\Scripts\python.exe -m unittest tests.test_local_security tests.test_caddy_lan_hosts
```

`src\DEPLOY_PROD.BAT` uses the local `/login` page as its readiness check. It no
longer relies on a disabled mobile API.

## Data safety

Do not run `src\init_database.py` against a live data directory unless a full
rebuild is intended. Back up and test restore according to
`doc/user_guide_backup.md` before application or schema upgrades.
