# LifePIM Networking

This document describes the current LAN setup for LifePIM Desktop and LifePIM Pocket.

## Current Shape

LifePIM Desktop runs a local Waitress server on port `9741`.

Caddy sits in front of it on the LAN IP:

```text
192.168.1.99
```

The intended split is:

```text
https://192.168.1.99/*                  Desktop web app
http://192.168.1.99/api/pocket/v1/*     Pocket mobile API only
```

The Pocket HTTP exception exists because the first Android build permits cleartext HTTP only for `192.168.1.99`.

## Ports

```text
80     Caddy HTTP listener, Pocket API only plus desktop HTTP-to-HTTPS redirect
443    Caddy HTTPS listener for the desktop web app
9741   Waitress / Flask app
```

Waitress should bind to either:

```text
0.0.0.0
192.168.1.99
```

Do not bind Waitress to `127.0.0.1` only if Android or another LAN client needs to hit port `9741` directly. Caddy can still proxy to `127.0.0.1:9741`, but binding to `0.0.0.0` is simpler for local testing.

## Caddy Setup

Install Caddy at:

```text
C:\apps\caddy\caddy_windows_amd64.exe
```

Use this `C:\apps\caddy\Caddyfile`:

```caddy
http://192.168.1.99 {
    handle /api/pocket/v1/* {
        reverse_proxy 127.0.0.1:9741
    }

    handle {
        redir https://{host}{uri} permanent
    }
}

https://192.168.1.99 {
    reverse_proxy 127.0.0.1:9741
}
```

This means:

```text
http://192.168.1.99/api/pocket/v1/health  -> HTTP 200
http://192.168.1.99/notes                 -> redirects to https://192.168.1.99/notes
https://192.168.1.99/notes                -> desktop app
```

Validate and reload Caddy:

```powershell
cd C:\apps\caddy
.\caddy_windows_amd64.exe validate --config Caddyfile
.\caddy_windows_amd64.exe reload --config Caddyfile
```

Start Caddy if it is not already running:

```powershell
cd C:\apps\caddy
.\caddy_windows_amd64.exe start
```

## LifePIM Server

The production launcher is:

```text
src\RUN_DESKTOP.BAT
```

Default environment:

```bat
set LIFEPIM_ENV=production
set LIFEPIM_HOST=0.0.0.0
set LIFEPIM_PORT=9741
```

Manual start from the repo:

```powershell
cd D:\DATA_LLM\dev\lifepim-desktop\src
$env:LIFEPIM_HOST = "0.0.0.0"
$env:LIFEPIM_PORT = "9741"
..\.venv\Scripts\python.exe run_waitress.py
```

Check listeners:

```powershell
Get-NetTCPConnection -LocalPort 80,443,9741 -State Listen |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

Expected:

```text
80     Caddy
443    Caddy
9741   Waitress, ideally bound to 0.0.0.0
```

## Windows Firewall

Run from an elevated PowerShell prompt:

```powershell
New-NetFirewallRule -DisplayName "LifePIM HTTP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80
New-NetFirewallRule -DisplayName "LifePIM HTTPS" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 443
New-NetFirewallRule -DisplayName "LifePIM Waitress" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 9741
```

Check existing rules:

```powershell
Get-NetFirewallRule -DisplayName "LifePIM*" |
  Select-Object DisplayName,Enabled,Direction,Action
