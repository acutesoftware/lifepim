import os

from waitress import serve

import common.config as cfg


LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def validate_loopback_host(host):
    host = (host or "").strip().lower()
    if host not in LOOPBACK_HOSTS:
        raise RuntimeError(
            "LifePIM Desktop is local-only. LIFEPIM_HOST must be 127.0.0.1, ::1, or localhost."
        )
    return host


def main():
    host = validate_loopback_host(os.getenv("LIFEPIM_HOST", "127.0.0.1"))
    port = int(os.getenv("LIFEPIM_PORT", str(cfg.port_num)))
    from app import app

    serve(app, host=host, port=port, threads=8)


if __name__ == "__main__":
    main()
