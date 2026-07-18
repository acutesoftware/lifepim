# LifePIM Production Deployment

These notes describe how to run the secured Flask/SQLite version of LifePIM from:

```text
C:\apps\LifePIM_Prod
```

## What Runs Where

- Flask app entry point: `src\app.py`
- Production WSGI entry point: `src\run_waitress.py`
- Production launcher: `src\RUN_DESKTOP.BAT`
- Expected virtual environment: `.venv\Scripts\python.exe` under the LifePIM root.

LifePIM Desktop is a standalone local-first tool. LifePIM Pocket is optional:
when installed, it acts as a mobile companion over the LAN through Desktop's
Pocket API and Caddy HTTPS. Do not treat Pocket as a required service for
Desktop startup.

`RUN_DESKTOP.BAT` works from either:

```text
C:\apps\LifePIM_Prod\RUN_DESKTOP.BAT
C:\apps\LifePIM_Prod\src\RUN_DESKTOP.BAT
```

It starts Waitress, not Flask's development server.

## One-Time Setup

Install dependencies in the production virtual environment:

```bat
cd /d C:\apps\LifePIM_Prod
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Set a persistent secret key:

```bat
setx LIFEPIM_SECRET_KEY "replace-this-with-a-long-random-secret"
```

Close and reopen the command prompt after `setx`, then confirm:

```bat
echo %LIFEPIM_SECRET_KEY%
```

The secret key is required because Flask signs login sessions and CSRF tokens with it. If it changes, existing browser sessions and trusted-device logins stop working. Do not commit it to source control.

## First Administrator

Create the admin username and a password 

```bat
cd /d C:\apps\LifePIM_Prod
.venv\Scripts\python.exe scripts\create_admin.py
```

That creates the first admin user and assigns existing unowned notes/media to that user.

## Starting LifePIM

Run:

```bat
C:\apps\LifePIM_Prod\src\RUN_DESKTOP.BAT
```

Default listener:

```text
http://127.0.0.1:9741
```

The launcher sets:

```text
LIFEPIM_ENV=production
LIFEPIM_HOST=127.0.0.1
LIFEPIM_PORT=9741
```

You can override host/port before starting:

```bat
set LIFEPIM_HOST=127.0.0.1
set LIFEPIM_PORT=9741
src\RUN_DESKTOP.BAT
```

Do not use `0.0.0.0` or the fixed LAN IP in production. Pocket reaches LifePIM through Caddy on HTTPS.

For normal LAN/mobile use, the reachable URL is:

```text
https://192.168.1.99
```

The direct Waitress URL remains local-only:

```text
http://127.0.0.1:9741
```

## User and Device Administration

Log in as the admin user, then open:

```text
/admin
/admin/users
/admin/trusted-devices
```

In the UI:

```text
Top-left menu -> Users
Top-left menu -> Trusted devices
Admin -> Security -> Manage users
Admin -> Security -> Manage trusted devices
```

Available actions:

- Create users: `/admin/users/new`
- Edit/disable users: `/admin/users/<id>/edit`
- Reset passwords: `/admin/users/<id>/reset-password`
- Revoke one trusted device: `/admin/trusted-devices`
- Revoke all devices for a user: `/admin/trusted-devices`

## Per-User Markdown Roots

The database already scopes private note rows by user. Production also keeps
new users' markdown note files under separate per-user roots.

Existing `duncan` paths are intentionally preserved. On migration, legacy
project-folder rows are claimed for `duncan` rather than rewritten to
`lan_users\duncan`, so the current production note folders keep working.

New users default to:

```text
N:\duncan\LifePIM_Data\DATA\lan_users\<username>
```

LifePIM creates `notes`, `projects`, and `lists` under that root. Project
default folders for new users are created inside their `notes` root. Media and
audio paths remain global.

## Using https instead of HTTP

Set the machine you are running LifePIM desktop on to a fixed IP address

```text
192.168.1.99
```

Download Caddy from https://caddyserver.com/download

copy the download to C:\apps\caddy

create "Caddyfile" with content below

```text
http://192.168.1.99 {
    redir https://192.168.1.99{uri} permanent
}

https://192.168.1.99 {
    request_body {
        max_size 10MB
    }

    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy no-referrer
        Permissions-Policy "camera=(), microphone=(), geolocation=()"
    }

    reverse_proxy 127.0.0.1:9741 {
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
        header_up X-Forwarded-Host {host}
    }
}
```

HTTP redirects to HTTPS. Pocket must use `https://192.168.1.99`; do not expose the Pocket API on cleartext HTTP.

LifePIM Pocket release builds require HTTPS for Desktop sync. They trust the
bundled public Caddy local root certificate for `192.168.1.99` and normal
system CAs for unrelated HTTPS. Do not disable Android certificate validation
or hostname verification to make local sync work.

Start the caddy service (also put this line into the startup BAT file)

```text
C:\apps\caddy> .\caddy_windows_amd64.exe start
```


Then browse from any PC on network or mobile on Wifi

```text
https://192.168.1.99
```

Note that you still get a warning about untrusted certificates, because the browser cant prove where certificate came from

