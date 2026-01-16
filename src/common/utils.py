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

def get_table_def(route_id):
    for tbl in mod_cfg.table_def:
        if tbl.get("route") == route_id:
            return tbl
    return None


def build_form_fields(col_list):
    fields = []
    for col in col_list:
        col_lower = col.lower()
        input_type = "text"
        is_textarea = False
        if "date" in col_lower:
            input_type = "date"
        if col_lower in ("description", "content", "col_list", "path"):
            is_textarea = True
        fields.append(
            {
                "name": col,
                "label": col.replace("_", " ").title(),
                "input_type": input_type,
                "is_textarea": is_textarea,
            }
        )
    return fields

