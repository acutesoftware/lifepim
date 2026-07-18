# LifePIM Networking

LifePIM Desktop is a standalone local-first desktop application. It does not
need LifePIM Pocket, LifePIM.com, or any cloud service to run.

When LifePIM Pocket is used, it is a LAN mobile companion. Desktop production
traffic is LAN-reachable only through Caddy HTTPS. Waitress binds to loopback
and must not be exposed directly to another device.

## Production Listeners

Expected listeners:

```text
127.0.0.1:9741       Waitress
192.168.1.99:80      Caddy HTTP redirect, if retained
192.168.1.99:443     Caddy HTTPS
```

Check them with:

```powershell
Get-NetTCPConnection -LocalPort 80,443,9741 -State Listen |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

From another LAN machine, this must be unreachable:

```text
http://192.168.1.99:9741
```

## Caddy

Install Caddy at:

```text
C:\apps\caddy\caddy_windows_amd64.exe
```

Use this `C:\apps\caddy\Caddyfile`:

```caddy
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

Do not expose the Pocket API on HTTP. The mobile base URL is:

```text
https://192.168.1.99
```

Release Pocket builds reject non-HTTPS server URLs except for tightly scoped
development cases. If a saved Pocket URL is exactly `http://192.168.1.99`, the
mobile app migrates it to `https://192.168.1.99`. Do not configure Pocket to use
`http://192.168.1.99`, `http://192.168.1.99:9741`, or another direct Waitress
URL for normal LAN use.

Validate Caddy before starting LifePIM:

```powershell
cd C:\apps\caddy
.\caddy_windows_amd64.exe validate --config Caddyfile
.\caddy_windows_amd64.exe start --config Caddyfile
```

`src\RUN_DESKTOP.BAT` performs this validation in production. If Caddy is missing, invalid, or cannot start, production startup stops instead of falling back to direct HTTP.

The Caddy data directory on this installation is:

```text
C:\Users\xblad\AppData\Roaming\Caddy
```

The local CA is stored under:

```text
C:\Users\xblad\AppData\Roaming\Caddy\pki\authorities\local
```

This directory is persistent desktop application data, not a cache. Back it up with LifePIM Desktop. If `root.crt` or `root.key` is lost, Caddy may generate a new local CA and LifePIM Pocket must be rebuilt with the new public root certificate.

## Waitress

Production defaults:

```bat
set "LIFEPIM_ENV=production"
set "LIFEPIM_HOST=127.0.0.1"
set "LIFEPIM_PORT=9741"
```

Manual run:

```powershell
cd D:\DATA_LLM\dev\lifepim-desktop\src
$env:LIFEPIM_HOST = "127.0.0.1"
$env:LIFEPIM_PORT = "9741"
..\.venv\Scripts\python.exe run_waitress.py
```

Flask uses `ProxyFix` for one proxy layer. This is safe only because Waitress is loopback-only and Caddy is the sole proxy. Caddy must overwrite forwarded headers as shown above; forwarded headers from direct external clients are not trusted.

## Windows Firewall

Use the Private network profile only. Allow inbound LAN traffic to ports 80 and 443 only; optionally restrict remote addresses to `192.168.1.0/24`.

```powershell
New-NetFirewallRule -DisplayName "LifePIM HTTP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80 -Profile Private -RemoteAddress 192.168.1.0/24
New-NetFirewallRule -DisplayName "LifePIM HTTPS" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 443 -Profile Private -RemoteAddress 192.168.1.0/24
```

Remove any old Waitress firewall rule:

```powershell
Remove-NetFirewallRule -DisplayName "LifePIM Waitress"
```

Do not create an inbound firewall rule for port 9741.

## Android Certificate Trust

Caddy local HTTPS uses Caddy's local CA. LifePIM Pocket trusts the public root certificate inside the app using Android Network Security Configuration. Do not install the certificate into Android's system trust store.

Actual Caddy local CA path on this installation:

```text
C:\Users\xblad\AppData\Roaming\Caddy\pki\authorities\local\root.crt
```

Export only the public root certificate for Pocket builds:

```powershell
cd D:\DATA_LLM\dev\lifepim-mobile
.\scripts\export_lifepim_caddy_root.ps1
```

The public root certificate is safe to include in the APK. The private CA key remains at `C:\Users\xblad\AppData\Roaming\Caddy\pki\authorities\local\root.key`; never copy it to Android and never commit it to Git.

Do not disable TLS certificate validation in the Android client. Do not use a trust-all hostname verifier, custom trust-all `X509TrustManager`, or SSL context.

## Pocket Registration

Pocket devices can log in with a LifePIM Desktop username and password over LAN HTTPS. The password is verified once and exchanged for a revocable Pocket bearer token bound to that user. Sync requests then send only:

