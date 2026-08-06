from __future__ import annotations


def recent_sessions(conn, limit=100, device_id=None, platform=None, application_identifier=None, date=None):
    where = []
    params = []
    if device_id:
        where.append("device_id = ?")
        params.append(device_id)
    if platform:
        where.append("platform = ?")
        params.append(platform)
    if application_identifier:
        where.append("application_identifier = ?")
        params.append(application_identifier)
    if date:
        where.append("substr(start_at_utc, 1, 10) = ?")
        params.append(date)
    sql = "SELECT * FROM activity_session"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY start_at_utc DESC LIMIT ?"
    params.append(int(limit or 100))
    return [dict(row) for row in conn.execute(sql, params).fetchall()]
