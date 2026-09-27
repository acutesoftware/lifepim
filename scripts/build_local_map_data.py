#!/usr/bin/env python3
"""Build the small, browser-ready Natural Earth files used by Places maps."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen


NATURAL_EARTH_VERSION = "5.1.2"
NATURAL_EARTH_REF = "f1890d9f152c896d250a77557a5751a93d494776"
SOURCE_ROOT = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    f"{NATURAL_EARTH_REF}/geojson"
)
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "src" / "static" / "map_data"

SOURCES = {
    # The overview disappears behind local street detail at close zoom levels,
    # so 110m geometry is both sufficient and much faster to redraw.
    "land": "ne_110m_land.geojson",
    "lakes": "ne_110m_lakes.geojson",
    "boundaries": "ne_110m_admin_0_boundary_lines_land.geojson",
    "countries": "ne_50m_admin_0_countries.geojson",
    "towns": "ne_10m_populated_places_simple.geojson",
}


def download_geojson(filename: str) -> dict:
    request = Request(
        f"{SOURCE_ROOT}/{filename}",
        headers={"User-Agent": "LifePIM-local-map-data-builder/1.0"},
    )
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def geometries(collection: dict) -> list[dict]:
    return [feature["geometry"] for feature in collection.get("features", [])]


def coordinate_bounds(geometry: dict) -> list[float] | None:
    points = []

    def collect(value):
        if value and isinstance(value[0], (int, float)):
            points.append(value)
            return
        for child in value:
            collect(child)

    collect(geometry.get("coordinates") or [])
    if not points:
        return None
    longitudes = [float(point[0]) for point in points]
    latitudes = [float(point[1]) for point in points]
    return [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]


def build() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_data = {name: download_geojson(filename) for name, filename in SOURCES.items()}

    countries = []
    for feature in source_data["countries"].get("features", []):
        properties = feature.get("properties") or {}
        name = properties.get("NAME_EN") or properties.get("NAME") or properties.get("ADMIN")
        bounds = coordinate_bounds(feature.get("geometry") or {})
        if name and bounds:
            countries.append([str(name), *[round(value, 5) for value in bounds]])
    countries.sort(key=lambda country: country[0].casefold())

    base = {
        "naturalEarthVersion": NATURAL_EARTH_VERSION,
        "land": geometries(source_data["land"]),
        "lakes": geometries(source_data["lakes"]),
        "boundaries": geometries(source_data["boundaries"]),
        "countries": countries,
    }
    towns = []
    for feature in source_data["towns"].get("features", []):
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if geometry.get("type") != "Point" or len(coordinates) < 2:
            continue
        properties = feature.get("properties") or {}
        name = properties.get("name") or properties.get("nameascii")
        if not name:
            continue
        towns.append(
            [
                round(float(coordinates[0]), 5),
                round(float(coordinates[1]), 5),
                str(name),
                int(properties.get("scalerank") or 10),
                int(properties.get("pop_max") or 0),
            ]
        )

    json_options = {"ensure_ascii": False, "separators": (",", ":")}
    (OUTPUT_DIR / "natural_earth_base.json").write_text(
        json.dumps(base, **json_options), encoding="utf-8"
    )
    (OUTPUT_DIR / "natural_earth_towns.json").write_text(
        json.dumps(towns, **json_options), encoding="utf-8"
    )
    print(
        f"Wrote {len(towns)} towns, {len(countries)} country extents, "
        f"and local base-map geometry to {OUTPUT_DIR}"
    )


if __name__ == "__main__":
    build()
