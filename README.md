# Schuylkill River Trail Map Sources

An interactive comparison map and working dataset for the Schuylkill River
Trail (SRT). The map brings together OpenStreetMap trail geometry, the official
Schuylkill River Greenways (SRG) map, annual improvement maps, and supporting
research layers so differences between the sources can be inspected in one
place.

This is a static site: no build step or application server is required. Serve
the repository root over HTTP so the browser can load the local GeoJSON files:

```sh
python3 -m http.server 8000
```

Then open <http://localhost:8000>. Opening `index.html` directly with a
`file://` URL will not reliably load the data because of browser security
restrictions.

## Repository layout

```text
index.html       Interactive MapLibre map
data/            GeoJSON, KMZ, downloaded source data, and manifests
  srg-map/raw/   Raw files downloaded from the official SRG map
  srg-data/      SRG source deliveries, organized by year and purpose
tools/           Scripts for fetching and rebuilding map datasets
```

The principal datasets are:

- `data/srt-osm.geojson`: working master of OSM-derived SRT geometry.
- `data/srg-website-map.geojson`: local export of the official SRG interactive
  map, including trails, trailheads, towns, and places to visit.
- `data/srt-scrub-route.geojson`: route geometry used by the map's longitudinal
  scrubber.
- `data/2025-Improvement-Map.*` and `data/2026-Improvement-Map.*`: annual
  improvement maps in source KMZ and converted GeoJSON formats.
- `data/google-places-srt-scan-2026-07-22.geojson`: a point-in-time Google
  Places research layer.
- `data/srg-map/`: raw official-map downloads and their provenance manifest.
- `data/srg-data/`: SRG alignment, mileage, sign-inventory, and
  supporting source files, with an inventory of known completeness issues.
- `data/srg-data/2020-alignment.geojson`: browser-ready export of the four
  supplied 2020 SRG alignment layers used by the explorer's **SRG Data** group.

Generated datasets are checked in so the map works without running the tools.
Run commands from the repository root because script defaults are relative to
it.

## Basemaps

The map uses MapLibre GL JS so local GeoJSON layers can be rendered over
OpenStreetMap Standard, CyclOSM, a light OSM-derived OpenFreeMap style, or
Google roadmap and satellite tiles. Esri World Imagery provides another
satellite and aerial photography option without the Google API. Choose a
provider under **Map Style**; local layers remain visible when the basemap
changes.

The Google basemap uses the public browser- and referrer-restricted Map Tiles
API key configured in the `google-maps-api-key` meta tag in `index.html`; users
are never prompted for credentials. When deploying on a new host, add that
host's referrer to the key restrictions.

When the **Trailheads** layer is enabled, each trailhead point gains a
collision-aware callout with its name and amenity pictograms. The amenity list
is read from that feature's `infowindow_html`, so refreshed SRG exports update
the labels without a separate amenity lookup table.

## Map data notes

### Schuylkill River Trail identity in OSM

The canonical trail is the Schuylkill River Trail, abbreviated SRT. In
OpenStreetMap (OSM), the trail is represented in two complementary ways:

- Route relations:
  - `relation/1541998`: `name=Schuylkill River Trail`, `route=bicycle`,
    `ref=SRT`
  - `relation/15062447`: `name=Schuylkill River Trail`, `route=foot`, `ref=SRT`
- Physical ways: individual trail segments tagged as `highway=cycleway`,
  `highway=path`, `highway=footway`, or occasionally related access/service
  ways.

The route relations are the canonical OSM objects for the overall route. The
physical ways are the line geometries that render on a map.

Do not assume every OSM object with `ref=SRT` means Schuylkill River Trail. In
Pennsylvania, `SRT` can also refer to other trails, including Saucon Rail Trail,
Swatara Rail Trail, and Stockertown Rail Trail. Prefer exact route relation
names or known relation IDs for canonical membership.

### Local section names and alternate names

Some physical sections of SRT use local names in OSM. These should remain part
of the master SRT file when they are members of the canonical SRT route
relations or when a name-like tag identifies them as SRT.

For example, `way/588786953` near Kernsville is named `Therman Madeira
Switchback` and has `alt_name=Schuylkill River Trail`. Preserve both concepts:

- `trail_name`: always `Schuylkill River Trail`
- `segment_name`: local section name, such as `Therman Madeira Switchback`
- `display_name`: local section name when present, otherwise
  `Schuylkill River Trail`
- `osm_name`: the current OSM `name` value
- `osm_alt_name`: the current OSM `alt_name` value

Avoid overwriting meaningful local names with `Schuylkill River Trail`. The
better OSM pattern is usually to keep the local name in `name`, add SRT in
`alt_name` or route relation membership, and ensure the way belongs to the SRT
route relation when appropriate.

### Master GeoJSON format

`data/srt-osm.geojson` is a `FeatureCollection` of physical OSM ways. Each
feature should include strong source references:

- `id`: stable compound ID, for example `osm:way/588786953`
- `osm_type`: usually `way`
- `osm_id`: numeric OSM ID
- `osm_url`: canonical OSM URL
- `osm_tags`: complete OSM tags copied from source data
- `relations`: canonical SRT route relations that include the way
- `inclusion_reasons`: why the way was included

Top-level `metadata` should record `trail_id`, `trail_name`, source and license,
OSM base timestamps, canonical route relations, and feature count. GeoJSON
coordinates must be `[longitude, latitude]`.

