from common import data as db

STATUS_VALUES = ("idea", "planned", "bought", "cancelled")


def list_plans(domain=None, statuses=None, date_preset=None, sort_key=None):
    conn = db._get_conn()
    conditions = []
    params = []
    if domain and domain.lower() not in ("all", "any"):
        conditions.append("lower(domain) = lower(?)")
        params.append(domain)
    if statuses:
        placeholders = ", ".join(["?"] * len(statuses))
        conditions.append(f"status IN ({placeholders})")
        params.extend(statuses)
    if date_preset == "unscheduled":
        conditions.append("(target_date IS NULL OR trim(target_date) = '')")
    elif date_preset in ("next30", "next90", "next365"):
        day_map = {
            "next30": "+30 day",
            "next90": "+90 day",
            "next365": "+365 day",
        }
        conditions.append(
            "target_date IS NOT NULL AND trim(target_date) <> '' "
            "AND date(target_date) >= date('now') "
            "AND date(target_date) <= date('now', ?)"
        )
        params.append(day_map[date_preset])
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    order_clause = _order_clause(sort_key)
    sql = (
        "SELECT plan_id, item, domain, estimated_cost, target_date, priority, status, notes, "
        "created_at, updated_at "
        "FROM lp_money_plans "
        f"WHERE {where_clause} "
        f"ORDER BY {order_clause}"
    )
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_plan(plan_id):
    conn = db._get_conn()
    row = conn.execute(
        "SELECT plan_id, item, domain, estimated_cost, target_date, priority, status, notes, "
        "created_at, updated_at FROM lp_money_plans WHERE plan_id = ?",
        (plan_id,),
    ).fetchone()
    return dict(row) if row else None


def create_plan(values):
    conn = db._get_conn()
    sql = (
        "INSERT INTO lp_money_plans "
        "(item, domain, estimated_cost, target_date, priority, status, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    cur = conn.execute(
        sql,
        (
            values.get("item"),
            values.get("domain"),
            values.get("estimated_cost"),
            values.get("target_date"),
            values.get("priority"),
            values.get("status"),
            values.get("notes"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_plan(plan_id, values):
    conn = db._get_conn()
    sql = (
        "UPDATE lp_money_plans SET "
        "item = ?, domain = ?, estimated_cost = ?, target_date = ?, "
        "priority = ?, status = ?, notes = ?, updated_at = datetime('now') "
        "WHERE plan_id = ?"
    )
    conn.execute(
        sql,
        (
            values.get("item"),
            values.get("domain"),
            values.get("estimated_cost"),
            values.get("target_date"),
            values.get("priority"),
            values.get("status"),
            values.get("notes"),
            plan_id,
        ),
    )
    conn.commit()


def delete_plan(plan_id):
    conn = db._get_conn()
    conn.execute("DELETE FROM lp_money_plans WHERE plan_id = ?", (plan_id,))
    conn.commit()


def list_domains():
    conn = db._get_conn()
    rows = conn.execute(
        "SELECT DISTINCT domain FROM lp_money_plans WHERE domain IS NOT NULL AND trim(domain) <> '' "
        "ORDER BY lower(domain)"
    ).fetchall()
    return [row[0] for row in rows]


def summary_totals(domain=None):
    conn = db._get_conn()
    domain_filter = ""
    params = []
    if domain and domain.lower() not in ("all", "any"):
        domain_filter = " AND lower(domain) = lower(?)"
        params.append(domain)
    row = conn.execute(
        "SELECT "
        "(SELECT COALESCE(SUM(estimated_cost), 0) FROM lp_money_plans "
        " WHERE status IN ('idea','planned') "
        " AND target_date IS NOT NULL AND trim(target_date) <> '' "
        " AND date(target_date) >= date('now') "
        " AND date(target_date) <= date('now','+30 day')"
        f"{domain_filter}) AS next_30, "
        "(SELECT COALESCE(SUM(estimated_cost), 0) FROM lp_money_plans "
        " WHERE status IN ('idea','planned') "
        " AND target_date IS NOT NULL AND trim(target_date) <> '' "
        " AND date(target_date) >= date('now') "
        " AND date(target_date) <= date('now','+90 day')"
        f"{domain_filter}) AS next_90, "
        "(SELECT COUNT(1) FROM lp_money_plans "
        " WHERE status IN ('idea','planned') "
        " AND (target_date IS NULL OR trim(target_date) = '')"
        f"{domain_filter}) AS unscheduled",
        params * 3,
    ).fetchone()
    return {
        "next_30": row[0] if row else 0,
        "next_90": row[1] if row else 0,
        "unscheduled": row[2] if row else 0,
    }


def _order_clause(sort_key):
    if sort_key == "priority":
        return "priority ASC, (target_date IS NULL) ASC, target_date ASC"
    if sort_key == "cost":
        return "estimated_cost DESC, (target_date IS NULL) ASC, target_date ASC"
    return "(target_date IS NULL) ASC, target_date ASC, priority ASC"
