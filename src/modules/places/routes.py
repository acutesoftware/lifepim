from html.parser import HTMLParser
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from flask import Blueprint, jsonify, render_template, request, redirect, url_for

from common import data as db
from common import config as cfg
from common import projects as projects_mod
from common import settings as settings_mod
from common.utils import (
    get_side_tabs,
    get_table_def,
    get_tabs,
    paginate_total,
    build_pagination,
    request_area_param,
    normalize_area_param,
)


places_bp = Blueprint(
    "places",
    __name__,
    url_prefix="/places",
    template_folder="templates",
    static_folder="static",
)

_NOMINATIM_LAST_REQUEST = 0.0


def _get_tbl():
    db.ensure_places_schema()
    return get_table_def("places")


def _normalize_area(area):
    return normalize_area_param(area) or None


def _clean_text(value):
    return "" if value is None else str(value).strip()


def _normalize_realm(value):
    text = _clean_text(value) or "all"
    lower = text.lower()
    if lower in {"all", "any"}:
        return "all"
    if lower in {"earth", "address", "addresses"}:
        return "earth"
    if lower in {"internet", "url", "urls"}:
        return "internet"
    if lower == "virtual":
        return "virtual"
    if lower.startswith("virtual:"):
        world = text.split(":", 1)[1].strip()
        return f"virtual:{world}" if world else "virtual"
    return "all"


def _realm_label(realm):
    if realm == "earth":
        return "Earth"
    if realm == "internet":
        return "Internet"
    if realm == "virtual":
        return "Virtual"
    if realm.startswith("virtual:"):
        return realm.split(":", 1)[1] or "Virtual"
    return "All"


def _build_condition(area, tbl, realm=None):
    clauses = []
    params = []
    if area and "area" in (tbl["col_list"] if tbl else []):
        clauses.append("lower(t.area) = lower(?)")
        params.append(area)
    realm = _normalize_realm(realm)
    if realm == "earth":
        clauses.append("COALESCE(NULLIF(t.place_type, ''), 'address') = 'address'")
    elif realm == "internet":
        clauses.append("t.place_type = 'url'")
    elif realm == "virtual":
        clauses.append("t.place_type = 'virtual'")
    elif realm.startswith("virtual:"):
        clauses.append("t.place_type = 'virtual' AND lower(COALESCE(t.virtual_world, '')) = lower(?)")
        params.append(realm.split(":", 1)[1])
    return " AND ".join(clauses) if clauses else "1=1", params


def _fetch_places(area=None, sort_col=None, sort_dir=None, limit=None, offset=None, realm=None):
    tbl = _get_tbl()
    if not tbl:
        return []
    cols = ["id"] + tbl["col_list"]
    order_map = {col: f"t.{col}" for col in tbl["col_list"]}
    sort_key = order_map.get(sort_col or "name", "t.name")
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"
    condition, params = _build_condition(area, tbl, realm)
    sql = (
        f"SELECT {', '.join([f't.{col}' for col in cols])} "
        f"FROM {tbl['name']} t "
        f"WHERE {condition} "
        f"ORDER BY {sort_key} {sort_dir}"
    )
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
        if offset:
            sql += " OFFSET ?"
            params.append(int(offset))
    rows = db._get_conn().execute(sql, params).fetchall()
    return _decorate_places([dict(row) for row in rows])


def _count_places(area=None, realm=None):
    tbl = _get_tbl()
    if not tbl:
        return 0
    condition, params = _build_condition(area, tbl, realm)
    row = db._get_conn().execute(
        f"SELECT COUNT(1) as cnt FROM {tbl['name']} t WHERE {condition}",
        params,
    ).fetchone()
    return row["cnt"] if row else 0


def _parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _join_place_parts(*values):
    return " ".join([str(value).strip() for value in values if str(value or "").strip()])


def _format_place_address(item):
    street = _join_place_parts(item.get("address_street"))
    suburb_line = _join_place_parts(item.get("suburb"), item.get("state"), item.get("postcode"))
    country = _join_place_parts(item.get("country"))
    return ", ".join([part for part in (street, suburb_line, country) if part])


def _build_marker_details(item, lat, lon):
    details = []
    description = _clean_text(item.get("desc"))
    address = _format_place_address(item)
    if description:
        details.append(description)
    if address:
        details.append(address)
    details.append(f"{lat:.6f}, {lon:.6f}")
    return details