```text
Authorization: Bearer <device_token>
X-LifePIM-Device-ID: <device_id>
```

The older pairing-code flow remains available:

1. A logged-in desktop user starts Pocket pairing.
2. LifePIM creates a random one-time pairing code.
3. The code expires after five minutes and can be used once.
4. The mobile app submits the pairing code, username, and device details.
5. The desktop resolves the user from the pairing record and returns a bearer token.

Failed and successful registration attempts are recorded in `pocket_registration_attempts`. Repeated failures by IP, username, pairing code, or device ID are temporarily rate-limited.

Only token hashes are stored in `pocket_devices`; raw bearer tokens are never stored.

## Pocket Sync Protocol

Pocket sync is an optional companion workflow. Desktop stays usable on its own
when no mobile device is paired.

The mobile app now exposes two separate LAN sync actions:

- `Sync Mobile to LAN Server`
- `Sync from LAN Server`

The old combined mobile sync behavior may still exist internally in Pocket, but
the user-facing flow is intentionally split so upload and download are explicit.

Desktop exposes these Pocket API endpoints:

- `GET /api/pocket/v1/health`
- `POST /api/pocket/v1/auth/register-device`
- `POST /api/pocket/v1/auth/logout-device`
- `GET /api/pocket/v1/sync/manifest`
- `GET /api/pocket/v1/items/<item_id>`
- `POST /api/pocket/v1/sync/push`

All sync endpoints except health require:

```text
Authorization: Bearer <device_token>
X-LifePIM-Device-ID: <device_id>
```

Pocket follows redirects only when they remain HTTPS on the same host and
effective port, with a maximum of three redirects. Bearer tokens and device IDs
must not be forwarded to a different scheme, host, or port.

### Sync Mobile to LAN Server

This is a one-way upload from Pocket to Desktop.

The mobile upload flow is:

1. Confirm Pocket has a saved Desktop token and device ID.
2. Read the Desktop manifest from `/api/pocket/v1/sync/manifest`.
3. Compare local markdown records with Desktop records by `relative_path`,
   `server_item_id`, `base_version`, and content hash where available.
4. Upload changed local records to `/api/pocket/v1/sync/push`.
5. Include `server_item_id` and `base_version` when updating an existing
   Desktop item.
6. Mark accepted uploads using the Desktop response values: `server_item_id`,
   `version`, and `sha256`.

The upload action does not download Desktop changes back to Pocket.

Desktop accepts supported note pushes for the paired user. Existing notes are
updated when the server item ID, client item map, or same mobile filename can be
matched. Mobile-only notes can be created in the user's configured Pocket
default note folder, or in the user's existing note area when no default is set.

When Desktop detects that a note changed on both sides, it returns a conflict
instead of overwriting Desktop content unless the mobile payload has a
comparable modified time that is strictly newer than Desktop's file time.

### Sync from LAN Server

This is a one-way download from Desktop to Pocket.

The mobile download flow is:

1. Confirm Pocket has a saved Desktop token and device ID.
2. Read the Desktop manifest from `/api/pocket/v1/sync/manifest`.
3. Download needed item content from `/api/pocket/v1/items/<item_id>`.
4. Save downloaded records into Pocket's local folders.
5. Mark downloaded records as synced using the server item ID, version, and
   hash.

The download action does not upload local Pocket changes back to Desktop.

### Duplicate and Conflict Expectations

Pocket compares same-path records before upload. If a Desktop manifest item has
the same `relative_path`:

- Matching hashes are marked synced and skipped.
- Different hashes are uploaded only when Pocket can determine the mobile file
  is strictly newer than Desktop.
- If Desktop is newer, equal, or the timestamps cannot be compared safely,
  Pocket skips the overwrite or records a conflict rather than creating a
  normal duplicate.

Desktop also avoids duplicate creation for repeated mobile-only pushes by
remembering the mobile client item ID and by matching the same mobile filename
for the paired user.

This prevents new ordinary duplicates for the same path, such as repeated
uploads of `Notes/List of Fav Movies.md`. It does not automatically clean up
older duplicates that already have different filenames, such as
`Notes/List of Fav Movies (2).md`.

Pocket conflict files are intentionally not merged automatically. Review them
manually before deleting either side.

## Device Administration

Open:

```text
/admin/trusted-devices
```

The Mobile devices table shows device name, platform, username, user ID, creation time, last-seen time, last IP, user agent, and revoked status. Revoking a mobile device immediately invalidates its bearer token.

## Validation

Verify:

```text
http://192.168.1.99              redirects to HTTPS
https://192.168.1.99/api/pocket/v1/health works after Android trusts the local CA
http://192.168.1.99:9741         is unreachable from another LAN machine
```

Also verify a device cannot register with only a known username, and a paired device can sync only notes owned by its bound LifePIM user.
