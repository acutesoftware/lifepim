# Local Places map data

The Places map uses these files locally and makes no request to a map or tile
service at runtime.

The data is derived from Natural Earth 5.1.2 at 1:50m (land, lakes and country
boundaries) and 1:10m (populated places). Natural Earth data is public domain:
https://www.naturalearthdata.com/about/terms-of-use/

Run `python scripts/build_local_map_data.py` from the repository root to rebuild
the compact JSON files from the pinned upstream revision.
