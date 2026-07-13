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

Keep Waitress bound to `127.0.0.1` when using an HTTPS reverse proxy on the same machine.

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

## Using https instead of HTTP

Set the machine you are running LifePIM desktop on to a fixed IP address

```text
192.168.1.99
```

Download Caddy from https://caddyserver.com/download

copy the download to C:\apps\caddy

create "Caddyfile" with content below

```text
https://192.168.1.99 {
    reverse_proxy 127.0.0.1:9741
}
```

Start the caddy service (also put this line into the startup BAT file)

```text
C:\apps\caddy> .\caddy_windows_amd64.exe start
```


Then browse from any PC on network or mobile on Wifi

```text
https://192.168.1.99
```

Note that you still get a warning about untrusted certificates, because the browser cant prove where certificate came from


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