```

## Desktop Browser Use

Use HTTPS for the desktop web app:

```text
https://192.168.1.99
```

The browser may warn about the certificate because this is a local IP address with a local/self-signed certificate. That warning is different from plain HTTP being marked "Not secure".

Do not use this for the desktop UI:

```text
http://192.168.1.99
```

If you do, Caddy should redirect desktop routes back to HTTPS.

## Pocket Mobile API

Android should be configured with:

```text
Server URL: http://192.168.1.99
Username: duncanmobile
```

Pocket API base path:

```text
/api/pocket/v1
```

Health check:

```text
GET http://192.168.1.99/api/pocket/v1/health
```

Expected response:

```json
{"ok":true,"service":"lifepim-pocket","version":1}
```

The health endpoint does not require authentication.

After registration, Pocket uses:

```text
Authorization: Bearer <device_token>
X-LifePIM-Device-ID: <device_id>
```

Required endpoints:

```text
GET  /api/pocket/v1/health
POST /api/pocket/v1/auth/register-device
GET  /api/pocket/v1/sync/manifest
GET  /api/pocket/v1/items/{id}
POST /api/pocket/v1/sync/push
POST /api/pocket/v1/auth/logout-device
```

## Pocket Note Folder

Pocket sync is scoped to the LifePIM user that registered the mobile device.

New mobile-only notes are saved to the user's Pocket default note folder when it is set:

```text
Admin -> Users -> Edit -> Pocket default note folder
```

Use an absolute Windows path, for example:

```text
N:\duncan\LifePIM_Data\DATA\notes\Mobile
```

If the field is blank, LifePIM falls back to the user's most common existing note folder. For a new or test user with only one desktop note, that means mobile uploads will go into the same folder as that note.

## Testing

From the LifePIM machine:

```powershell
Invoke-WebRequest -Uri "http://192.168.1.99/api/pocket/v1/health" -MaximumRedirection 0 -UseBasicParsing
```

Expected:

```text
StatusCode: 200
Content-Type: application/json
Body: {"ok":true,"service":"lifepim-pocket","version":1}
```

Check that desktop HTTP redirects to HTTPS:

```powershell
Invoke-WebRequest -Uri "http://192.168.1.99/notes" -MaximumRedirection 0 -UseBasicParsing
```

Expected:

```text
StatusCode: 301
Location: https://192.168.1.99/notes
```

Check HTTPS desktop path:

```powershell
curl.exe -k -I https://192.168.1.99/notes
```

Expected when not logged in:

```text
HTTP/1.1 302 Found
Location: /login?next=/notes
```

From another device on the same Wi-Fi, open:

```text
http://192.168.1.99/api/pocket/v1/health
```

The page should show:

```json
{"ok":true,"service":"lifepim-pocket","version":1}
```

## Network Log

LifePIM writes network and mobile API diagnostics to:

```text
lp_network.log
```

By default the file is created in the current app folder, which is normally:

```text
D:\DATA_LLM\dev\lifepim-desktop\src
```

Override the path with:

```powershell
$env:LIFEPIM_NETWORK_LOG = "D:\DATA_LLM\dev\lifepim-desktop\lp_network.log"
```

The log includes:

```text
request_start
request_finish
request_exception
pocket_register_device
pocket_auth_ok
pocket_auth_failed
pocket_manifest_start
pocket_manifest_finish
pocket_item_download
pocket_push_start
pocket_push_finish
login_attempt
login_success
login_failure
trusted_device_restore_ok
trusted_device_restore_failed
logout
```

Sensitive values such as bearer tokens, cookies, and passwords are not written.

To watch the log while pressing Sync in the Android app:

```powershell
Get-Content D:\DATA_LLM\dev\lifepim-desktop\src\lp_network.log -Wait -Tail 80
```

## Trusted Devices vs Pocket Devices

The Admin `Trusted devices` page currently lists browser trusted-login cookies from:

```text
auth_trusted_devices
```

Those rows are tied to a LifePIM web user by `user_id`.

The Pocket API uses its own table:

```text
pocket_devices
```

`pocket_devices` stores the mobile device token hash, device name, platform, IP, user agent, username, and bound LifePIM `user_id`.

If the Admin `Trusted devices` page shows the same phone under an old user, that is the web trusted-device cookie record, not the Pocket bearer token record. Revoke the old trusted web device if needed, then log into the desktop web app as the intended user to create a new browser trusted-device record.

The Admin `Trusted devices` page also has a separate `Mobile devices` table for Pocket devices.