def _build_external_map_links(item, lat, lon):
    name = _clean_text(item.get("name"))
    address = _format_place_address(item)
    context = {
        "lat": f"{lat:.6f}",
        "lon": f"{lon:.6f}",
        "name": quote_plus(name),
        "address": quote_plus(address),
    }
    links = []
    for spec in getattr(cfg, "PLACES_MAP_EXTERNAL_URLS", []):
        label = _clean_text(spec.get("label"))
        template = _clean_text(spec.get("url"))
        if not label or not template:
            continue
        try:
            link_url = template.format(**context)
        except (KeyError, ValueError):
            continue
        links.append({"label": label, "url": link_url})
    return links


def _place_map_actions(item):
    lat = _parse_float(item.get("gps_lat"))
    lon = _parse_float(item.get("gps_long"))
    if lat is None or lon is None:
        return []
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return []
    return _build_external_map_links(item, lat, lon)


def _place_type(item):
    value = _clean_text(item.get("place_type")).lower()
    if value in {"address", "url", "virtual"}:
        return value
    if _clean_text(item.get("url")):
        return "url"
    if any(_clean_text(item.get(col)) for col in ("virtual_world", "coord_x", "coord_y", "coord_z", "coord_region")):
        return "virtual"
    return "address"


def _host_from_url(value):
    try:
        return urlsplit(value or "").hostname or ""
    except ValueError:
        return ""


def _display_url(value):
    try:
        parts = urlsplit(value or "")
    except ValueError:
        return value or ""
    host = parts.hostname or ""
    if not host:
        return value or ""
    path = (parts.path or "").rstrip("/")
    return host + (path if path and path != "/" else "")


def _location_summary(item):
    current_type = _place_type(item)
    if current_type == "url":
        return _display_url(item.get("url") or "")
    if current_type == "virtual":
        coords = _join_place_parts(item.get("coord_x"), item.get("coord_y"), item.get("coord_z"))
        parts = [item.get("virtual_world"), item.get("coord_region"), coords]
        return " - ".join([_clean_text(part) for part in parts if _clean_text(part)])
    return _format_place_address(item) or _join_place_parts(item.get("gps_lat"), item.get("gps_long"))


def _decorate_place(item):
    current_type = _place_type(item)
    item["place_type_current"] = current_type
    item["place_type_label"] = {"address": "Earth", "url": "Internet", "virtual": "Virtual"}.get(current_type, current_type)
    if current_type == "virtual" and _clean_text(item.get("virtual_world")):
        item["place_type_label"] = _clean_text(item.get("virtual_world"))
    item["hostname"] = _host_from_url(item.get("url") or "")
    item["display_url"] = _display_url(item.get("url") or "")
    item["location_summary"] = _location_summary(item)
    item["open_url"] = item.get("url") if current_type == "url" and item.get("url") else ""
    item["map_actions"] = _place_map_actions(item)
    return item


def _decorate_places(items):
    for item in items:
        _decorate_place(item)
    return items


class _TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_parts = []
        self.og_title = ""

    def handle_starttag(self, tag, attrs):
        tag = (tag or "").lower()
        attrs = {str(key).lower(): value for key, value in attrs}
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            prop = (attrs.get("property") or attrs.get("name") or "").lower()
            if prop == "og:title" and not self.og_title:
                self.og_title = _clean_text(attrs.get("content"))

    def handle_endtag(self, tag):
        if (tag or "").lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title and data:
            self.title_parts.append(data)

    @property
    def title(self):
        title = " ".join(" ".join(self.title_parts).split()).strip()
        return title or " ".join((self.og_title or "").split()).strip()