## Rebuilding the data

### OSM master

`tools/build_srt_geojson.py` expects two Overpass JSON exports: route relation
members with geometry and named or alt-named SRT ways with geometry. The
intended queries are:

```overpass
[out:json][timeout:180];
area["ISO3166-2"="US-PA"][admin_level=4]->.pa;
relation(area.pa)["type"="route"]["route"~"^(bicycle|foot)$"]["name"="Schuylkill River Trail"]->.routes;
way(r.routes);
out tags geom;
.routes out body;
```

```overpass
[out:json][timeout:180];
area["ISO3166-2"="US-PA"][admin_level=4]->.pa;
(
  way(area.pa)["highway"]["name"~"(Schuylkill River Trail|\\bSRT\\b)",i];
  way(area.pa)["highway"]["alt_name"~"(Schuylkill River Trail|\\bSRT\\b)",i];
  way(area.pa)["highway"]["official_name"~"(Schuylkill River Trail|\\bSRT\\b)",i];
  way(area.pa)["highway"]["loc_name"~"(Schuylkill River Trail|\\bSRT\\b)",i];
  way(area.pa)["highway"]["ref"~"\\bSRT\\b",i];
);
out tags geom;
```

After saving the payloads, run:

```sh
python3 tools/build_srt_geojson.py \
  --route-json /path/to/srt-route-members-overpass.json \
  --named-json /path/to/srt-named-ways-overpass.json
```

The default output is `data/srt-osm.geojson`.

### Official SRG interactive map

The official map at <https://schuylkillriver.org/map/> exposes its primary data
source as `bloginfo.mapjson`. Its current URL is
<https://schuylkillriver.org/wp-content/themes/schuylkill2018/data/mapdata.json>.
This is separate from OSM and its provenance should remain separate.

`mapdata.json` contains point records for `trailhead`, `places_to_visit`, and
`town`, plus four trail layers whose current KML sources are:

- Active off-road: `SRT_Existing_Off_Road_2025_v4.0.kml`
- Active on-road: `SRT_Existing_On_Road_2025_v2.kml`
- Proposed off-road: `SRT_Planned_Off_Road_2025.kml`
- Proposed on-road: `SRT_Planned_On_Road_2025.kml`

Refresh the local export with:

```sh
python3 tools/fetch_srg_map_data.py
```

To regenerate only the GeoJSON from the checked-in raw downloads, without
network access:

```sh
python3 tools/fetch_srg_map_data.py --use-existing
```

The fetcher downloads the map page, `mapdata.json`, and referenced KML files to
`data/srg-map/raw/`; writes download metadata to
`data/srg-map/manifest.json`; and rebuilds `data/srg-website-map.geojson`.

Exported feature IDs are stable and source-derived:

- `srg:trail/{trail_post_id}/placemark/{placemark_index}`
- `srg:trailhead/{source_id}`
- `srg:places_to_visit/{source_id}`
- `srg:town/{source_id}`

Trail IDs use the placemark index because source KML can repeat placemark IDs.
The original KML ID and index remain in `placemark_id` and `placemark_index`.
Trail features include `status` (`active` or `proposed`) and `alignment`
(`off_road` or `on_road`). Point features retain `infowindow_html`, where the
public map stores most display text.

### Supplied SRG alignment

Rebuild the browser-ready 2020 alignment after replacing any source KML under
`data/srg-data/2020-alignment/`:

```sh
python3 tools/build_srg_data_geojson.py
```

The output is `data/srg-data/2020-alignment.geojson`, displayed as the separate
**SRG Data** layer group in the explorer.

### Scrubber route

Rebuild the longitudinal route used by the map scrubber after refreshing the
official data:

```sh
python3 tools/build_srt_scrub_route.py
```

It reads `data/srg-website-map.geojson` and writes
`data/srt-scrub-route.geojson` by default.

## OSM editing guidance

Use the master file as a review aid, not as an automatic OSM edit source.
Before changing OSM:

- Verify the segment on current imagery, official trail maps, or local
  knowledge.
- Preserve real public-facing local names.
- Prefer route relation membership for SRT identity.
- Use `alt_name=Schuylkill River Trail` only when the segment is genuinely
  known by both names.
- Avoid broad mechanical edits across the trail without manual review.

## License and data terms

The original software and documentation in this repository are available under
the [MIT License](LICENSE).

The MIT License does not apply to third-party data, map tiles, styles, or other
materials included in or accessed by this project. Those materials remain
subject to their respective source terms:

- `data/srt-osm.geojson` contains OpenStreetMap-derived data and is available
  under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
  Copyright belongs to OpenStreetMap contributors.
- `data/srg-website-map.geojson`, `data/srt-scrub-route.geojson`, and files
  under `data/srg-map/` contain or derive from the SRG interactive map. They are
  not relicensed under MIT; consult the source provider's terms before reuse.
- `data/2025-Improvement-Map.*` and `data/2026-Improvement-Map.*` are
  third-party map data and are not relicensed under MIT.
- `data/google-places-srt-scan-2026-07-22.geojson` contains Google Maps
  Platform search results and is subject to the applicable Google Maps
  Platform terms, not the MIT License.
- Basemap tiles, styles, and client libraries loaded at runtime remain under
  their providers' respective terms and licenses.

Apply CC0 to newly created data only when you own or otherwise have authority
to waive all applicable rights in that data.
