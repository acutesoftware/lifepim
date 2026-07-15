import os

from waitress import serve

import common.config as cfg
from app import app


if __name__ == "__main__":
    host = os.getenv("LIFEPIM_HOST", "0.0.0.0")
    port = int(os.getenv("LIFEPIM_PORT", str(cfg.port_num)))
    serve(app, host=host, port=port, threads=8)
