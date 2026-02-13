"""Convert GTFS shapes to GeoJSON for the 20 Frequent Network routes."""

import csv
import json
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GTFS_DIR = PROJECT_ROOT / "data" / "gtfs"
OUTPUT = PROJECT_ROOT / "site" / "routes.geojson"

# The 20 Frequent Network routes and their phases
PHASES = {
    1: {"routes": ["J14", "34", "47", "54", "60", "63", "79", "95"], "launch": "2025-03-23", "label": "Phase 1 (Mar 2025)"},
    2: {"routes": ["4", "49", "53", "66"], "launch": "2025-06-15", "label": "Phase 2 (Summer 2025)"},
    3: {"routes": ["20", "55", "77", "82"], "launch": "2025-09-15", "label": "Phase 3 (Fall 2025)"},
    4: {"routes": ["9", "12", "72", "81"], "launch": "2025-12-21", "label": "Phase 4 (Dec 2025)"},
}

FN_ROUTE_IDS = {r for phase in PHASES.values() for r in phase["routes"]}


def route_phase(route_id: str) -> int:
    for phase_num, info in PHASES.items():
        if route_id in info["routes"]:
            return phase_num
    return 0


def main():
    # 1. Read routes.txt for route names
    route_names = {}
    with open(GTFS_DIR / "routes.txt") as f:
        for row in csv.DictReader(f):
            rid = row["route_id"]
            if rid in FN_ROUTE_IDS:
                route_names[rid] = row["route_long_name"]

    # 2. Read trips.txt to get shape_ids per route
    route_shapes = defaultdict(set)
    with open(GTFS_DIR / "trips.txt") as f:
        for row in csv.DictReader(f):
            rid = row["route_id"]
            if rid in FN_ROUTE_IDS:
                route_shapes[rid].add(row["shape_id"])

    # 3. Read shapes.txt
    all_needed = {s for shapes in route_shapes.values() for s in shapes}
    shape_points = defaultdict(list)
    with open(GTFS_DIR / "shapes.txt") as f:
        for row in csv.DictReader(f):
            sid = row["shape_id"]
            if sid in all_needed:
                shape_points[sid].append(
                    (int(row["shape_pt_sequence"]), float(row["shape_pt_lon"]), float(row["shape_pt_lat"]))
                )

    # Sort each shape by sequence
    for sid in shape_points:
        shape_points[sid].sort(key=lambda x: x[0])

    # 4. Pick the longest shape per route (most points = most complete)
    features = []
    for rid in sorted(FN_ROUTE_IDS, key=lambda r: (route_phase(r), r)):
        shapes = route_shapes.get(rid, set())
        if not shapes:
            print(f"Warning: no shapes for route {rid}")
            continue

        best_shape = max(shapes, key=lambda s: len(shape_points.get(s, [])))
        points = shape_points.get(best_shape, [])
        if not points:
            print(f"Warning: no points for route {rid} shape {best_shape}")
            continue

        coords = [[pt[1], pt[2]] for pt in points]  # [lon, lat]
        phase = route_phase(rid)

        features.append({
            "type": "Feature",
            "properties": {
                "route_id": rid,
                "route_name": route_names.get(rid, rid),
                "phase": phase,
                "phase_label": PHASES[phase]["label"],
                "launch_date": PHASES[phase]["launch"],
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
        })

    geojson = {"type": "FeatureCollection", "features": features}

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(geojson, f)

    print(f"Wrote {len(features)} routes to {OUTPUT}")
    total_points = sum(len(ft["geometry"]["coordinates"]) for ft in features)
    print(f"Total coordinate points: {total_points}")


if __name__ == "__main__":
    main()