def normalize_place_url(value):
    text = _clean_text(value)
    if not text:
        return ""
    if any(ch.isspace() for ch in text):
        raise ValueError("URL cannot contain spaces.")
    if "://" not in text:
        text = "https://" + text
    parts = urlsplit(text)
    scheme = (parts.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise ValueError("URL must start with http:// or https://.")
    if not parts.netloc or not _clean_text(parts.hostname):
        raise ValueError("URL must include a host.")
    return urlunsplit((scheme, parts.netloc, parts.path or "", parts.query, ""))


def _url_metadata(value, fetch=True):
    try:
        normalized = normalize_place_url(value)
    except ValueError as exc:
        return {"url": value or "", "title": _clean_text(value), "hostname": "", "error": str(exc)}
    hostname = _host_from_url(normalized)
    title = hostname
    result_url = normalized
    if fetch:
        try:
            req = Request(
                normalized,
                headers={
                    "User-Agent": "LifePIM/1.0 (+local desktop URL title lookup)",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urlopen(req, timeout=3) as response:
                result_url = response.geturl() or normalized
                hostname = _host_from_url(result_url) or hostname
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read(256 * 1024).decode(charset, errors="replace")
            parser = _TitleParser()
            parser.feed(body)
            title = parser.title or hostname
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            title = hostname
    return {"url": result_url, "title": title or hostname or normalized, "hostname": hostname}


def _nominatim_json(path, params):
    global _NOMINATIM_LAST_REQUEST
    elapsed = time.monotonic() - _NOMINATIM_LAST_REQUEST
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _NOMINATIM_LAST_REQUEST = time.monotonic()
    query = urlencode({key: value for key, value in params.items() if _clean_text(value)})
    url = f"https://nominatim.openstreetmap.org/{path}?{query}"
    req = Request(
        url,
        headers={
            "User-Agent": "LifePIM Desktop/3.1 places-geocode",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=4) as response:
        data = json.loads(response.read(128 * 1024).decode("utf-8", errors="replace"))
    return data


def _address_query(payload):
    parts = [
        payload.get("address_street"),
        payload.get("suburb"),
        payload.get("state"),
        payload.get("postcode"),
        payload.get("country"),
    ]
    query = ", ".join([_clean_text(part) for part in parts if _clean_text(part)])
    return query or _clean_text(payload.get("name"))


def _address_fields_from_nominatim(address):
    address = address or {}
    street = _join_place_parts(address.get("house_number"), address.get("road") or address.get("pedestrian"))
    suburb = (
        address.get("suburb")
        or address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
    )
    state = address.get("state") or address.get("region")
    return {
        "address_street": street,
        "suburb": _clean_text(suburb),
        "state": _clean_text(state),
        "postcode": _clean_text(address.get("postcode")),
        "country": _clean_text(address.get("country")),
    }


def _geocode_address(payload):
    query = _address_query(payload)
    if not query:
        return {"error": "Enter an address or title first."}
    try:
        results = _nominatim_json(
            "search",
            {
                "format": "jsonv2",
                "addressdetails": "1",
                "limit": "1",
                "q": query,
            },
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return {"error": f"Address lookup failed: {exc}"}
    if not results:
        return {"error": "No matching address found."}
    first = results[0]
    return {
        "latitude": _clean_text(first.get("lat")),
        "longitude": _clean_text(first.get("lon")),
        "display_name": _clean_text(first.get("display_name")),
        **_address_fields_from_nominatim(first.get("address")),
    }


def _reverse_geocode(payload):
    lat = _parse_float(payload.get("gps_lat"))
    lon = _parse_float(payload.get("gps_long"))
    if lat is None or lon is None:
        return {"error": "Enter latitude and longitude first."}
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return {"error": "Latitude or longitude is out of range."}
    try:
        result = _nominatim_json(
            "reverse",
            {
                "format": "jsonv2",
                "addressdetails": "1",
                "lat": f"{lat:.7f}",
                "lon": f"{lon:.7f}",
            },
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return {"error": f"Coordinate lookup failed: {exc}"}
    if not result:
        return {"error": "No matching address found."}
    return {
        "display_name": _clean_text(result.get("display_name")),
        **_address_fields_from_nominatim(result.get("address")),
    }


def _configured_virtual_worlds():
    worlds = []
    try:
        configured_worlds = settings_mod.get_places_settings(db._get_conn()).get("virtual_worlds") or []
    except Exception:
        configured_worlds = []
    for world in configured_worlds:
        text = _clean_text(world)
        if text and text not in worlds:
            worlds.append(text)
    try:
        rows = db._get_conn().execute(
            "SELECT DISTINCT virtual_world FROM lp_places "
            "WHERE COALESCE(virtual_world, '') != '' ORDER BY lower(virtual_world)"
        ).fetchall()
        for row in rows:
            text = _clean_text(row["virtual_world"] if hasattr(row, "keys") else row[0])
            if text and text not in worlds:
                worlds.append(text)
    except Exception:
        pass
    return worlds


def _place_type_choices(item=None):
    choices = [
        {"value": "address", "label": "Address"},
        {"value": "url", "label": "URL"},
    ]
    worlds = _configured_virtual_worlds()
    current_world = _clean_text((item or {}).get("virtual_world"))
    if current_world and current_world not in worlds:
        worlds.insert(0, current_world)
    if worlds:
        choices.extend({"value": f"virtual|{world}", "label": world} for world in worlds)
    else:
        choices.append({"value": "virtual|", "label": "Virtual"})
    return choices


def _selected_type_choice(item):
    current_type = _place_type(item or {})
    if current_type == "virtual":
        return f"virtual|{_clean_text((item or {}).get('virtual_world'))}"
    return current_type


def _form_values(form, area, tbl):
    values = {col: _clean_text(form.get(col)) for col in (tbl["col_list"] if tbl else [])}
    if "area" in values and not values["area"] and area:
        values["area"] = area
    choice = _clean_text(form.get("place_type_choice") or values.get("place_type") or "address")
    virtual_world = values.get("virtual_world", "")
    if choice.startswith("virtual|"):
        place_type = "virtual"
        selected_world = choice.split("|", 1)[1].strip()
        if selected_world:
            virtual_world = selected_world
    elif choice == "url":
        place_type = "url"
    else:
        place_type = "address"
    values["place_type"] = place_type
    values["virtual_world"] = virtual_world
    if place_type == "url":
        raw_url = values.get("url", "")
        if not raw_url:
            return values, "URL is required for Internet Places."
        try:
            values["url"] = normalize_place_url(raw_url)
        except ValueError as exc:
            return values, str(exc)
        if not values.get("name"):
            values["name"] = _host_from_url(values["url"]) or values["url"]
    elif not values.get("name") and place_type == "virtual":
        values["name"] = values.get("coord_region") or values.get("virtual_world") or "Virtual Place"
    elif not values.get("name"):
        values["name"] = _format_place_address(values) or _join_place_parts(values.get("gps_lat"), values.get("gps_long")) or "Place"
    return values, ""


def _place_row(place_id, tbl=None):
    tbl = tbl or _get_tbl()
    if not tbl:
        return None
    rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [place_id])
    return dict(rows[0]) if rows else None


def _insert_place(values, tbl=None):
    tbl = tbl or _get_tbl()
    if not tbl:
        return None
    return db.add_record(db.conn, tbl["name"], tbl["col_list"], [values.get(col, "") for col in tbl["col_list"]])


def _update_place(place_id, values, tbl=None):
    tbl = tbl or _get_tbl()
    if not tbl:
        return False
    return db.update_record(db.conn, tbl["name"], place_id, tbl["col_list"], [values.get(col, "") for col in tbl["col_list"]])


def _existing_url_place_id(url):
    try:
        row = db._get_conn().execute(
            "SELECT id FROM lp_places WHERE place_type = 'url' AND lower(url) = lower(?) LIMIT 1",
            (url,),
        ).fetchone()
    except Exception:
        return None
    return row["id"] if row else None


def _fallback_address_parts(line):
    parts = [_clean_text(part) for part in (line or "").split(",")]
    parts = [part for part in parts if part]
    values = {
        "address_street": parts[0] if len(parts) > 0 else _clean_text(line),
        "suburb": parts[1] if len(parts) > 1 else "",
        "state": "",
        "postcode": "",
        "country": parts[-1] if len(parts) > 2 else "",
    }
    if len(parts) > 2:
        state_parts = parts[2].split()
        if state_parts and state_parts[-1].isdigit():
            values["postcode"] = state_parts[-1]
            values["state"] = " ".join(state_parts[:-1])
        else:
            values["state"] = parts[2]
    return values


def _import_url_lines(text, area):
    tbl = _get_tbl()
    rows = []
    for line_no, line in enumerate((text or "").splitlines(), start=1):
        raw = _clean_text(line)
        if not raw:
            continue
        result = {"line": line_no, "input": raw, "status": "skipped", "message": ""}
        metadata = _url_metadata(raw)
        if metadata.get("error"):
            result["message"] = metadata["error"]
            rows.append(result)
            continue
        url = metadata.get("url") or ""
        existing_id = _existing_url_place_id(url)
        if existing_id:
            result.update({"status": "exists", "place_id": existing_id, "title": metadata.get("title") or ""})
            rows.append(result)
            continue
        values = {col: "" for col in tbl["col_list"]}
        values.update(
            {
                "name": metadata.get("title") or metadata.get("hostname") or url,
                "desc": "",
                "place_type": "url",
                "url": url,
                "area": area or "",
            }
        )
        place_id = _insert_place(values, tbl)
        result.update({"status": "added" if place_id else "failed", "place_id": place_id, "title": values["name"], "url": url})
        if not place_id:
            result["message"] = "Could not save Place."
        rows.append(result)
    return rows


def _import_address_lines(text, area):
    tbl = _get_tbl()
    rows = []
    for line_no, line in enumerate((text or "").splitlines(), start=1):
        raw = _clean_text(line)
        if not raw:
            continue
        result = {"line": line_no, "input": raw, "status": "added", "message": ""}
        values = {col: "" for col in tbl["col_list"]}
        values.update(
            {
                "name": raw,
                "desc": "",
                "place_type": "address",
                "area": area or "",
                **_fallback_address_parts(raw),
            }
        )
        geocoded = _geocode_address({"name": raw, "address_street": raw})
        if geocoded.get("error"):
            result["message"] = geocoded["error"]
        else:
            values.update(
                {
                    "gps_lat": geocoded.get("latitude") or "",
                    "gps_long": geocoded.get("longitude") or "",
                    "address_street": geocoded.get("address_street") or values["address_street"],
                    "suburb": geocoded.get("suburb") or values["suburb"],
                    "state": geocoded.get("state") or values["state"],
                    "postcode": geocoded.get("postcode") or values["postcode"],
                    "country": geocoded.get("country") or values["country"],
                }
            )
            if geocoded.get("display_name"):
                values["name"] = geocoded["display_name"].split(",", 1)[0] or raw
        place_id = _insert_place(values, tbl)
        result.update({"status": "added" if place_id else "failed", "place_id": place_id, "title": values["name"]})
        if not place_id:
            result["message"] = "Could not save Place."
        rows.append(result)
    return rows


def _rescan_place(item):
    tbl = _get_tbl()
    values = {col: item.get(col, "") for col in tbl["col_list"]}
    current_type = _place_type(item)
    if current_type == "url":
        metadata = _url_metadata(item.get("url") or "")
        if metadata.get("error"):
            return False, metadata["error"]
        values["url"] = metadata.get("url") or values.get("url", "")
        if metadata.get("title"):
            values["name"] = metadata["title"]
        return _update_place(item["id"], values, tbl), "URL title refreshed."
    if current_type == "address":
        if _format_place_address(item) or item.get("name"):
            geocoded = _geocode_address(item)
            if not geocoded.get("error"):
                values["gps_lat"] = geocoded.get("latitude") or values.get("gps_lat", "")
                values["gps_long"] = geocoded.get("longitude") or values.get("gps_long", "")
                for col in ("address_street", "suburb", "state", "postcode", "country"):
                    values[col] = geocoded.get(col) or values.get(col, "")
                return _update_place(item["id"], values, tbl), "Address GPS refreshed."
        reverse = _reverse_geocode(item)
        if reverse.get("error"):
            return False, reverse["error"]
        for col in ("address_street", "suburb", "state", "postcode", "country"):
            values[col] = reverse.get(col) or values.get(col, "")
        return _update_place(item["id"], values, tbl), "Address fields refreshed."
    return False, "Virtual Places do not have external details to rescan."


def _selected_place_ids(payload):
    raw_ids = payload.get("place_ids") or payload.get("ids") or []
    ids = []
    for value in raw_ids:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return ids


def _filter_options(area, active_realm):
    filters = [{"id": "all", "label": "All", "count": _count_places(area, "all")}]
    earth_count = _count_places(area, "earth")
    filters.append({"id": "earth", "label": "Earth", "count": earth_count})
    internet_count = _count_places(area, "internet")
    filters.append({"id": "internet", "label": "Internet", "count": internet_count})
    try:
        condition, params = _build_condition(area, _get_tbl(), "virtual")
        rows = db._get_conn().execute(
            "SELECT COALESCE(NULLIF(virtual_world, ''), 'Virtual') AS world, COUNT(1) AS cnt "
            f"FROM lp_places t WHERE {condition} "
            "GROUP BY COALESCE(NULLIF(virtual_world, ''), 'Virtual') "
            "ORDER BY lower(world)",
            params,
        ).fetchall()
    except Exception:
        rows = []
    for row in rows:
        world = row["world"]
        filter_id = f"virtual:{world if world != 'Virtual' else ''}".rstrip(":")
        filters.append({"id": filter_id, "label": world, "count": row["cnt"]})
    if active_realm.startswith("virtual:") and active_realm not in {item["id"] for item in filters}:
        world = active_realm.split(":", 1)[1]
        filters.append({"id": active_realm, "label": world, "count": 0})
    return filters


@places_bp.route("/")
def list_places_route():
    return list_places_table_route()


@places_bp.route("/table")
def list_places_table_route():
    area = _normalize_area(request_area_param())
    realm = _normalize_realm(request.args.get("realm"))
    mode = request.args.get("mode") or ("grid" if realm == "internet" else "table")
    if mode not in {"table", "grid"}:
        mode = "table"
    sort_col = request.args.get("sort") or "name"
    sort_dir = request.args.get("dir") or "asc"
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = _count_places(area, realm)
    offset = (page - 1) * per_page
    items = _fetch_places(area, sort_col, sort_dir, limit=per_page, offset=offset, realm=realm)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "places.list_places_table_route",
        {"area": area, "realm": realm, "mode": mode, "sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
    tbl = _get_tbl()
    col_list = [
        col for col in (tbl["col_list"] if tbl else [])
        if col in {"name", "place_type", "virtual_world", "url", "suburb", "state", "country", "gps_lat", "gps_long", "area"}
    ]
    return render_template(
        "places_list_table.html",
        active_tab="places",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Places - {_realm_label(realm)} ({area or 'All'})",
        content_html="",
        items=items,
        col_list=col_list,
        area=area,
        realm=realm,
        mode=mode,
        filters=_filter_options(area, realm),
        sort_col=sort_col,
        sort_dir=sort_dir,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@places_bp.route("/import", methods=["GET", "POST"])
def import_places_route():
    area = request_area_param("General", include_form=True) or "General"
    import_kind = (request.values.get("kind") or "internet").strip().lower()
    if import_kind not in {"internet", "address"}:
        import_kind = "internet"
    text = request.form.get("import_text", "")
    results = []
    if request.method == "POST":
        if import_kind == "internet":
            results = _import_url_lines(text, area)
        else:
            results = _import_address_lines(text, area)
    return render_template(
        "places_import.html",
        active_tab="places",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Places",
        content_html="",
        area=area,
        import_kind=import_kind,
        import_text=text,
        results=results,
    )


@places_bp.route("/map")
def list_places_map_route():
    area = _normalize_area(request_area_param())
    items = _fetch_places(area, sort_col="name", sort_dir="asc")
    markers = []
    for item in items:
        lat = _parse_float(item.get("gps_lat"))
        lon = _parse_float(item.get("gps_long"))
        if lat is None or lon is None:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        markers.append(
            {
                "id": item.get("id"),
                "name": item.get("name") or "",
                "details": _build_marker_details(item, lat, lon),
                "actions": _build_external_map_links(item, lat, lon),
                "lat": lat,
                "lon": lon,
                "url": url_for("places.view_place_route", place_id=item.get("id"), area=area),
            }
        )
    return render_template(
        "places_list_map.html",
        active_tab="places",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Places Map ({area or 'All'})",
        content_html="",
        items=items,
        markers=markers,
        area=area,
        map_names_english=settings_mod.get_general_settings().get("map_names_english", True),
    )


@places_bp.route("/view/<int:place_id>")
def view_place_route(place_id):
    area = _normalize_area(request_area_param())
    tbl = _get_tbl()
    item = None
    if tbl:
        rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [place_id])
        if rows:
            item = dict(rows[0])
    if not item:
        return redirect(url_for("places.list_places_table_route", area=area))
    _decorate_place(item)
    return render_template(
        "places_view.html",
        active_tab="places",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=item.get("name", "Place"),
        content_html="",
        item=item,
        selected_type_choice=_selected_type_choice(item),
        area=area,
        project_options=projects_mod.project_list(statuses=("planned", "active")),
        record_projects=projects_mod.record_projects("place", place_id),
    )


@places_bp.route("/add", methods=["GET", "POST"])
def add_place_route():
    area = request_area_param("General", include_form=True) or "General"
    tbl = _get_tbl()
    error = ""
    item = {"place_type": "address", "area": area}
    if request.method == "POST" and tbl:
        item, error = _form_values(request.form, area, tbl)
        if not error:
            values = [item.get(col, "") for col in tbl["col_list"]]
            place_id = db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
            if place_id:
                return redirect(url_for("places.view_place_route", place_id=place_id, area=area))
            error = "Could not save Place."
    return render_template(
        "places_edit.html",
        active_tab="places",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add Place",
        item=item,
        error=error,
        place_type_choices=_place_type_choices(item),
        selected_type_choice=_selected_type_choice(item),
        area=area,
    )


@places_bp.route("/edit/<int:place_id>", methods=["GET", "POST"])
def edit_place_route(place_id):
    area = _normalize_area(request_area_param(include_form=True))
    tbl = _get_tbl()
    item = None
    if tbl:
        item = _place_row(place_id, tbl)
    if not item:
        return redirect(url_for("places.list_places_table_route", area=area))
    error = ""
    if request.method == "POST" and tbl:
        item, error = _form_values(request.form, area, tbl)
        if not error:
            values = [item.get(col, "") for col in tbl["col_list"]]
            db.update_record(db.conn, tbl["name"], place_id, tbl["col_list"], values)
            return redirect(url_for("places.view_place_route", place_id=place_id, area=area))
    return render_template(
        "places_edit.html",
        active_tab="places",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Place",
        item=item,
        error=error,
        place_type_choices=_place_type_choices(item),
        selected_type_choice=_selected_type_choice(item),
        area=area,
    )


@places_bp.route("/delete/<int:place_id>")
def delete_place_route(place_id):
    area = _normalize_area(request_area_param())
    tbl = _get_tbl()
    if tbl:
        db.delete_record(db.conn, tbl["name"], place_id)
    return redirect(url_for("places.list_places_table_route", area=area))


@places_bp.route("/api/delete-selected", methods=["POST"])
def delete_selected_places_route():
    payload = request.get_json(silent=True) or {}
    ids = _selected_place_ids(payload)
    deleted = []
    errors = []
    tbl = _get_tbl()
    for place_id in ids:
        if not _place_row(place_id, tbl):
            errors.append({"place_id": place_id, "error": "Place not found."})
            continue
        if db.delete_record(db.conn, tbl["name"], place_id):
            deleted.append(place_id)
        else:
            errors.append({"place_id": place_id, "error": "Delete failed."})
    return jsonify({"deleted": len(deleted), "deleted_ids": deleted, "errors": errors})


@places_bp.route("/api/rescan-selected", methods=["POST"])
def rescan_selected_places_route():
    payload = request.get_json(silent=True) or {}
    ids = _selected_place_ids(payload)
    updated = []
    errors = []
    tbl = _get_tbl()
    for place_id in ids:
        item = _place_row(place_id, tbl)
        if not item:
            errors.append({"place_id": place_id, "error": "Place not found."})
            continue
        ok, message = _rescan_place(item)
        if ok:
            updated.append({"place_id": place_id, "message": message})
        else:
            errors.append({"place_id": place_id, "error": message})
    return jsonify({"updated": len(updated), "updated_items": updated, "errors": errors})


@places_bp.route("/url-metadata", methods=["POST"])
def url_metadata_route():
    payload = request.get_json(silent=True) or {}
    return jsonify(_url_metadata(payload.get("url") or ""))


@places_bp.route("/geocode-address", methods=["POST"])
def geocode_address_route():
    payload = request.get_json(silent=True) or {}
    return jsonify(_geocode_address(payload))


@places_bp.route("/reverse-geocode", methods=["POST"])
def reverse_geocode_route():
    payload = request.get_json(silent=True) or {}
    return jsonify(_reverse_geocode(payload))
