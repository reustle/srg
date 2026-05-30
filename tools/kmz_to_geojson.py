#!/usr/bin/env python3
import argparse
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "gx": "http://www.google.com/kml/ext/2.2",
}


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def text_of(parent, name):
    child = parent.find(f"kml:{name}", NS)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def parse_coordinates(text):
    coords = []
    for chunk in re.split(r"\s+", (text or "").strip()):
        if not chunk:
            continue
        parts = chunk.split(",")
        if len(parts) < 2:
            continue
        point = [float(parts[0]), float(parts[1])]
        if len(parts) > 2 and parts[2] != "":
            altitude = float(parts[2])
            if altitude != 0:
                point.append(altitude)
        coords.append(point)
    return coords


def coordinates_for(el):
    coord_el = el.find("kml:coordinates", NS)
    return parse_coordinates(coord_el.text if coord_el is not None else "")


def linearring_coordinates(el):
    ring = el.find("kml:LinearRing", NS)
    return coordinates_for(ring) if ring is not None else []


def geometry_for(el):
    tag = local_name(el.tag)

    if tag == "Point":
        coords = coordinates_for(el)
        return {"type": "Point", "coordinates": coords[0]} if coords else None

    if tag == "LineString":
        return {"type": "LineString", "coordinates": coordinates_for(el)}

    if tag == "Polygon":
        rings = []
        outer = el.find("kml:outerBoundaryIs", NS)
        if outer is not None:
            rings.append(linearring_coordinates(outer))
        for inner in el.findall("kml:innerBoundaryIs", NS):
            rings.append(linearring_coordinates(inner))
        return {"type": "Polygon", "coordinates": rings}

    if tag == "MultiGeometry":
        geometries = []
        for child in list(el):
            geom = geometry_for(child)
            if geom is not None:
                geometries.append(geom)
        if not geometries:
            return None
        types = {geom["type"] for geom in geometries}
        if types == {"Point"}:
            return {
                "type": "MultiPoint",
                "coordinates": [geom["coordinates"] for geom in geometries],
            }
        if types == {"LineString"}:
            return {
                "type": "MultiLineString",
                "coordinates": [geom["coordinates"] for geom in geometries],
            }
        if types == {"Polygon"}:
            return {
                "type": "MultiPolygon",
                "coordinates": [geom["coordinates"] for geom in geometries],
            }
        return {"type": "GeometryCollection", "geometries": geometries}

    return None


def placemark_geometry(placemark):
    for child in list(placemark):
        if local_name(child.tag) in {"Point", "LineString", "Polygon", "MultiGeometry"}:
            return geometry_for(child)
    return None


def extended_data(placemark):
    data = {}
    ext = placemark.find("kml:ExtendedData", NS)
    if ext is None:
        return data

    for item in ext.findall(".//kml:Data", NS):
        key = item.attrib.get("name")
        value = text_of(item, "value")
        if key and value is not None:
            data[key] = value

    for item in ext.findall(".//kml:SimpleData", NS):
        key = item.attrib.get("name")
        value = item.text.strip() if item.text else None
        if key and value is not None:
            data[key] = value

    return data


def feature_for(placemark, folder_path):
    props = {}
    name = text_of(placemark, "name")
    if name is not None:
        props["name"] = name

    description = text_of(placemark, "description")
    if description is not None:
        props["description"] = description

    style_url = text_of(placemark, "styleUrl")
    if style_url is not None:
        props["styleUrl"] = style_url

    if folder_path:
        props["folder"] = folder_path[-1]
        props["folder_path"] = " / ".join(folder_path)

    props.update(extended_data(placemark))

    return {
        "type": "Feature",
        "properties": props,
        "geometry": placemark_geometry(placemark),
    }


def walk_features(el, folder_path):
    features = []
    for child in list(el):
        tag = local_name(child.tag)
        if tag == "Folder":
            folder_name = text_of(child, "name")
            child_path = folder_path + ([folder_name] if folder_name else [])
            features.extend(walk_features(child, child_path))
        elif tag == "Placemark":
            features.append(feature_for(child, folder_path))
        elif tag == "Document":
            features.extend(walk_features(child, folder_path))
    return features


def read_kml_from_kmz(path):
    with zipfile.ZipFile(path) as kmz:
        kml_names = [name for name in kmz.namelist() if name.lower().endswith(".kml")]
        if not kml_names:
            raise ValueError(f"No KML file found in {path}")
        with kmz.open(kml_names[0]) as fh:
            return fh.read()


def main():
    parser = argparse.ArgumentParser(description="Convert a KMZ/KML file to GeoJSON.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.input.suffix.lower() == ".kmz":
        raw = read_kml_from_kmz(args.input)
    else:
        raw = args.input.read_bytes()

    root = ET.fromstring(raw)
    features = walk_features(root, [])
    collection = {"type": "FeatureCollection", "features": features}
    args.output.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(features)} features to {args.output}")


if __name__ == "__main__":
    main()
