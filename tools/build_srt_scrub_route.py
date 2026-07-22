#!/usr/bin/env python3
"""Build one west-to-east SRT line for the map's trail scrubber.

This is a temporary derived route. It joins the official SRG map's four trail
line layers at nearby endpoints, bridges any remaining component gaps with
straight lines, and exports the shortest connected path from the westernmost
endpoint to the easternmost endpoint.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
from datetime import datetime, timezone
from pathlib import Path


EARTH_RADIUS_MILES = 3958.8
TRAIL_STATUSES = {"active", "proposed"}
TRAIL_ALIGNMENTS = {"off_road", "on_road"}


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


def line_length_miles(coordinates: list[list[float]]) -> float:
    return sum(distance_miles(first, second) for first, second in zip(coordinates, coordinates[1:]))


def trail_features(geojson: dict, excluded_post_ids: set[int]) -> list[dict]:
    return [
        feature
        for feature in geojson.get("features", [])
        if feature.get("properties", {}).get("layer") == "trail"
        and feature.get("properties", {}).get("status") in TRAIL_STATUSES
        and feature.get("properties", {}).get("alignment") in TRAIL_ALIGNMENTS
        and feature.get("properties", {}).get("source_post_id") not in excluded_post_ids
        and feature.get("geometry", {}).get("type") == "LineString"
        and len(feature["geometry"].get("coordinates", [])) > 1
    ]


def add_edge(
    graph: list[list[dict]],
    start: int,
    end: int,
    coordinates: list[list[float]],
    *,
    connector: bool = False,
) -> None:
    weight = max(line_length_miles(coordinates), 0.000001)
    graph[start].append(
        {"to": end, "weight": weight, "coordinates": coordinates, "connector": connector}
    )
    graph[end].append(
        {
            "to": start,
            "weight": weight,
            "coordinates": list(reversed(coordinates)),
            "connector": connector,
        }
    )


def graph_components(graph: list[list[dict]]) -> tuple[list[int], int]:
    components = [-1] * len(graph)
    component_count = 0
    for start in range(len(graph)):
        if components[start] != -1:
            continue
        components[start] = component_count
        stack = [start]
        while stack:
            node = stack.pop()
            for edge in graph[node]:
                destination = edge["to"]
                if components[destination] == -1:
                    components[destination] = component_count
                    stack.append(destination)
        component_count += 1
    return components, component_count


def connect_graph(
    graph: list[list[dict]], endpoints: list[dict], nearby_gap_miles: float
) -> list[float]:
    connector_lengths = []
    for first in range(len(endpoints)):
        for second in range(first):
            if endpoints[first]["segment"] == endpoints[second]["segment"]:
                continue
            gap = distance_miles(endpoints[first]["coordinate"], endpoints[second]["coordinate"])
            if gap <= nearby_gap_miles:
                add_edge(
                    graph,
                    first,
                    second,
                    [endpoints[first]["coordinate"], endpoints[second]["coordinate"]],
                    connector=True,
                )

    components, component_count = graph_components(graph)
    while component_count > 1:
        closest = None
        for first in range(len(endpoints)):
            for second in range(first):
                if components[first] == components[second]:
                    continue
                gap = distance_miles(
                    endpoints[first]["coordinate"], endpoints[second]["coordinate"]
                )
                if closest is None or gap < closest[0]:
                    closest = (gap, first, second)
        if closest is None:
            break
        gap, first, second = closest
        add_edge(
            graph,
            first,
            second,
            [endpoints[first]["coordinate"], endpoints[second]["coordinate"]],
            connector=True,
        )
        connector_lengths.append(gap)
        components, component_count = graph_components(graph)
    return connector_lengths


def shortest_path(graph: list[list[dict]], start: int, end: int) -> list[dict]:
    distances = [math.inf] * len(graph)
    previous: list[tuple[int, dict] | None] = [None] * len(graph)
    distances[start] = 0
    queue = [(0.0, start)]

    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        if node == end:
            break
        for edge in graph[node]:
            candidate = distance + edge["weight"]
            destination = edge["to"]
            if candidate < distances[destination]:
                distances[destination] = candidate
                previous[destination] = (node, edge)
                heapq.heappush(queue, (candidate, destination))

    path = []
    node = end
    while node != start and previous[node] is not None:
        node, edge = previous[node]
        path.append(edge)
    if node != start:
        raise RuntimeError("Could not find a connected west-to-east trail path")
    return list(reversed(path))


def build_route(source: dict, nearby_gap_miles: float, excluded_post_ids: set[int]) -> dict:
    features = trail_features(source, excluded_post_ids)
    segments = [feature["geometry"]["coordinates"] for feature in features]
    if not segments:
        raise RuntimeError("No SRG trail LineStrings found in source GeoJSON")

    endpoints = []
    graph: list[list[dict]] = [[] for _ in range(len(segments) * 2)]
    for segment_index, coordinates in enumerate(segments):
        start = len(endpoints)
        endpoints.append({"segment": segment_index, "coordinate": coordinates[0]})
        end = len(endpoints)
        endpoints.append({"segment": segment_index, "coordinate": coordinates[-1]})
        add_edge(graph, start, end, coordinates)

    forced_connector_lengths = connect_graph(graph, endpoints, nearby_gap_miles)
    west = min(range(len(endpoints)), key=lambda index: endpoints[index]["coordinate"][0])
    east = max(range(len(endpoints)), key=lambda index: endpoints[index]["coordinate"][0])
    path = shortest_path(graph, west, east)

    route_coordinates = []
    connector_count = 0
    connector_miles = 0.0
    source_segment_count = 0
    for edge in path:
        connector_count += int(edge["connector"])
        connector_miles += edge["weight"] if edge["connector"] else 0
        source_segment_count += int(not edge["connector"])
        for coordinate in edge["coordinates"]:
            if not route_coordinates or route_coordinates[-1] != coordinate:
                route_coordinates.append(coordinate)

    route_miles = line_length_miles(route_coordinates)
    return {
        "type": "FeatureCollection",
        "name": "Temporary SRT Scrubber Route",
        "metadata": {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "source": "srg-website-map.geojson",
            "purpose": "Temporary continuous west-to-east route for the map footer scrubber",
            "replacement_note": "Replace this derived line when official distance line data is available.",
            "input_trail_feature_count": len(features),
            "path_source_segment_count": source_segment_count,
            "connector_count": connector_count,
            "connector_miles": round(connector_miles, 6),
            "forced_component_connector_miles": [round(value, 6) for value in forced_connector_lengths],
            "route_miles": round(route_miles, 6),
        },
        "features": [
            {
                "type": "Feature",
                "id": "srt-scrubber-route",
                "properties": {
                    "name": "Temporary SRT Scrubber Route",
                    "start": "source",
                    "end": "trail end",
                    "distance_miles": round(route_miles, 6),
                },
                "geometry": {"type": "LineString", "coordinates": route_coordinates},
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("srg-website-map.geojson"))
    parser.add_argument("--output", type=Path, default=Path("srt-scrub-route.geojson"))
    parser.add_argument(
        "--nearby-gap-miles",
        type=float,
        default=0.15,
        help="Maximum endpoint gap to consider a direct trail connection",
    )
    parser.add_argument(
        "--exclude-post-id",
        type=int,
        action="append",
        default=[1796],
        help="SRG source post ID to exclude (repeatable)",
    )
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8") as handle:
        source = json.load(handle)
    route = build_route(source, args.nearby_gap_miles, set(args.exclude_post_id))
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(route, handle, indent=2)
        handle.write("\n")

    metadata = route["metadata"]
    print(
        f"Wrote {args.output}: {metadata['route_miles']:.1f} miles, "
        f"{metadata['path_source_segment_count']} source segments, "
        f"{metadata['connector_count']} straight connectors"
    )


if __name__ == "__main__":
    main()
