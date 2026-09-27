"""Download and query optional offline OpenStreetMap GeoPackage snapshots."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import struct
import threading
from urllib.request import Request, urlopen
import zipfile

from common import settings as settings_mod


PACKS = {
    "new-south-wales": {"label": "New South Wales (including ACT)", "download_mb": 511.0},
    "northern-territory": {"label": "Northern Territory", "download_mb": 35.5},
    "queensland": {"label": "Queensland", "download_mb": 369.5},
    "south-australia": {"label": "South Australia", "download_mb": 143.9},
    "tasmania": {"label": "Tasmania", "download_mb": 133.7},
    "victoria": {"label": "Victoria", "download_mb": 441.4},
    "western-australia": {"label": "Western Australia", "download_mb": 251.6},
}
SCOPE_PACKS = {
    "sa": ["south-australia"],
    "au": list(PACKS),
}
SOURCE_ROOT = "https://download.geofabrik.de/australia-oceania/australia"
INDEX_VERSION = 1

DETAIL_LAYERS = {
    "roads": ("gis_osm_roads_free", 1, 3500),
    "railways": ("gis_osm_railways_free", 1, 1200),
    "waterways": ("gis_osm_waterways_free", 1, 1800),
    "places": ("gis_osm_places_free", 1, 800),
    "landuse": ("gis_osm_landuse_a_free", 2, 1500),
    "water": ("gis_osm_water_a_free", 2, 1800),
    "buildings": ("gis_osm_buildings_a_free", 3, 3000),
}

_download_lock = threading.RLock()
_download_state = {
    "running": False,
    "scope": "",
    "pack": "",
    "phase": "idle",
    "downloaded": 0,
    "total": 0,
    "message": "",
    "error": "",
    "cache_dir": "",
}


def cache_dir() -> Path:
    root = Path(settings_mod.places_map_cache_dir())
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cache_root(root=None) -> Path:
    path = Path(root) if root is not None else cache_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def pack_path(pack_name: str, root=None) -> Path:
    return _cache_root(root) / f"{pack_name}.gpkg"


def manifest_path(pack_name: str, root=None) -> Path:
    return _cache_root(root) / f"{pack_name}.json"


def download_dir(root=None) -> Path:
    path = _cache_root(root) / ".downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_manifest(pack_name: str, root=None) -> dict:
    path = manifest_path(pack_name, root)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def installed_packs(root=None) -> list[dict]:
    root = _cache_root(root)
    installed = []
    for pack_name, spec in PACKS.items():
        path = pack_path(pack_name, root)
        if not path.is_file():
            continue
        manifest = _read_manifest(pack_name, root)
        installed.append(
            {
                "id": pack_name,
                "label": spec["label"],
                "size": path.stat().st_size,
                "installed_at": manifest.get("installed_at", ""),
                "bounds": manifest.get("bounds") or [],
            }
        )
    return installed


def status() -> dict:
    with _download_lock:
        current = dict(_download_state)
    root = _cache_root(current["cache_dir"]) if current["running"] and current["cache_dir"] else cache_dir()
    current["installed"] = installed_packs(root)
    current["cache_dir"] = str(root)
    current["sa_download_mb"] = PACKS["south-australia"]["download_mb"]
    current["au_download_mb"] = round(sum(spec["download_mb"] for spec in PACKS.values()), 1)
    return current


def start_download(scope: str) -> tuple[bool, str]:
    if scope not in SCOPE_PACKS:
        return False, "Unknown offline-map scope."
    root = cache_dir()
    with _download_lock:
        if _download_state["running"]:
            return False, "A map download is already running."
        _download_state.update(
            running=True,
            scope=scope,
            pack="",
            phase="starting",
            downloaded=0,
            total=0,
            message="Preparing offline map download…",
            error="",
            cache_dir=str(root),
        )
    worker = threading.Thread(target=_download_worker, args=(scope, root), daemon=True)
    worker.start()
    return True, "Offline map download started."


def _set_state(**values) -> None:
    with _download_lock:
        _download_state.update(values)


def _download_worker(scope: str, root: Path) -> None:
    try:
        wanted = SCOPE_PACKS[scope]
        missing = [pack for pack in wanted if not pack_path(pack, root).is_file()]
        if not missing:
            _set_state(message="The requested offline map pack is already installed.")
            return
        # Allow for both the compressed archive and the larger extracted
        # GeoPackage to coexist while each pack is installed.
        required_bytes = int(sum(PACKS[pack]["download_mb"] for pack in missing) * 1024 * 1024 * 3.5)
        if shutil.disk_usage(root).free < required_bytes:
            raise RuntimeError("Not enough free disk space for the selected offline map pack.")
        for pack_name in missing:
            _download_pack(pack_name, root)
        _set_state(phase="complete", message="Offline street-map data is ready.")
    except Exception as exc:
        _set_state(phase="failed", error=str(exc), message="Offline map download failed.")
    finally:
        _set_state(running=False, pack="", downloaded=0, total=0)


def _download_pack(pack_name: str, root: Path) -> None:
    target = pack_path(pack_name, root)
    temporary_dir = download_dir(root)
    archive = temporary_dir / f"{pack_name}.gpkg.zip.part"
    extracted = temporary_dir / f"{pack_name}.gpkg.part"
    archive.unlink(missing_ok=True)
    extracted.unlink(missing_ok=True)
    url = f"{SOURCE_ROOT}/{pack_name}-latest-free.gpkg.zip"
    _set_state(pack=pack_name, phase="downloading", message=f"Downloading {PACKS[pack_name]['label']}…")
    request = Request(url, headers={"User-Agent": "LifePIM-offline-map-downloader/1.0"})
    with urlopen(request, timeout=90) as response, archive.open("wb") as output:
        total = int(response.headers.get("Content-Length") or 0)
        _set_state(total=total, downloaded=0)
        downloaded = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            downloaded += len(chunk)
            _set_state(downloaded=downloaded)

    _set_state(phase="extracting", message=f"Extracting {PACKS[pack_name]['label']}…")
    with zipfile.ZipFile(archive) as zipped:
        members = [member for member in zipped.infolist() if member.filename.lower().endswith(".gpkg")]
        if len(members) != 1:
            raise RuntimeError("The downloaded archive did not contain one GeoPackage file.")
        with zipped.open(members[0]) as source, extracted.open("wb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)
    archive.unlink(missing_ok=True)

    _set_state(phase="indexing", message=f"Indexing {PACKS[pack_name]['label']} for local zoom…")
    _ensure_spatial_indexes(extracted)
    bounds = _package_bounds(extracted)
    os.replace(extracted, target)
    manifest = {
        "pack": pack_name,
        "source": url,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "bounds": bounds,
        "index_version": INDEX_VERSION,
    }
    manifest_path(pack_name, root).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _package_bounds(path: Path) -> list[float]:
    with closing(sqlite3.connect(path)) as conn:
        row = conn.execute(
            "SELECT MIN(min_x), MIN(min_y), MAX(max_x), MAX(max_y) "
            "FROM gpkg_contents WHERE data_type = 'features'"
        ).fetchone()
    return [float(value) for value in row] if row and all(value is not None for value in row) else []


def _geometry_envelope(blob: bytes) -> tuple[float, float, float, float] | None:
    if not blob or len(blob) < 9 or blob[:2] != b"GP":
        return None
    flags = blob[3]
    byte_order = "<" if flags & 1 else ">"
    envelope_code = (flags >> 1) & 7
    envelope_values = {0: 0, 1: 4, 2: 6, 3: 6, 4: 8}.get(envelope_code, 0)
    if envelope_values >= 4:
        min_x, max_x, min_y, max_y = struct.unpack_from(byte_order + "dddd", blob, 8)
        return min_x, max_x, min_y, max_y
    geometry = _decode_gpkg_geometry(blob)
    points = list(_coordinate_points(geometry.get("coordinates") if geometry else []))
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), max(xs), min(ys), max(ys)


def _ensure_spatial_indexes(path: Path) -> None:
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA journal_mode=MEMORY")
        for _layer_name, (table_name, _detail, _limit) in DETAIL_LAYERS.items():
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
            ).fetchone()
            if not exists:
                continue
            index_name = f"lifepim_rtree_{table_name}"
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {index_name} USING rtree(id, minx, maxx, miny, maxy)"
            )
            indexed = conn.execute(f"SELECT COUNT(*) FROM {index_name}").fetchone()[0]
            total = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            if indexed == total:
                continue
            conn.execute(f"DELETE FROM {index_name}")
            batch = []
            for feature_id, geometry in conn.execute(f"SELECT fid, geom FROM {table_name}"):
                envelope = _geometry_envelope(geometry)
                if envelope:
                    batch.append((feature_id, *envelope))
                if len(batch) >= 5000:
                    conn.executemany(f"INSERT INTO {index_name} VALUES (?, ?, ?, ?, ?)", batch)
                    batch.clear()
            if batch:
                conn.executemany(f"INSERT INTO {index_name} VALUES (?, ?, ?, ?, ?)", batch)
            conn.commit()


def _coordinate_points(value):
    if not value:
        return
    if isinstance(value[0], (int, float)):
        yield value
        return
    for child in value:
        yield from _coordinate_points(child)


class _WkbReader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def unpack(self, fmt: str, byte_order: str):
        size = struct.calcsize(fmt)
        value = struct.unpack_from(byte_order + fmt, self.data, self.offset)
        self.offset += size
        return value

    def geometry(self) -> dict:
        byte_order = "<" if self.unpack("B", "<")[0] == 1 else ">"
        raw_type = self.unpack("I", byte_order)[0]
        geometry_type = raw_type % 1000
        dimensions = 3 if 1000 <= raw_type < 2000 else 2
        if geometry_type == 1:
            return {"type": "Point", "coordinates": list(self.unpack("d" * dimensions, byte_order)[:2])}
        if geometry_type == 2:
            count = self.unpack("I", byte_order)[0]
            return {
                "type": "LineString",
                "coordinates": [list(self.unpack("d" * dimensions, byte_order)[:2]) for _ in range(count)],
            }
        if geometry_type == 3:
            ring_count = self.unpack("I", byte_order)[0]
            rings = []
            for _ in range(ring_count):
                point_count = self.unpack("I", byte_order)[0]
                rings.append([list(self.unpack("d" * dimensions, byte_order)[:2]) for _ in range(point_count)])
            return {"type": "Polygon", "coordinates": rings}
        child_type = {4: "MultiPoint", 5: "MultiLineString", 6: "MultiPolygon", 7: "GeometryCollection"}.get(geometry_type)
        if child_type:
            count = self.unpack("I", byte_order)[0]
            children = [self.geometry() for _ in range(count)]
            if child_type == "GeometryCollection":
                return {"type": child_type, "geometries": children}
            return {"type": child_type, "coordinates": [child["coordinates"] for child in children]}
        raise ValueError(f"Unsupported WKB geometry type {raw_type}")


def _decode_gpkg_geometry(blob: bytes) -> dict | None:
    if not blob or blob[:2] != b"GP":
        return None
    flags = blob[3]
    envelope_code = (flags >> 1) & 7
    envelope_values = {0: 0, 1: 4, 2: 6, 3: 6, 4: 8}.get(envelope_code, 0)
    offset = 8 + envelope_values * 8
    try:
        return _WkbReader(blob[offset:]).geometry()
    except (ValueError, IndexError, struct.error):
        return None


def query_features(bounds: tuple[float, float, float, float], detail: int) -> dict:
    min_x, min_y, max_x, max_y = bounds
    result = {name: [] for name in DETAIL_LAYERS}
    result["truncated"] = []
    for pack in installed_packs():
        pack_bounds = pack.get("bounds") or []
        if len(pack_bounds) == 4 and (
            max_x < pack_bounds[0] or min_x > pack_bounds[2] or
            max_y < pack_bounds[1] or min_y > pack_bounds[3]
        ):
            continue
        path = pack_path(pack["id"])
        with closing(sqlite3.connect(path)) as conn:
            for layer_name, (table_name, minimum_detail, limit) in DETAIL_LAYERS.items():
                if detail < minimum_detail:
                    continue
                index_name = f"lifepim_rtree_{table_name}"
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (index_name,)
                ).fetchone()
                if not exists:
                    continue
                class_filter = ""
                parameters = [min_x, max_x, min_y, max_y]
                if layer_name == "roads" and detail == 1:
                    class_filter = " AND t.fclass IN ('motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link')"
                elif layer_name == "roads" and detail == 2:
                    class_filter = " AND t.fclass NOT IN ('footway','path','steps','cycleway','bridleway','service')"
                rows = conn.execute(
                    f"SELECT t.geom, t.fclass, t.name FROM {table_name} t "
                    f"JOIN {index_name} r ON r.id=t.fid "
                    "WHERE r.maxx>=? AND r.minx<=? AND r.maxy>=? AND r.miny<=?"
                    f"{class_filter} LIMIT ?",
                    (*parameters, limit + 1),
                ).fetchall()
                if len(rows) > limit:
                    result["truncated"].append(layer_name)
                    rows = rows[:limit]
                for geometry_blob, feature_class, name in rows:
                    geometry = _decode_gpkg_geometry(geometry_blob)
                    if geometry:
                        result[layer_name].append(
                            {"g": geometry, "c": feature_class or "", "n": name or ""}
                        )
    return result
