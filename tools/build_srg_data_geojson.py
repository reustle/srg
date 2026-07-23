#!/usr/bin/env python3
import html
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from kmz_to_geojson import NS, placemark_geometry, text_of


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "srg-data" / "2020-alignment"
OUTPUT = ROOT / "data" / "srg-data" / "2020-alignment.geojson"

LAYERS = [
    ("SRT_Existing_Off_Road_2020.kml", "existing_off_road", "existing", "off_road"),
    ("SRT_Existing_On_Road_2020.kml", "existing_on_road", "existing", "on_road"),
    ("SRT_Planned_Off_Road_2020.kml", "planned_off_road", "planned", "off_road"),
    ("SRT_Planned_On_Road_2020.kml", "planned_on_road", "planned", "on_road"),
]


def parse_kml(path):
    raw = path.read_text(encoding="utf-8")
    if "xsi:schemaLocation" in raw and "xmlns:xsi=" not in raw:
        raw = raw.replace(
            "<kml ",
            '<kml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ',
            1,
        )
    return ET.fromstring(raw)


def clean_html(value):
    return " ".join(
        html.unescape(re.sub(r"<[^>]+>", " ", value)).split()
    )


def description_fields(description):
    if not description:
        return {}

    decoded = html.unescape(description)
    fields = {}
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", decoded, flags=re.I | re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.I | re.S)
        if len(cells) != 2:
            continue
        key, value = (clean_html(cell) for cell in cells)
        if key and value and value not in {"<Null>", "&lt;Null&gt;"}:
            fields[key] = value
    return fields


def normalized_properties(placemark, filename, layer_key, status, alignment):
    description = text_of(placemark, "description")
    source_fields = description_fields(description)
    class_label = f"{status.title()} {alignment.replace('_', '-')}"
    properties = {
        "source": "SRG data delivery",
        "source_file": f"data/srg-data/2020-alignment/{filename}",
        "layer": "2020_alignment",
        "alignment_class": layer_key,
        "status": status,
        "alignment": alignment,
        "display_name": f"{class_label} segment",
    }

    name = text_of(placemark, "name")
    if name:
        properties["name"] = name
        if not re.fullmatch(r"-?\d+(?:\.\d+)?", name):
            properties["display_name"] = name
    field_map = {
        "OWNER": "owner",
        "Owner": "owner",
        "County": "county",
        "Municipality": "municipality",
        "Prop_Interest": "property_interest",
        "SHAPE_Length": "shape_length_ft",
        "miles2": "length_miles",
    }
    for source_key, target_key in field_map.items():
        value = source_fields.get(source_key)
        if value is None:
            continue
        if target_key in {"shape_length_ft", "length_miles"}:
            try:
                value = float(value)
            except ValueError:
                pass
        properties[target_key] = value

    return properties


def main():
    features = []
    counts = {}

    for filename, layer_key, status, alignment in LAYERS:
        path = SOURCE_DIR / filename
        root = parse_kml(path)
        placemarks = root.findall(".//kml:Placemark", NS)
        counts[layer_key] = len(placemarks)

        for index, placemark in enumerate(placemarks, start=1):
            geometry = placemark_geometry(placemark)
            if geometry is None:
                continue
            features.append(
                {
                    "type": "Feature",
                    "id": f"srg-data:2020-alignment:{layer_key}:{index}",
                    "properties": normalized_properties(
                        placemark, filename, layer_key, status, alignment
                    ),
                    "geometry": geometry,
                }
            )

    collection = {
        "type": "FeatureCollection",
        "name": "SRG 2020 Alignment",
        "metadata": {
            "source": "Schuylkill River Greenways data delivery",
            "source_directory": "data/srg-data/2020-alignment",
            "feature_count": len(features),
            "layer_counts": counts,
            "notes": [
                "Generated from the four supplied 2020 alignment KML files.",
                "The missing xsi namespace in the source KML is repaired while parsing.",
            ],
        },
        "features": features,
    }
    OUTPUT.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(features)} features to {OUTPUT}")


if __name__ == "__main__":
    main()
