# LifePIM Desktop networking

LifePIM Desktop is supported as a single-owner, local-only application. Its
browser UI is available only on the same computer that runs LifePIM.

## Expected listener

Normal startup uses Waitress at:

```text
http://127.0.0.1:9741
```

`src\RUN_DESKTOP.BAT` and `src\run_waitress.py` reject wildcard, LAN and public
bind addresses. The Flask development server also runs without debug mode and
rejects a non-loopback configured host. Do not put LifePIM behind a LAN reverse
proxy, port forward, tunnel or public web server.

Verify the listener from PowerShell:

```powershell
Get-NetTCPConnection -LocalPort 9741 -State Listen |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

`LocalAddress` must be `127.0.0.1` (or IPv6 loopback `::1` if intentionally
configured), never `0.0.0.0`, `::` or a LAN address.

## Browser request restrictions

The app accepts `Host` values for `localhost`, `127.0.0.1` and `::1` only.
State-changing requests require CSRF tokens, and cross-site `Origin` or
`Sec-Fetch-Site` requests are rejected. Authentication remains required for the
private UI. These checks are defence in depth; loopback binding is the primary
network boundary.

## Disabled companion surfaces

Public notes, Pocket/mobile API and logger API routes are disabled by default.
Their legacy code remains for compatibility, but enabling any of these is
outside the reviewed local-only deployment model:

```text
LIFEPIM_ENABLE_PUBLIC_NOTES=1
LIFEPIM_ENABLE_POCKET_API=1
LIFEPIM_ENABLE_LOGGER_API=1
```

Do not set those variables for normal use. Caddy is not started or configured
by the normal launcher. `scripts\prod\allow_lifepim_caddy_firewall.ps1` now
removes only the old LifePIM-named firewall rules; it does not create inbound
rules.

## Manual second-device check

With LifePIM running, obtain the desktop LAN address with `ipconfig`. From a
second computer or phone on the same network, both of these must fail:

```text
http://<desktop-lan-ip>:9741
https://<desktop-lan-ip>
```

If port 80/443 is still reachable, a legacy Caddy or another reverse proxy may
still be running. Stop it only after confirming it is the LifePIM-specific
instance; do not remove shared proxy configuration.

## Local HTTP and cookies

Loopback HTTP is intentional. Session and remember-me cookies are HttpOnly and
SameSite=Lax. They are not marked Secure on the default HTTP endpoint because a
browser would then refuse to send them. If an operator deliberately supplies
loopback HTTPS, set `LIFEPIM_SECURE_COOKIES=1`.
