#!/usr/bin/env python3
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from build_srg_data_geojson import description_fields
from kmz_to_geojson import NS, placemark_geometry, read_kml_from_kmz, text_of


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "srg-data" / "2025-mileage-measurements"
OUTPUT = ROOT / "data" / "srg-data" / "2025-measurements-partial.geojson"

LAYERS = [
    (
        "SRT Alighment.kmz",
        "measurement_alignment",
        "2025 measurement alignment",
    ),
    (
        "SRT_0.10_mile_points_2025.kmz",
        "tenth_mile_points",
        "2025 tenth-mile point",
    ),
    (
        "SRT_0.25_mile_points_2025.kmz",
        "quarter_mile_points",
        "2025 quarter-mile point",
    ),
    (
        "Trailheads_Station_points.kmz",
        "trailhead_stations",
        "2025 trailhead station",
    ),
]


def numeric_field(fields, *names):
    for name in names:
        value = fields.get(name)
        if value is None:
            continue
        try:
            return float(value)
        except ValueError:
            continue
    return None


def normalized_properties(placemark, filename, layer_key, default_name):
    fields = description_fields(text_of(placemark, "description"))
    name = text_of(placemark, "name")
    mile = numeric_field(
        fields,
        "Miles_from_Ft_Mifflin",
        "mile marker",
        "mile",
        "Miles_tenths",
    )
    properties = {
        "source": "SRG data delivery",
        "source_file": f"data/srg-data/2025-mileage-measurements/{filename}",
        "layer": "2025_measurements_partial",
        "measurement_layer": layer_key,
        "partial": True,
        "display_name": name or default_name,
    }

    if mile is not None:
        properties["mile"] = mile
        if not name:
            properties["display_name"] = f"Mile {mile:g}"

    field_map = {
        "Name": "name",
        "County": "county",
        "Municipality": "municipality",
        "Parking": "parking",
    }
    for source_key, target_key in field_map.items():
        value = fields.get(source_key)
        if value is not None:
            properties[target_key] = value
    if properties.get("name"):
        properties["display_name"] = properties["name"]

    shape_length = numeric_field(fields, "SHAPE_Length", "length (ft)")
    if shape_length is not None:
        properties["shape_length_ft"] = shape_length

    return properties


def main():
    features = []
    counts = {}

    for filename, layer_key, default_name in LAYERS:
        root = ET.fromstring(read_kml_from_kmz(SOURCE_DIR / filename))
        placemarks = root.findall(".//kml:Placemark", NS)
        counts[layer_key] = len(placemarks)

        for index, placemark in enumerate(placemarks, start=1):
            geometry = placemark_geometry(placemark)
            if geometry is None:
                continue
            features.append(
                {
                    "type": "Feature",
                    "id": f"srg-data:2025-measurements-partial:{layer_key}:{index}",
                    "properties": normalized_properties(
                        placemark,
                        filename,
                        layer_key,
                        default_name,
                    ),
                    "geometry": geometry,
                }
            )

    collection = {
        "type": "FeatureCollection",
        "name": "SRG 2025 Measurements (Partial)",
        "metadata": {
            "source": "Schuylkill River Greenways data delivery",
            "source_directory": "data/srg-data/2025-mileage-measurements",
            "partial": True,
            "feature_count": len(features),
            "layer_counts": counts,
            "notes": [
                "Completeness and positional accuracy have not been verified.",
                "The tenth-mile series runs from mile 0.0 through 123.2.",
                "The quarter-mile series stops at mile 71.0.",
                "The final quarter-mile points do not align with the supplied measurement line.",
            ],
        },
        "features": features,
    }
    OUTPUT.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(features)} features to {OUTPUT}")


if __name__ == "__main__":
    main()
