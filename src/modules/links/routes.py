from flask import Blueprint, jsonify, request

from common import data
from common import links as link_model
from common import links_records


links_bp = Blueprint("links", __name__)

_schema_ready = False


def _ensure_schema():
    global _schema_ready
    if _schema_ready:
        return
    conn = data._get_conn()
    link_model.ensure_links_schema(conn)
    conn.commit()
    _schema_ready = True


def _attach_other_summary(links, perspective):
    if not links:
        return links
    for link in links:
        if perspective == "incoming":
            other_type = link.get("src_type")
            other_id = link.get("src_id")
        else:
            other_type = link.get("dst_type")
            other_id = link.get("dst_id")
        if not other_type or not other_id:
            continue
        summary = links_records.get_record_summary(other_type, other_id)
        if summary:
            link["other_summary"] = summary
    return links


@links_bp.route("/api/config")
def links_config_route():
    return jsonify(
        {
            "link_types": list(link_model.LINK_TYPE_VOCAB),
            "context_defaults": link_model.CONTEXT_DEFAULTS,
            "fallback_contexts": list(link_model.FALLBACK_CONTEXTS),
        }
    )


@links_bp.route("/api/outgoing")
def list_outgoing_route():
    _ensure_schema()
    src_type = request.args.get("src_type", "")
    src_id = request.args.get("src_id", "")
    if not src_type or not src_id:
        return jsonify({"links": []})
    links = link_model.list_outgoing(data._get_conn(), src_type, src_id)
    _attach_other_summary(links, "outgoing")
    return jsonify({"links": links})


@links_bp.route("/api/incoming")
def list_incoming_route():
    _ensure_schema()
    dst_type = request.args.get("dst_type", "")
    dst_id = request.args.get("dst_id", "")
    if not dst_type or not dst_id:
        return jsonify({"links": []})
    links = link_model.list_incoming(data._get_conn(), dst_type, dst_id)
    _attach_other_summary(links, "incoming")
    return jsonify({"links": links})


@links_bp.route("/api/create", methods=["POST"])
def create_link_route():
    _ensure_schema()
    payload = request.get_json(silent=True) or {}
    if payload.get("link_type") not in link_model.LINK_TYPE_VOCAB:
        return jsonify({"error": "invalid_link_type"}), 400
    result = link_model.create_link(data._get_conn(), payload)
    return jsonify(result)


@links_bp.route("/api/update/<int:link_id>", methods=["PATCH"])
def update_link_route(link_id):
    _ensure_schema()
    payload = request.get_json(silent=True) or {}
    if "link_type" in payload and payload["link_type"] not in link_model.LINK_TYPE_VOCAB:
        return jsonify({"error": "invalid_link_type"}), 400
    updated = link_model.update_link(data._get_conn(), link_id, payload)
    return jsonify({"updated": bool(updated)})


@links_bp.route("/api/delete/<int:link_id>", methods=["DELETE"])
def delete_link_route(link_id):
    _ensure_schema()
    deleted = link_model.delete_link(data._get_conn(), link_id)
    return jsonify({"deleted": bool(deleted)})


@links_bp.route("/api/search")
def records_search_route():
    query = request.args.get("q", "")
    types_param = request.args.get("types", "")
    types = [t.strip() for t in types_param.split(",") if t.strip()]
    limit = request.args.get("limit", type=int) or 30
    results = links_records.search_records(query, types=types, limit=limit)
    return jsonify({"results": results})


@links_bp.route("/api/summary")
def record_summary_route():
    type_id = request.args.get("type")
    record_id = request.args.get("id")
    if not type_id or not record_id:
        return jsonify({"error": "missing_params"}), 400
    summary = links_records.get_record_summary(type_id, record_id)
    if not summary:
        return jsonify({"error": "not_found"}), 404
    return jsonify(summary)


@links_bp.route("/api/resolve", methods=["POST"])
def resolve_types_route():
    payload = request.get_json(silent=True) or {}
    context_type = payload.get("context_type") or ""
    src_type = payload.get("src_type") or ""
    dst_types = payload.get("dst_types") or []
    resolved = {}
    for dst_type in dst_types:
        default_type = link_model.default_link_type(context_type, src_type, dst_type)
        allowed = link_model.allowed_link_types(src_type, dst_type)
        resolved[dst_type] = {"default_type": default_type, "allowed_types": allowed}
    return jsonify({"resolved": resolved})


@links_bp.route("/api/bulk", methods=["POST"])
def bulk_create_route():
    _ensure_schema()
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    results = []
    for item in items:
        if item.get("link_type") not in link_model.LINK_TYPE_VOCAB:
            results.append({"created": False, "duplicate": False, "error": "invalid_link_type"})
            continue
        result = link_model.create_link(data._get_conn(), item)
        results.append(result)
    return jsonify({"results": results})
