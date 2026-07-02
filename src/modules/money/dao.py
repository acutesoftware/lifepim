import json
import os
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from common import data as db
from common import config as cfg


STATUS_VALUES = tuple(cfg.MONEY_PLAN_STATUSES)
SECTION_DEFS = {section["id"]: section for section in cfg.MONEY_SECTIONS}
DEFAULT_SECTION = "assets"
SQL_IDENTIFIER_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
QUOTE_HEADERS = {"User-Agent": "Mozilla/5.0 LifePIM Desktop"}
MARKET_SUFFIXES = {
    "Australia (ASX)": ".AX",
    "United States (US)": "",
    "United Kingdom (LSE)": ".L",
    "Canada (TSX)": ".TO",
    "India (NSE)": ".NS",
}
MANUAL_MARKET = "Manual / Yahoo symbol"


def ensure_money_schema(conn=None):
    conn = db._get_conn() if conn is None else conn
    schema_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "schema_money.sql")
    )
    with open(schema_path, "r", encoding="utf-8") as handle:
        conn.executescript(handle.read())
    db.add_column_if_missing(conn, "lp_money_share_trades", "market", "TEXT")
    conn.commit()
    return conn


def sections():
    return cfg.MONEY_SECTIONS


def section(section_id):
    return SECTION_DEFS.get(section_id) or SECTION_DEFS[DEFAULT_SECTION]


def list_records(section_id, search=None, limit=None):
    ensure_money_schema()
    sec = section(section_id)
    conn = db._get_conn()
    cols = [sec["pk"]] + [col["name"] for col in sec["columns"]]
    derived_cols = [col["name"] for col in sec.get("derived_columns", [])]
    select_cols = ", ".join(cols)
    params = []
    where = "1=1"
    if search:
        like_cols = [col["name"] for col in sec["columns"] if col.get("type") in ("text", "textarea", "select")]
        if like_cols:
            where = " OR ".join([f"lower({name}) LIKE lower(?)" for name in like_cols])
            params = [f"%{search}%"] * len(like_cols)
    sql = f"SELECT {select_cols} FROM {sec['table']} WHERE {where} ORDER BY {sec['default_sort']}"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    if "profit_loss" in derived_cols:
        for row in rows:
            row["profit_loss"] = _profit_loss(row)
    return rows