LifePIM Pocket does not use Android's system CA store for this local CA. It trusts the bundled public Caddy root certificate inside the Pocket app only.

On this installation, Caddy stores its persistent local CA at:

```text
C:\Users\xblad\AppData\Roaming\Caddy\pki\authorities\local
```

Back up the whole Caddy data directory with LifePIM Desktop:

```text
C:\Users\xblad\AppData\Roaming\Caddy
```

`root.crt` is the public root certificate and may be copied into the Pocket Android project. `root.key` is the private CA key; keep it on the Desktop machine, include it only in private Desktop backups, and never commit it to Git. If this CA is lost or regenerated, existing Pocket builds will no longer trust Desktop and Pocket must be rebuilt with the new public root certificate.


## Pocket Companion Sync

Pocket sync is optional and explicit. Desktop can be used normally without a
paired phone. When a phone is paired, Pocket has two separate sync directions:

- `Sync Mobile to LAN Server`: uploads local Pocket changes to Desktop through
  `/api/pocket/v1/sync/push`.
- `Sync from LAN Server`: reads Desktop's manifest from
  `/api/pocket/v1/sync/manifest` and downloads item content from
  `/api/pocket/v1/items/<item_id>`.

Device setup:

1. Start Desktop in production behind Caddy.
2. Log in as the Desktop user who should own the paired mobile data.
3. Open `/admin/trusted-devices`.
4. Create a Pocket pairing code.
5. In Pocket, use `https://192.168.1.99` as the server URL and enter the pairing
   code.

After pairing, Pocket sends a bearer token and `X-LifePIM-Device-ID` on sync
requests. Desktop stores only token hashes, binds each device to a Desktop user,
and rejects revoked devices.

The current Desktop Pocket API is primarily note-focused. Pocket may store
notes, lists, media, and its own sync metadata locally, but Desktop's documented
LAN API support here is the manifest/item/push flow implemented under
`/api/pocket/v1`.

Duplicate handling is path- and identity-based. Pocket compares its local files
with Desktop's manifest before upload and should skip same-path uploads unless
the mobile copy is clearly newer. Desktop also maps mobile client item IDs and
same mobile filenames so repeated mobile-only pushes update the same Desktop
note instead of creating new copies. Existing older duplicates with different
filenames are not cleaned up automatically.

## Secure Cookies and Local HTTP

In production, LifePIM uses secure cookies. Secure cookies are only sent over HTTPS by browsers.

That means:

- `python app.py` is acceptable for local development checks.
- `http://127.0.0.1:9741` may work for local testing.
- Normal family/LAN use should be through HTTPS.
- If you run production over plain HTTP from another device, login/trusted-device behavior may fail or be unsafe.

For temporary local development only:

```bat
set LIFEPIM_ENV=development
set LIFEPIM_ALLOW_INSECURE_COOKIES=1
python app.py
```

Do not use that mode for the normal LAN deployment.

## Database and Migration Notes

The app creates/updates the security schema at startup:

- `users`
- `auth_trusted_devices`
- `auth_login_attempts`
- note visibility fields on `lp_notes`
- media visibility fields on `lp_media`

The visibility fields are:

```text
owner_user_id
visibility
show_in_blog
is_public
```

SQLite settings used by the app:

```text
PRAGMA foreign_keys = ON
PRAGMA busy_timeout = 5000
PRAGMA journal_mode = WAL
```

## Public Routes

Public unauthenticated content is only under:

```text
/public
/public/blog
/public/notes/<id>
/public/media/<id>
```

Only records with `is_public = 1` are exposed there. `show_in_blog = 1` alone does not make a record public.

## Do Not Rebuild Production DB Accidentally

This command is destructive:

```bat
cd src
..\.venv\Scripts\python.exe init_database.py
```

It deletes and recreates the configured SQLite database. Do not run it against production data unless you intend to rebuild the DB.

## Operational Checks

Allow inbound LAN traffic to the LifePIM/Caddy ports from an elevated PowerShell prompt:

```powershell
New-NetFirewallRule -DisplayName "LifePIM HTTP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80 -Profile Private -RemoteAddress 192.168.1.0/24
New-NetFirewallRule -DisplayName "LifePIM HTTPS" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 443 -Profile Private -RemoteAddress 192.168.1.0/24
Remove-NetFirewallRule -DisplayName "LifePIM Waitress"
```

Check app imports:

```bat
cd /d C:\apps\LifePIM_Prod
.venv\Scripts\python.exe -m py_compile src\app.py
```

Check configured DB:

```bat
cd /d C:\apps\LifePIM_Prod\src
..\.venv\Scripts\python.exe -c "from common import config; print(config.DB_FILE)"
```

Check users:

```bat
cd /d C:\apps\LifePIM_Prod\src
..\.venv\Scripts\python.exe -c "from common import data; print(data._get_conn().execute('select username, role, is_active from users').fetchall())"
```

## Current Gaps

- Notes and media have central permission checks, but not every other content type has ownership/visibility enforcement yet.
- Visibility controls are not yet fully exposed on all edit screens.
- HTTPS is not built into the Flask app; it must be provided by a reverse proxy.
