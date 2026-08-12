#!/usr/bin/env python3
"""Build a station-calibrated scrub route from the official 2025 SRG data.

The supplied alignment is a multipart line whose five parts are traversed by
the official 0.10-mile points. This builder orders and orients those parts,
inserts every tenth-mile point as an exact route vertex, and assigns calibrated
mileage to every intervening alignment vertex. The map can therefore follow
the detailed trail shape while landing exactly on each official station.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
from datetime import datetime, timezone
from pathlib import Path


EARTH_RADIUS_MILES = 3958.8
ALIGNMENT_LAYER = "measurement_alignment"
ANCHOR_LAYER = "tenth_mile_points"


def distance_miles(first: list[float], second: list[float]) -> float:
    first_lat = math.radians(first[1])
    second_lat = math.radians(second[1])
    delta_lat = second_lat - first_lat
    delta_lng = math.radians(second[0] - first[0])
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(first_lat) * math.cos(second_lat) * math.sin(delta_lng / 2) ** 2
    )
    return EARTH_RADIUS_MILES * 2 * math.asin(min(1, math.sqrt(haversine)))


def cumulative_distances(coordinates: list[list[float]]) -> list[float]:
    cumulative = [0.0]
    for first, second in zip(coordinates, coordinates[1:]):
        cumulative.append(cumulative[-1] + distance_miles(first, second))
    return cumulative


def project_to_segment(
    point: list[float], first: list[float], second: list[float]
) -> tuple[float, float, list[float]]:
    latitude_scale = math.cos(math.radians((first[1] + second[1] + point[1]) / 3))
    segment_x = (second[0] - first[0]) * latitude_scale
    segment_y = second[1] - first[1]
    point_x = (point[0] - first[0]) * latitude_scale
    point_y = point[1] - first[1]
    segment_length_squared = segment_x**2 + segment_y**2
    amount = (
        max(
            0.0,
            min(
                1.0,
                (point_x * segment_x + point_y * segment_y)
                / segment_length_squared,
            ),
        )
        if segment_length_squared
        else 0.0
    )
    projected = [
        first[0] + (second[0] - first[0]) * amount,
        first[1] + (second[1] - first[1]) * amount,
    ]
    return distance_miles(point, projected), amount, projected


def nearest_projection(
    point: list[float], parts: list[list[list[float]]], part_cumulative: list[list[float]]
) -> dict:
    closest = None
    for part_index, coordinates in enumerate(parts):
        for segment_index, (first, second) in enumerate(
            zip(coordinates, coordinates[1:])
        ):
            gap, amount, projected = project_to_segment(point, first, second)
            if closest is None or gap < closest["gap_miles"]:
                segment_start = part_cumulative[part_index][segment_index]
                segment_end = part_cumulative[part_index][segment_index + 1]
                closest = {
                    "gap_miles": gap,
                    "part_index": part_index,
                    "part_position": segment_start
                    + (segment_end - segment_start) * amount,
                    "projected": projected,
                }
    if closest is None:
        raise RuntimeError("Could not project an official station onto the alignment")
    return closest


def source_layers(source: dict) -> tuple[list[list[list[float]]], list[dict]]:
    alignment_features = [
        feature
        for feature in source.get("features", [])
        if feature.get("properties", {}).get("measurement_layer") == ALIGNMENT_LAYER
    ]
    if len(alignment_features) != 1:
        raise RuntimeError(
            f"Expected one {ALIGNMENT_LAYER} feature, found {len(alignment_features)}"
        )
    geometry = alignment_features[0].get("geometry", {})
    if geometry.get("type") != "MultiLineString":
        raise RuntimeError("The official measurement alignment must be a MultiLineString")
    parts = geometry.get("coordinates", [])
    if not parts or any(len(part) < 2 for part in parts):
        raise RuntimeError("The official measurement alignment has an empty line part")

    anchors = sorted(
        (
            feature
            for feature in source.get("features", [])
            if feature.get("properties", {}).get("measurement_layer") == ANCHOR_LAYER
            and feature.get("geometry", {}).get("type") == "Point"
        ),
        key=lambda feature: feature["properties"]["mile"],
    )
    if not anchors:
        raise RuntimeError("No official tenth-mile points found")
    for index, anchor in enumerate(anchors):
        mile = round(float(anchor["properties"]["mile"]), 1)
        expected = round(index / 10, 1)
        if mile != expected:
            raise RuntimeError(
                f"Expected a complete tenth-mile series at {expected:.1f}, found {mile:.1f}"
            )
        anchor["station_mile"] = mile
    return parts, anchors


def ordered_alignment(
    parts: list[list[list[float]]], anchors: list[dict]
) -> tuple[list[list[float]], list[float], list[dict], list[int]]:
    part_cumulative = [cumulative_distances(part) for part in parts]
    projected_anchors = []
    matches_by_part = {index: [] for index in range(len(parts))}
    for anchor in anchors:
        projection = nearest_projection(
            anchor["geometry"]["coordinates"], parts, part_cumulative
        )
        projection["mile"] = anchor["station_mile"]
        projection["coordinate"] = anchor["geometry"]["coordinates"]
        projected_anchors.append(projection)
        matches_by_part[projection["part_index"]].append(projection)

    unmatched = [index for index, matches in matches_by_part.items() if not matches]
    if unmatched:
        raise RuntimeError(f"Alignment parts without tenth-mile anchors: {unmatched}")

    part_order = sorted(
        range(len(parts)),
        key=lambda index: min(match["mile"] for match in matches_by_part[index]),
    )
    orientation = {}
    for part_index in part_order:
        matches = sorted(matches_by_part[part_index], key=lambda match: match["mile"])
        orientation[part_index] = (
            "forward"
            if matches[-1]["part_position"] >= matches[0]["part_position"]
            else "reverse"
        )

    coordinates = []
    offsets = {}
    for part_index in part_order:
        part = parts[part_index]
        if orientation[part_index] == "reverse":
            part = list(reversed(part))
        offsets[part_index] = (
            cumulative_distances(coordinates)[-1] if coordinates else 0.0
        )
        for coordinate in part:
            if not coordinates or coordinate != coordinates[-1]:
                coordinates.append(coordinate)
    route_cumulative = cumulative_distances(coordinates)

    # Convert each projection from its source-part position into a position on
    # the ordered, oriented route.
    for projection in projected_anchors:
        part_index = projection["part_index"]
        part_length = part_cumulative[part_index][-1]
        oriented_position = projection["part_position"]
        if orientation[part_index] == "reverse":
            oriented_position = part_length - oriented_position
        projection["route_position"] = offsets[part_index] + oriented_position

    previous = -math.inf
    for projection in projected_anchors:
        if projection["route_position"] <= previous:
            raise RuntimeError(
                "Official tenth-mile points are not monotonic on the ordered alignment"
            )
        previous = projection["route_position"]

    return coordinates, route_cumulative, projected_anchors, part_order


def calibrated_coordinates(
    coordinates: list[list[float]],
    route_cumulative: list[float],
    anchors: list[dict],
) -> tuple[list[list[float]], list[float], list[int]]:
    output_coordinates = []
    output_miles = []
    anchor_indices = []

    for index, (start, end) in enumerate(zip(anchors, anchors[1:])):
        if index == 0:
            output_coordinates.append(start["coordinate"])
            output_miles.append(start["mile"])
            anchor_indices.append(0)

        first_vertex = bisect.bisect_right(route_cumulative, start["route_position"])
        last_vertex = bisect.bisect_left(route_cumulative, end["route_position"])
        route_span = end["route_position"] - start["route_position"]
        station_span = end["mile"] - start["mile"]
        for vertex_index in range(first_vertex, last_vertex):
            position = route_cumulative[vertex_index]
            amount = (position - start["route_position"]) / route_span
            output_coordinates.append(coordinates[vertex_index])
            output_miles.append(start["mile"] + station_span * amount)

        output_coordinates.append(end["coordinate"])
        output_miles.append(end["mile"])
        anchor_indices.append(len(output_coordinates) - 1)

    return output_coordinates, output_miles, anchor_indices


def build_route(source: dict) -> dict:
    parts, anchors = source_layers(source)
    coordinates, geometric_cumulative, projected_anchors, part_order = (
        ordered_alignment(parts, anchors)
    )
    calibrated, cumulative_miles, anchor_indices = calibrated_coordinates(
        coordinates, geometric_cumulative, projected_anchors
    )
    maximum_gap_feet = max(anchor["gap_miles"] for anchor in projected_anchors) * 5280
    total_miles = anchors[-1]["station_mile"]

    return {
        "type": "FeatureCollection",
        "name": "Station-calibrated SRT Scrubber Route",
        "metadata": {
            "generated_at": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat(),
            "source": "data/srg-data/2025-measurements-partial.geojson",
            "purpose": "Officially stationed Philadelphia-to-Frackville route for the map footer scrubber",
            "distance_authority": "SRG 2025 tenth-mile points",
            "geometry_authority": "SRG 2025 measurement alignment",
            "alignment_part_order": part_order,
            "alignment_part_count": len(parts),
            "anchor_count": len(anchors),
            "maximum_anchor_gap_feet": round(maximum_gap_feet, 6),
            "geometric_route_miles": round(geometric_cumulative[-1], 6),
            "stationed_route_miles": total_miles,
            "start_coordinate": calibrated[0],
            "end_coordinate": calibrated[-1],
        },
        "features": [
            {
                "type": "Feature",
                "id": "srt-scrubber-route",
                "properties": {
                    "name": "Station-calibrated SRT Scrubber Route",
                    "start": "Philadelphia",
                    "end": "Frackville",
                    "distance_miles": total_miles,
                    "cumulative_miles": cumulative_miles,
                    "official_anchor_indices": anchor_indices,
                },
                "geometry": {"type": "LineString", "coordinates": calibrated},
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/srg-data/2025-measurements-partial.geojson"),
    )
    parser.add_argument("--output", type=Path, default=Path("data/srt-scrub-route.geojson"))
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8") as handle:
        source = json.load(handle)
    route = build_route(source)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(route, handle, indent=2)
        handle.write("\n")

    metadata = route["metadata"]
    print(
        f"Wrote {args.output}: {metadata['stationed_route_miles']:.1f} stationed miles, "
        f"{metadata['anchor_count']} exact tenth-mile anchors, "
        f"maximum source gap {metadata['maximum_anchor_gap_feet']:.3f} feet"
    )


if __name__ == "__main__":
    main()