def get_record(section_id, record_id):
    ensure_money_schema()
    sec = section(section_id)
    conn = db._get_conn()
    cols = [sec["pk"]] + [col["name"] for col in sec["columns"]]
    row = conn.execute(
        f"SELECT {', '.join(cols)} FROM {sec['table']} WHERE {sec['pk']} = ?",
        (record_id,),
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    if any(col["name"] == "profit_loss" for col in sec.get("derived_columns", [])):
        result["profit_loss"] = _profit_loss(result)
    return result


def create_record(section_id, payload):
    ensure_money_schema()
    sec = section(section_id)
    values = normalize_payload(sec, payload)
    cols = list(values.keys())
    placeholders = ", ".join(["?"] * len(cols))
    conn = db._get_conn()
    cur = conn.execute(
        f"INSERT INTO {sec['table']} ({', '.join(cols)}) VALUES ({placeholders})",
        [values[col] for col in cols],
    )
    conn.commit()
    return cur.lastrowid


def update_record(section_id, record_id, payload):
    ensure_money_schema()
    sec = section(section_id)
    values = normalize_payload(sec, payload)
    cols = list(values.keys())
    set_clause = ", ".join([f"{col} = ?" for col in cols])
    conn = db._get_conn()
    conn.execute(
        f"UPDATE {sec['table']} SET {set_clause}, updated_at = datetime('now') WHERE {sec['pk']} = ?",
        [values[col] for col in cols] + [record_id],
    )
    conn.commit()


def delete_record(section_id, record_id):
    ensure_money_schema()
    sec = section(section_id)
    conn = db._get_conn()
    conn.execute(f"DELETE FROM {sec['table']} WHERE {sec['pk']} = ?", (record_id,))
    conn.commit()


def normalize_payload(sec, payload):
    values = {}
    for col in sec["columns"]:
        name = col["name"]
        if col.get("readonly"):
            continue
        raw = payload.get(name)
        if (raw is None or str(raw).strip() == "") and "default" in col:
            raw = col.get("default")
        if col.get("required") and not str(raw or "").strip():
            raise ValueError(f"{col['label']} is required")
        col_type = col.get("type")
        if col_type in ("money", "number"):
            values[name] = _float_value(raw)
        elif col_type == "checkbox":
            values[name] = 1 if raw in (True, "1", "true", "on", "yes", 1) else 0
        else:
            values[name] = str(raw or "").strip()
    if sec["id"] in ("watchlist", "pretend"):
        market = values.get("market") or "Australia (ASX)"
        values["market"] = market
        values["symbol"] = normalize_quote_symbol(values.get("symbol"), market)
    return values


def summaries():
    ensure_money_schema()
    conn = db._get_conn()
    data = {}
    for sec in sections():
        summary_rule = sec.get("summary") or "count"
        if summary_rule == "count":
            row = conn.execute(f"SELECT COUNT(1) FROM {sec['table']}").fetchone()
            data[sec["id"]] = {"label": "Rows", "value": row[0] if row else 0, "kind": "count"}
        elif summary_rule.startswith("sum:"):
            col_name = summary_rule.split(":", 1)[1]
            if col_name == "profit_loss":
                total = sum(_profit_loss(row) for row in list_records(sec["id"]))
            else:
                _assert_identifier(col_name)
                row = conn.execute(f"SELECT COALESCE(SUM({col_name}), 0) FROM {sec['table']}").fetchone()
                total = row[0] if row else 0
            data[sec["id"]] = {"label": "Total", "value": total, "kind": "money"}
        elif summary_rule.startswith("annualized:"):
            _, amount_col, frequency_col = summary_rule.split(":", 2)
            _assert_identifier(amount_col)
            _assert_identifier(frequency_col)
            rows = conn.execute(f"SELECT {amount_col}, {frequency_col} FROM {sec['table']}").fetchall()
            total = sum(_annualized(row[0], row[1]) for row in rows)
            data[sec["id"]] = {"label": "Annual", "value": total, "kind": "money"}
    return data


def refresh_quotes(section_id):
    ensure_money_schema()
    sec = section(section_id)
    if sec["id"] not in ("watchlist", "pretend"):
        return {"updated": 0, "errors": []}
    conn = db._get_conn()
    symbol_rows = conn.execute(
        f"SELECT DISTINCT symbol, market FROM {sec['table']} "
        "WHERE symbol IS NOT NULL AND trim(symbol) <> ''"
    ).fetchall()
    updated = 0
    errors = []
    for row in symbol_rows:
        original_symbol = row["symbol"]
        quote_symbols = quote_symbol_candidates(original_symbol, row["market"] if "market" in row.keys() else "")
        symbol = quote_symbols[0]
        price = None
        last_error = None
        for quote_symbol in quote_symbols:
            try:
                price = fetch_delayed_quote(quote_symbol)
                symbol = quote_symbol
                break
            except Exception as exc:
                last_error = exc
                continue
        if price is None:
            errors.append(f"{original_symbol}: {last_error or 'no price returned'}")
            continue
        cur = conn.execute(
            f"UPDATE {sec['table']} SET symbol = ?, current_price = ?, price_updated_at = ? WHERE upper(symbol) = upper(?)",
            (symbol, price, _utc_now(), original_symbol),
        )
        updated += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    conn.commit()
    return {"updated": updated, "errors": errors}


def fetch_delayed_quote(symbol):
    symbol = normalize_quote_symbol(symbol, "")
    query = urlencode({"range": "1d", "interval": "1m"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}"
    request = Request(url, headers=QUOTE_HEADERS)
    with urlopen(request, timeout=8) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    result = (((payload.get("chart") or {}).get("result") or [None])[0]) or {}
    meta = result.get("meta") or {}
    price = meta.get("regularMarketPrice")
    if price is None:
        closes = (((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
        closes = [item for item in closes if item is not None]
        price = closes[-1] if closes else None
    return float(price) if price is not None else None


def normalize_quote_symbol(symbol, market):
    base = (symbol or "").strip().upper()
    if not base:
        return ""
    market = (market or "").strip()
    if market == MANUAL_MARKET:
        return base
    suffix = MARKET_SUFFIXES.get(market, "")
    if suffix and not base.endswith(suffix):
        base = base.split(".")[0] + suffix
    return base


def quote_symbol_candidates(symbol, market):
    primary = normalize_quote_symbol(symbol, market)
    candidates = [primary] if primary else []
    market = (market or "").strip()
    if market in ("", "Australia (ASX)") and primary and "." not in primary:
        candidates.append(normalize_quote_symbol(primary, "Australia (ASX)"))
    seen = set()
    result = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            result.append(candidate)
            seen.add(candidate)
    return result


def list_plans(domain=None, statuses=None, date_preset=None, sort_key=None):
    records = list_records("planned")
    if domain and domain.lower() not in ("all", "any"):
        records = [row for row in records if (row.get("domain") or "").lower() == domain.lower()]
    if statuses:
        records = [row for row in records if row.get("status") in statuses]
    return records


def get_plan(plan_id):
    return get_record("planned", plan_id)


def create_plan(values):
    return create_record("planned", values)


def update_plan(plan_id, values):
    update_record("planned", plan_id, values)


def delete_plan(plan_id):
    delete_record("planned", plan_id)


def list_domains():
    ensure_money_schema()
    rows = db._get_conn().execute(
        "SELECT DISTINCT domain FROM lp_money_plans WHERE domain IS NOT NULL AND trim(domain) <> '' "
        "ORDER BY lower(domain)"
    ).fetchall()
    return [row[0] for row in rows]


def summary_totals(domain=None):
    return summaries().get("planned", {"value": 0})


def _float_value(value):
    if value is None or str(value).strip() == "":
        return 0.0
    return float(value)


def _annualized(amount, frequency):
    multiplier = {
        "weekly": 52,
        "fortnightly": 26,
        "monthly": 12,
        "quarterly": 4,
        "yearly": 1,
        "once": 1,
    }.get((frequency or "").lower(), 1)
    return float(amount or 0) * multiplier


def _profit_loss(row):
    quantity = float(row.get("quantity") or 0)
    buy_price = float(row.get("pretend_buy_price") or 0)
    current_price = float(row.get("current_price") or 0)
    fees = float(row.get("fees") or 0)
    return (current_price - buy_price) * quantity - fees


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _assert_identifier(value):
    if not value or any(ch not in SQL_IDENTIFIER_CHARS for ch in value):
        raise sqlite3.OperationalError("Invalid SQL identifier")
