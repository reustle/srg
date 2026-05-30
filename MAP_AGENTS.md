# Map Agent Notes

This repo contains map data for Schuylkill River Greenways work. Future agents should treat `srt-osm.geojson` as the working master OSM-derived GeoJSON for the Schuylkill River Trail (SRT).

The official Schuylkill River Greenways interactive map at `https://schuylkillriver.org/map/` is a separate source from OSM. Its derived local export is `srg-website-map.geojson`, and its raw downloaded sources live under `data/srg-map/raw/`.

## Schuylkill River Trail Identity

The canonical trail is the Schuylkill River Trail, abbreviated SRT. In OpenStreetMap (OSM), the trail is represented in two complementary ways:

- Route relations:
  - `relation/1541998`: `name=Schuylkill River Trail`, `route=bicycle`, `ref=SRT`
  - `relation/15062447`: `name=Schuylkill River Trail`, `route=foot`, `ref=SRT`
- Physical ways:
  - Individual trail segments tagged as `highway=cycleway`, `highway=path`, `highway=footway`, or occasionally related access/service ways.

The route relations are the canonical OSM objects for the overall route. The physical ways are the line geometries that render on a map.

Do not assume every OSM object with `ref=SRT` means Schuylkill River Trail. In Pennsylvania, `SRT` can also refer to other trails, including Saucon Rail Trail, Swatara Rail Trail, and Stockertown Rail Trail. Prefer exact route relation names or known relation IDs for canonical membership.

## Local Section Names And Alternate Names

Some physical sections of SRT use local names in OSM. These should remain part of the master SRT file when they are members of the canonical SRT route relations or when a name-like tag identifies them as SRT.

Example:

- `way/588786953`
- `name=Therman Madeira Switchback`
- `alt_name=Schuylkill River Trail`
- Near Kernsville

For these cases, preserve both concepts:

- `trail_name`: always `Schuylkill River Trail`
- `segment_name`: local section name, such as `Therman Madeira Switchback`
- `display_name`: local section name when present, otherwise `Schuylkill River Trail`
- `osm_name`: the current OSM `name` value
- `osm_alt_name`: the current OSM `alt_name` value

Avoid overwriting meaningful local names with `Schuylkill River Trail`. The better OSM pattern is usually to keep the local name in `name`, add SRT in `alt_name` or route relation membership, and ensure the way belongs to the SRT route relation when appropriate.

## Master GeoJSON Format

`srt-osm.geojson` is a `FeatureCollection` of physical OSM ways. Each feature should include strong source references:

- `id`: stable compound ID, for example `osm:way/588786953`
- `osm_type`: usually `way`
- `osm_id`: numeric OSM ID
- `osm_url`: canonical OSM URL
- `osm_tags`: complete OSM tags copied from source data
- `relations`: any canonical SRT route relations that include the way
- `inclusion_reasons`: why the way was included

Top-level `metadata` should record:

- `trail_id`
- `trail_name`
- source and license
- OSM base timestamps
- canonical route relations
- feature count

GeoJSON coordinates must be `[longitude, latitude]`.

## Regenerating `srt-osm.geojson`

The builder is `tools/build_srt_geojson.py`. It expects two Overpass JSON exports:

- Route relation members with geometry
- Named or alt-named SRT ways with geometry

The current intended Overpass patterns are:

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

After saving those payloads, run:

```sh
python3 tools/build_srt_geojson.py \
  --route-json /private/tmp/srt-route-members-overpass.json \
  --named-json /private/tmp/srt-named-ways-overpass.json \
  --output srt-osm.geojson
```

## Official SRG Interactive Map Source

The SRG interactive map page exposes its primary data source in the page HTML:

- `bloginfo.mapjson`
- Current URL: `https://schuylkillriver.org/wp-content/themes/schuylkill2018/data/mapdata.json`

`mapdata.json` contains:

- `trailhead`: point records for trailheads/parking
- `places_to_visit`: point records for places of interest
- `town`: point records for trail towns
- `trail`: four trail layers with KML source paths

The four trail layers currently referenced by `mapdata.json` are:

- Active off-road SRT: `SRT_Existing_Off_Road_2025_v4.0.kml`
- Active on-road SRT: `SRT_Existing_On_Road_2025_v2.kml`
- Proposed off-road SRT: `SRT_Planned_Off_Road_2025.kml`
- Proposed on-road SRT: `SRT_Planned_On_Road_2025.kml`

This is not OSM data. Treat it as the official SRG map source and keep provenance separate from `srt-osm.geojson`.

To refresh the official SRG map export, run:

```sh
python3 tools/fetch_srg_map_data.py
```

The fetcher:

- Downloads the map page, `mapdata.json`, and all KML trail files.
- Writes raw sources under `data/srg-map/raw/`.
- Writes download metadata to `data/srg-map/manifest.json`.
- Builds `srg-website-map.geojson` from all trail lines, trailheads, trail towns, and places to visit.

`srg-website-map.geojson` feature IDs use stable source-derived IDs:

- `srg:trail/{trail_post_id}/placemark/{placemark_index}`
- `srg:trailhead/{source_id}`
- `srg:places_to_visit/{source_id}`
- `srg:town/{source_id}`

Trail feature IDs use the placemark index because the source KML can repeat placemark IDs. The original KML ID is preserved as `placemark_id`, and the index is preserved as `placemark_index`.

Trail features include `status` (`active` or `proposed`) and `alignment` (`off_road` or `on_road`) based on the source layer name. Point features preserve the source `infowindow_html` because that is where the public map stores most display text.

## OSM Update Notes

Use the master file as a review aid, not as an automatic OSM edit source. Before changing OSM:

- Verify the segment on current imagery, official trail maps, or local knowledge.
- Preserve local names when they are real public-facing names.
- Prefer adding route relation membership for SRT identity.
- Use `alt_name=Schuylkill River Trail` only when the segment is genuinely known by both names.
- Avoid broad mechanical edits across the entire trail without manual review.
