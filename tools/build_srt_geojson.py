#!/usr/bin/env python3
"""Build the master Schuylkill River Trail GeoJSON from Overpass JSON exports."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


TRAIL_ID = "schuylkill-river-trail"
TRAIL_NAME = "Schuylkill River Trail"
SRT_ROUTE_RELATION_IDS = {1541998, 15062447}
NAME_KEYS = ("name", "alt_name", "official_name", "loc_name", "ref")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def osm_url(osm_type: str, osm_id: int) -> str:
    return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


def way_geometry(way: dict) -> dict | None:
    geometry = way.get("geometry")
    if not geometry or len(geometry) < 2:
        return None
    return {
        "type": "LineString",
        "coordinates": [[point["lon"], point["lat"]] for point in geometry],
    }


def srt_name_match(tags: dict) -> list[str]:
    matches = []
    for key in NAME_KEYS:
        value = tags.get(key)
        if not value:
            continue
        normalized = value.lower()
        if "schuylkill river trail" in normalized or normalized == "srt":
            matches.append(key)
    return matches


def collect_route_members(route_payload: dict) -> tuple[dict[int, list[dict]], list[dict]]:
    memberships: dict[int, list[dict]] = {}
    route_relations = []

    for element in route_payload.get("elements", []):
        if element.get("type") != "relation" or element.get("id") not in SRT_ROUTE_RELATION_IDS:
            continue

        tags = element.get("tags", {})
        relation = {
            "osm_type": "relation",
            "osm_id": element["id"],
            "osm_url": osm_url("relation", element["id"]),
            "name": tags.get("name"),
            "route": tags.get("route"),
            "network": tags.get("network"),
            "ref": tags.get("ref"),
        }
        route_relations.append(relation)

        for member in element.get("members", []):
            if member.get("type") != "way":
                continue
            entry = dict(relation)
            entry["role"] = member.get("role", "")
            memberships.setdefault(member["ref"], []).append(entry)

    return memberships, route_relations


def merge_way(features_by_id: dict[int, dict], way: dict, inclusion_reason: str, memberships: dict[int, list[dict]]) -> None:
    if way.get("type") != "way":
        return

    geometry = way_geometry(way)
    if geometry is None:
        return

    way_id = way["id"]
    tags = way.get("tags", {})
    name_matches = srt_name_match(tags)
    relations = memberships.get(way_id, [])
    existing = features_by_id.get(way_id)

    if existing:
        reasons = set(existing["properties"]["inclusion_reasons"])
        reasons.add(inclusion_reason)
        if relations:
            existing_relations = {
                relation["osm_id"]: relation for relation in existing["properties"].get("relations", [])
            }
            for relation in relations:
                existing_relations[relation["osm_id"]] = relation
            existing["properties"]["relations"] = list(existing_relations.values())
            reasons.add("member of canonical SRT route relation")
        if name_matches:
            reasons.add("OSM name-like tag matches SRT")
        existing["properties"]["inclusion_reasons"] = sorted(reasons)
        return

    osm_name = tags.get("name")
    segment_name = osm_name if osm_name and osm_name != TRAIL_NAME else None
    reasons = {inclusion_reason}
    if relations:
        reasons.add("member of canonical SRT route relation")
    if name_matches:
        reasons.add("OSM name-like tag matches SRT")

    features_by_id[way_id] = {
        "type": "Feature",
        "id": f"osm:way/{way_id}",
        "properties": {
            "trail_id": TRAIL_ID,
            "trail_name": TRAIL_NAME,
            "segment_name": segment_name,
            "display_name": segment_name or TRAIL_NAME,
            "is_srt": True,
            "osm_type": "way",
            "osm_id": way_id,
            "osm_url": osm_url("way", way_id),
            "osm_name": osm_name,
            "osm_alt_name": tags.get("alt_name"),
            "highway": tags.get("highway"),
            "surface": tags.get("surface"),
            "bicycle": tags.get("bicycle"),
            "foot": tags.get("foot"),
            "relations": relations,
            "inclusion_reasons": sorted(reasons),
            "osm_tags": tags,
        },
        "geometry": geometry,
    }


def build_geojson(route_payload: dict, named_payload: dict) -> dict:
    memberships, route_relations = collect_route_members(route_payload)
    features_by_id: dict[int, dict] = {}

    for element in route_payload.get("elements", []):
        merge_way(
            features_by_id,
            element,
            "member of canonical SRT route relation",
            memberships,
        )

    for element in named_payload.get("elements", []):
        merge_way(
            features_by_id,
            element,
            "OSM name-like tag matches SRT",
            memberships,
        )

    features = sorted(features_by_id.values(), key=lambda feature: feature["properties"]["osm_id"])
    timestamps = sorted(
        {
            payload.get("osm3s", {}).get("timestamp_osm_base")
            for payload in (route_payload, named_payload)
            if payload.get("osm3s", {}).get("timestamp_osm_base")
        }
    )

    return {
        "type": "FeatureCollection",
        "name": "Schuylkill River Trail",
        "metadata": {
            "trail_id": TRAIL_ID,
            "trail_name": TRAIL_NAME,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "source": "OpenStreetMap via Overpass API",
            "license": "Open Database License (ODbL)",
            "osm_timestamps": timestamps,
            "canonical_route_relations": sorted(route_relations, key=lambda relation: relation["osm_id"]),
            "feature_count": len(features),
            "notes": [
                "Features are physical OSM ways, not route relation geometries.",
                "The file includes ways from canonical Schuylkill River Trail route relations and ways whose name-like tags identify them as SRT.",
                "Local section names are preserved as segment_name when OSM name differs from Schuylkill River Trail.",
            ],
        },
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--route-json",
        default="/private/tmp/srt-route-members-overpass.json",
        type=Path,
        help="Overpass JSON containing canonical SRT route relations and member way geometry.",
    )
    parser.add_argument(
        "--named-json",
        default="/private/tmp/srt-named-ways-overpass.json",
        type=Path,
        help="Overpass JSON containing SRT name/alt-name matching way geometry.",
    )
    parser.add_argument("--output", default="data/srt-osm.geojson", type=Path)
    args = parser.parse_args()

    geojson = build_geojson(load_json(args.route_json), load_json(args.named_json))
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(geojson, handle, indent=2, sort_keys=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
