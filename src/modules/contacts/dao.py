import csv
import re

from common import data as db

FACT_TYPES = ("email", "phone", "address", "url", "org", "note", "other")


def normalize_name(value):
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def list_contacts(sort_key=None, sort_dir=None, limit=None, offset=None):
    conn = db._get_conn()
    order_map = {
        "display_name": "c.display_name",
        "normalized_name": "c.normalized_name",
        "created_utc": "c.created_utc",
        "updated_utc": "c.updated_utc",
        "fact_count": "fact_count",
    }
    sort_key = order_map.get(sort_key or "display_name", "c.display_name")
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"
    sql = (
        "SELECT c.contact_id, c.display_name, c.normalized_name, c.created_utc, c.updated_utc, "
        "(SELECT COUNT(1) FROM lp_contact_facts f WHERE f.contact_id = c.contact_id) AS fact_count "
        "FROM lp_contacts c "
        f"ORDER BY {sort_key} {sort_dir}"
    )
    params = []
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
        if offset:
            sql += " OFFSET ?"
            params.append(int(offset))
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def count_contacts():
    conn = db._get_conn()
    row = conn.execute("SELECT COUNT(1) AS cnt FROM lp_contacts").fetchone()
    return row["cnt"] if row else 0


def get_contact(contact_id):
    conn = db._get_conn()
    row = conn.execute(
        "SELECT contact_id, display_name, normalized_name, created_utc, updated_utc "
        "FROM lp_contacts WHERE contact_id = ?",
        (contact_id,),
    ).fetchone()
    return dict(row) if row else None


def get_contact_by_normalized(normalized_name):
    conn = db._get_conn()
    row = conn.execute(
        "SELECT contact_id, display_name, normalized_name, created_utc, updated_utc "
        "FROM lp_contacts WHERE normalized_name = ?",
        (normalized_name,),
    ).fetchone()
    return dict(row) if row else None


def create_contact(display_name):
    name = (display_name or "").strip()
    if not name:
        return None
    normalized = normalize_name(name)
    conn = db._get_conn()
    cur = conn.execute(
        "INSERT INTO lp_contacts (display_name, normalized_name, created_utc, updated_utc) "
        "VALUES (?, ?, datetime('now'), datetime('now'))",
        (name, normalized),
    )
    conn.commit()
    return cur.lastrowid


def update_contact(contact_id, display_name):
    name = (display_name or "").strip()
    if not name:
        return False
    normalized = normalize_name(name)
    conn = db._get_conn()
    conn.execute(
        "UPDATE lp_contacts SET display_name = ?, normalized_name = ?, updated_utc = datetime('now') "
        "WHERE contact_id = ?",
        (name, normalized, contact_id),
    )
    conn.commit()
    return True


def touch_contact(contact_id):
    conn = db._get_conn()
    conn.execute(
        "UPDATE lp_contacts SET updated_utc = datetime('now') WHERE contact_id = ?",
        (contact_id,),
    )
    conn.commit()


def delete_contact(contact_id):
    conn = db._get_conn()
    conn.execute("DELETE FROM lp_contacts WHERE contact_id = ?", (contact_id,))
    conn.commit()


def list_facts(contact_id):
    conn = db._get_conn()
    rows = conn.execute(
        "SELECT fact_id, contact_id, fact_type, fact_value, source_system, source_ref, confidence, created_utc "
        "FROM lp_contact_facts WHERE contact_id = ? ORDER BY fact_type, fact_value",
        (contact_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def add_fact(contact_id, fact_type, fact_value, source_system, source_ref=None, confidence=None):
    fact_value = (fact_value or "").strip()
    if not fact_value:
        return None
    if fact_type not in FACT_TYPES:
        fact_type = "other"
    source_system = (source_system or "").strip() or "manual"
    source_ref = (source_ref or "").strip() or None
    conn = db._get_conn()
    cur = conn.execute(
        "INSERT INTO lp_contact_facts "
        "(contact_id, fact_type, fact_value, source_system, source_ref, confidence, created_utc) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        (contact_id, fact_type, fact_value, source_system, source_ref, confidence),
    )
    conn.commit()
    touch_contact(contact_id)
    return cur.lastrowid


def delete_fact(fact_id):
    conn = db._get_conn()
    row = conn.execute("SELECT contact_id FROM lp_contact_facts WHERE fact_id = ?", (fact_id,)).fetchone()
    conn.execute("DELETE FROM lp_contact_facts WHERE fact_id = ?", (fact_id,))
    conn.commit()
    if row:
        touch_contact(row["contact_id"])


def import_contacts_from_csv(csv_path, header_map, source_system="csv", source_ref=None, confidence=None):
    inserted = 0
    updated = 0
    created_facts = 0
    if not csv_path:
        return {"inserted": 0, "updated": 0, "facts": 0}
    display_headers = [h for h, v in header_map.items() if v == "display_name"]
    if not display_headers:
        raise ValueError("A display_name column is required for import.")
    if len(display_headers) > 1:
        raise ValueError("Only one display_name column can be selected.")
    display_header = display_headers[0]
    with open(csv_path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            display_name = (row.get(display_header) or "").strip()
            if not display_name:
                continue
            normalized = normalize_name(display_name)
            contact = get_contact_by_normalized(normalized)
            if contact:
                contact_id = contact["contact_id"]
                updated += 1
                if display_name != contact.get("display_name"):
                    update_contact(contact_id, display_name)
            else:
                contact_id = create_contact(display_name)
                inserted += 1
            if not contact_id:
                continue
            for header, mapping in header_map.items():
                if mapping in ("", None, "ignore", "display_name"):
                    continue
                value = (row.get(header) or "").strip()
                if not value:
                    continue
                add_fact(contact_id, mapping, value, source_system, source_ref, confidence)
                created_facts += 1
    return {"inserted": inserted, "updated": updated, "facts": created_facts}
