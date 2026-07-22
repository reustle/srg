SRG Sandbox

## Google basemap

The map uses MapLibre GL JS so the local GeoJSON layers can be rendered over OpenStreetMap Standard, CyclOSM, a light OSM-derived OpenFreeMap style, or Google roadmap tiles. Choose a provider under **Map Style**; all local GeoJSON layers remain visible when the basemap changes.

The Google basemap uses the public browser- and referrer-restricted Map Tiles API key configured in the `google-maps-api-key` meta tag in `index.html`; users are never prompted for credentials.
