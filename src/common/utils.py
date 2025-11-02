from datetime import datetime
import common.config as mod_cfg

def format_date(dt):
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M")


def get_tabs():
    return mod_cfg.TABS


def get_side_tabs():
    return mod_cfg.SIDE_TABS
