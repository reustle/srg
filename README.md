SRG Sandbox

## Google basemap

The map uses MapLibre GL JS so the local GeoJSON layers can be rendered over OpenStreetMap Standard, CyclOSM, a light OSM-derived OpenFreeMap style, or Google roadmap tiles. Choose a provider under **Map Style**; all local GeoJSON layers remain visible when the basemap changes.

The Google basemap uses the public browser- and referrer-restricted Map Tiles API key configured in the `google-maps-api-key` meta tag in `index.html`; users are never prompted for credentials.

## License

The original software and documentation in this repository are available under
the [MIT License](LICENSE).

The MIT License does not apply to third-party data, map tiles, styles, or other
materials included in or accessed by this project. Those materials remain
subject to their respective source terms:

- `srt-osm.geojson` contains OpenStreetMap-derived data and is available under
  the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
  Copyright belongs to OpenStreetMap contributors.
- `srg-website-map.geojson`, `srt-scrub-route.geojson`, and files under
  `data/srg-map/` contain or derive from the Schuylkill River Greenways
  interactive map. They are not relicensed under MIT; consult the source
  provider's terms before reuse.
- `2025-Improvement-Map.*` and `2026-Improvement-Map.*` are third-party map
  data and are not relicensed under MIT; consult their source provider's terms
  before reuse.
- `google-places-srt-scan-2026-07-22.geojson` contains Google Maps Platform
  search results and is not relicensed under MIT. Its use is subject to the
  applicable Google Maps Platform terms.
- Basemap tiles, styles, and client libraries loaded at runtime remain under
  their providers' respective terms and licenses.

You may apply CC0 to newly created data only when you own or otherwise have the
authority to waive all applicable rights in that data.
