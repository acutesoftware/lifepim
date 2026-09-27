# Places Tab

The Places tab stores locations that the user may navigate to. A Place can be:

- an Earth location with an address and GPS coordinates;
- a location in a configured virtual world; or
- an Internet location represented by a URL.

All Place types remain in the `lp_places` table. The type controls which fields
and actions are shown; it does not create a separate map or bookmark database.

## Earth map

`Places -> Map` has two local map layers:

1. A small world overview made from Natural Earth data bundled under
   `src/static/map_data`. It works immediately and never contacts a map server.
2. Optional OpenStreetMap street detail downloaded as GeoPackage files from
   Geofabrik. Once downloaded, these files are read locally and no network
   request is made while viewing or zooming the map.

Saved Places are drawn from their latitude and longitude. Use the Country or
Saved place selectors to move to an area. The mouse wheel zooms around the
pointer, double-click zooms in, and holding the left mouse button pans the map.
The `+`, `-`, home, and world buttons provide the equivalent basic controls.

At wider views the map shows the bundled overview. As the view becomes smaller,
downloaded detail is progressively added:

- major roads, railways, waterways, and locality names;
- smaller roads, land use, and water; then
- local roads and building outlines at close zoom levels.

The map requests only the features inside the current viewport from LifePIM's
local server. The server reads those features directly from SQLite/GeoPackage
spatial indexes and returns them to the browser as geometry for the local SVG
map. No third-party API is involved in this display path.

## Places map menu

The `Places [...]` menu above the map provides:

- **Enable/disable downloaded street detail** - controls whether installed
  GeoPackages are queried. It is off by default. The bundled overview remains
  available in either state.
- **Download/cache South Australia** - installs the South Australia package.
  The download is about 144 MB and the extracted data is about 302 MB.
- **Download/cache Australia** - installs seven regional packages covering the
  Australian states and mainland territories. The download is about 1.9 GB and
  normally requires about 4-5 GB after extraction.

Downloads start only after confirmation and run in a background thread. The map
page shows download and extraction progress. Existing packages are skipped when
an Australia download is requested, so installing South Australia first does
not download it twice.

The source archives use OpenStreetMap data distributed by Geofabrik under the
Open Database License. Package URLs use Geofabrik's `latest-free.gpkg.zip`
snapshots. An installed snapshot continues to work if the computer is offline
or the remote download service later changes.

## Storage location

The map storage root is configured under:

```text
Settings -> Places -> Offline Map Storage -> Map cache directory
```

The default is:

```text
<LifePIM data folder>/MapCache/places
```

The directory must be outside the LifePIM source/Git repository. LifePIM rejects
a path inside the repository so large map databases and partial downloads cannot
be accidentally committed.

For managed or portable installations, the environment variable below overrides
the saved setting:

```text
LIFEPIM_MAP_CACHE_DIR
```

The selected root contains:

```text
places/
|-- south-australia.gpkg       installed feature data
|-- south-australia.json       source, bounds, and install metadata
|-- other-region.gpkg
|-- other-region.json
`-- .downloads/                temporary archives and extraction files
```

Temporary files use a `.part` suffix and are never created in the source tree.
A retry replaces stale `.part` files for that package. Completed GeoPackages are
moved atomically into the storage root after their local spatial indexes have
been built.

To move an existing cache:

1. Stop any active map download.
2. Move the entire configured map-cache directory to the new external location.
3. Change the directory under Settings -> Places and save.
4. Reload the Places map.

Changing the setting does not automatically move existing files. It switches
LifePIM to the packages found in the new directory.

## Optional external maps

Clicking a saved marker shows links for Google Maps, Google Street View, and
OpenStreetMap. These are ordinary optional URLs and open in a separate browser
tab. They are not used to draw the LifePIM map and are the only map actions that
contact those external services.

## Limits and maintenance

- The local renderer is intentionally simpler than a full online mapping site.
- Geocoding an address may still require the separately configured geocoding
  service; viewing a saved coordinate does not.
- Map packages are snapshots. A future refresh can be implemented by replacing
  or removing a package and downloading the current snapshot again.
- Deleting an installed `.gpkg` and its matching `.json` file removes that
  region from the local cache. Do this only while no download is active.

The implementation is primarily in:

- `src/modules/places/local_maps.py` - download, storage, indexing, and queries;
- `src/modules/places/routes.py` - local map HTTP endpoints;
- `src/static/places_local_map.js` - browser rendering and interaction; and
- `src/modules/places/templates/places_list_map.html` - map controls and menu.
