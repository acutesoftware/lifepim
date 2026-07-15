# LifePIM Networking

LifePIM Desktop production traffic is LAN-reachable only through Caddy.
Waitress binds to loopback and must not be exposed directly to another device.

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

Validate Caddy before starting LifePIM:

```powershell
cd C:\apps\caddy
.\caddy_windows_amd64.exe validate --config Caddyfile
.\caddy_windows_amd64.exe start --config Caddyfile
```

`src\RUN_DESKTOP.BAT` performs this validation in production. If Caddy is missing, invalid, or cannot start, production startup stops instead of falling back to direct HTTP.

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

Caddy local HTTPS uses Caddy's local CA. Export the root certificate from the LifePIM desktop machine, copy it to the Android phone used for LifePIM Pocket, then install it as a user CA certificate in Android settings.

Typical Caddy local CA path:

```text
%APPDATA%\Caddy\pki\authorities\local\root.crt
```

On Android, install the certificate through:

```text
Settings -> Security -> Encryption and credentials -> Install a certificate -> CA certificate
```

Do not disable TLS certificate validation in the Android client. Do not use a trust-all hostname verifier or SSL context.

## Pocket Registration

Pocket devices no longer register with only a username.

1. A logged-in desktop user starts Pocket pairing.
2. LifePIM creates a random one-time pairing code.
3. The code expires after five minutes and can be used once.
4. The mobile app submits the pairing code, username, and device details.
5. The desktop resolves the user from the pairing record and returns a bearer token.

Failed and successful registration attempts are recorded in `pocket_registration_attempts`. Repeated failures by IP, username, pairing code, or device ID are temporarily rate-limited.

After registration, Pocket sends:

```text
Authorization: Bearer <device_token>
X-LifePIM-Device-ID: <device_id>
```

Only token hashes are stored in `pocket_devices`; raw bearer tokens are never stored.

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
