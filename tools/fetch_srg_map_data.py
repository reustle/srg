#!/usr/bin/env python3
"""Fetch the official SRG interactive map source data and build GeoJSON."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse


MAP_PAGE_URL = "https://schuylkillriver.org/map/"
DEFAULT_OUT_DIR = Path("data/srg-map")
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}
POINT_LAYERS = ("trailhead", "places_to_visit", "town")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch_url(url: str) -> tuple[bytes, dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "srg-map-fetcher/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read(), dict(response.headers.items())


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def discover_mapjson_url(page_html: str, page_url: str) -> str:
    match = re.search(r'"mapjson"\s*:\s*"([^"]+)"', page_html)
    if not match:
        raise RuntimeError("Could not find bloginfo.mapjson in the map page HTML")
    return urljoin(page_url, match.group(1).replace("\\/", "/"))


def safe_filename_from_url(url: str) -> str:
    name = Path(urlparse(url).path).name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name) or "download"


def absolute_url(base_url: str, maybe_url: str) -> str:
    return urljoin(base_url, maybe_url)


def parse_coordinates(text: str | None) -> list[list[float]]:
    coordinates = []
    for token in (text or "").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        coordinates.append([float(parts[0]), float(parts[1])])
    return coordinates


def child_text(element: ET.Element, name: str) -> str | None:
    child = element.find(f"kml:{name}", KML_NS)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def placemark_geometry(placemark: ET.Element) -> dict | None:
    lines = [
        parse_coordinates(node.text)
        for node in placemark.findall(".//kml:LineString/kml:coordinates", KML_NS)
    ]
    lines = [line for line in lines if len(line) >= 2]
    if lines:
        if len(lines) == 1:
            return {"type": "LineString", "coordinates": lines[0]}
        return {"type": "MultiLineString", "coordinates": lines}

    points = [
        parse_coordinates(node.text)
        for node in placemark.findall(".//kml:Point/kml:coordinates", KML_NS)
    ]
    points = [point[0] for point in points if point]
    if len(points) == 1:
        return {"type": "Point", "coordinates": points[0]}
    if len(points) > 1:
        return {"type": "MultiPoint", "coordinates": points}

    polygons = []
    for node in placemark.findall(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS):
        ring = parse_coordinates(node.text)
        if len(ring) >= 4:
            polygons.append([ring])
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    if len(polygons) > 1:
        return {"type": "MultiPolygon", "coordinates": polygons}

    return None


def trail_classification(name: str) -> tuple[str, str]:
    normalized = name.lower()
    status = "proposed" if "proposed" in normalized or "planned" in normalized else "active"
    alignment = "on_road" if "on-road" in normalized or "on_road" in normalized else "off_road"
    return status, alignment


def kml_features(kml_path: Path, trail_id: str, trail: dict, kml_url: str) -> list[dict]:
    tree = ET.parse(kml_path)
    features = []
    status, alignment = trail_classification(trail.get("name", ""))

    for index, placemark in enumerate(tree.findall(".//kml:Placemark", KML_NS), start=1):
        geometry = placemark_geometry(placemark)
        if geometry is None:
            continue

        placemark_id = placemark.get("id")
        placemark_name = child_text(placemark, "name")
        description = child_text(placemark, "description")
        feature_id = f"srg:trail/{trail_id}/placemark/{index}"
        features.append(
            {
                "type": "Feature",
                "id": feature_id,
                "properties": {
                    "source": "Schuylkill River Greenways interactive map",
                    "source_type": "kml",
                    "source_url": kml_url,
                    "source_file": str(kml_path),
                    "source_trail_id": trail_id,
                    "source_post_id": trail.get("post_id"),
                    "source_urlpath": trail.get("urlpath"),
                    "layer": "trail",
                    "name": trail.get("name"),
                    "placemark_id": placemark_id,
                    "placemark_index": index,
                    "placemark_name": html.unescape(placemark_name) if placemark_name else None,
                    "description_html": description,
                    "status": status,
                    "alignment": alignment,
                    "color": trail.get("color"),
                    "dashed": trail.get("dashed"),
                },
                "geometry": geometry,
            }
        )
    return features


def point_features(mapdata: dict, site_url: str) -> list[dict]:
    features = []
    for layer in POINT_LAYERS:
        for item_id, item in mapdata.get(layer, {}).items():
            lat = item.get("lat")
            lng = item.get("lng")
            if lat in (None, "") or lng in (None, ""):
                continue
            feature = {
                "type": "Feature",
                "id": f"srg:{layer}/{item_id}",
                "properties": {
                    "source": "Schuylkill River Greenways interactive map",
                    "source_type": "mapdata.json",
                    "source_url": site_url,
                    "layer": layer,
                    "source_id": item_id,
                    "source_post_id": item.get("post_id"),
                    "source_urlpath": item.get("urlpath"),
                    "source_page_url": absolute_url(site_url, item.get("urlpath", "")),
                    "name": html.unescape(item.get("name", "")),
                    "infowindow_html": item.get("infowindow"),
                },
                "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
            }
            for optional_key in ("town", "amenities"):
                if optional_key in item:
                    feature["properties"][optional_key] = item[optional_key]
            features.append(feature)
    return features


def build_geojson(mapdata: dict, kml_paths: dict[str, Path], kml_urls: dict[str, str], site_url: str) -> dict:
    features = []
    for trail_id, trail in mapdata.get("trail", {}).items():
        features.extend(kml_features(kml_paths[trail_id], trail_id, trail, kml_urls[trail_id]))
    features.extend(point_features(mapdata, site_url))

    return {
        "type": "FeatureCollection",
        "name": "Schuylkill River Greenways Interactive Map",
        "metadata": {
            "generated_at": utc_now(),
            "source": "Schuylkill River Greenways interactive map",
            "map_page_url": MAP_PAGE_URL,
            "mapdata_url": site_url,
            "feature_count": len(features),
            "layers": {
                "trail": len(mapdata.get("trail", {})),
                "trailhead": len(mapdata.get("trailhead", {})),
                "places_to_visit": len(mapdata.get("places_to_visit", {})),
                "town": len(mapdata.get("town", {})),
            },
            "notes": [
                "Trail linework comes from KML files referenced by mapdata.json.",
                "Trailheads, towns, and places to visit come from point records in mapdata.json.",
                "GeoJSON coordinates are [longitude, latitude].",
            ],
        },
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-page-url", default=MAP_PAGE_URL)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, type=Path)
    parser.add_argument("--geojson", default=Path("srg-website-map.geojson"), type=Path)
    args = parser.parse_args()

    raw_dir = args.out_dir / "raw"
    trail_dir = raw_dir / "trails"
    manifest = {
        "generated_at": utc_now(),
        "map_page_url": args.map_page_url,
        "downloads": [],
    }

    page_bytes, page_headers = fetch_url(args.map_page_url)
    page_html = page_bytes.decode("utf-8", errors="replace")
    mapjson_url = discover_mapjson_url(page_html, args.map_page_url)
    write_bytes(raw_dir / "map-page.html", page_bytes)
    manifest["downloads"].append({"url": args.map_page_url, "path": str(raw_dir / "map-page.html"), "headers": page_headers})

    mapdata_bytes, mapdata_headers = fetch_url(mapjson_url)
    mapdata_path = raw_dir / "mapdata.json"
    write_bytes(mapdata_path, mapdata_bytes)
    manifest["mapdata_url"] = mapjson_url
    manifest["downloads"].append({"url": mapjson_url, "path": str(mapdata_path), "headers": mapdata_headers})

    mapdata = json.loads(mapdata_bytes)
    kml_paths: dict[str, Path] = {}
    kml_urls: dict[str, str] = {}
    for trail_id, trail in mapdata.get("trail", {}).items():
        kml_url = absolute_url(args.map_page_url, trail["kml"])
        kml_bytes, kml_headers = fetch_url(kml_url)
        kml_path = trail_dir / safe_filename_from_url(kml_url)
        write_bytes(kml_path, kml_bytes)
        kml_paths[trail_id] = kml_path
        kml_urls[trail_id] = kml_url
        manifest["downloads"].append({"url": kml_url, "path": str(kml_path), "headers": kml_headers})

    args.geojson.parent.mkdir(parents=True, exist_ok=True)
    with args.geojson.open("w", encoding="utf-8") as handle:
        json.dump(build_geojson(mapdata, kml_paths, kml_urls, mapjson_url), handle, indent=2)
        handle.write("\n")

    manifest_path = args.out_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")

    print(f"Wrote {args.geojson}")
    print(f"Wrote raw sources under {raw_dir}")
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, urllib.error.URLError, ET.ParseError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
