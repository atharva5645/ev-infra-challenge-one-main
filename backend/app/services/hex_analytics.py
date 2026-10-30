from __future__ import annotations

import math
from typing import Any
import h3
from app.services.trip_planner import haversine_km


def compute_hex_metrics(
    stations: list[dict[str, Any]],
    *,
    resolution: int = 7,
    district_ev_demand: int = 2500,
    expand_disk_k: int = 1,
) -> dict[str, Any]:
    """
    Compute H3 hexagonal spatial analytics (resolution 7 or 8) holding:
    - per-hex EV chargers
    - nearest charger distance
    - demand proxy
    - composite spatial gap score
    - cell polygon boundary for Leaflet rendering
    """
    res = 8 if resolution == 8 else 7

    # 1. Map stations into H3 cells
    charger_points: list[tuple[float, float]] = []
    cells_with_chargers: dict[str, list[dict[str, Any]]] = {}
    for st in stations:
        lat = st.get("latitude")
        lon = st.get("longitude")
        if lat is None or lon is None:
            continue
        charger_points.append((lat, lon))
        cell_id = h3.latlng_to_cell(lat, lon, res)
        if cell_id not in cells_with_chargers:
            cells_with_chargers[cell_id] = []
        cells_with_chargers[cell_id].append(st)

    if not charger_points:
        return {
            "resolution": res,
            "total_cells": 0,
            "cells": [],
            "summary": {
                "high_gap_cells": 0,
                "medium_gap_cells": 0,
                "low_gap_cells": 0,
                "avg_nearest_charger_km": 0.0,
            },
        }

    # 2. Expand region to include neighboring cells to discover perimeter dead zones
    all_cells: set[str] = set()
    for base_cell in cells_with_chargers:
        all_cells.add(base_cell)
        if expand_disk_k > 0:
            for neighbor in h3.grid_disk(base_cell, expand_disk_k):
                all_cells.add(neighbor)

    # 3. For each cell, calculate metrics
    total_active = len(cells_with_chargers)
    base_demand_per_cell = max(10, district_ev_demand // max(1, len(all_cells)))

    hex_cells: list[dict[str, Any]] = []
    nearest_dists: list[float] = []

    for cell_id in all_cells:
        center_lat, center_lon = h3.cell_to_latlng(cell_id)
        station_list = cells_with_chargers.get(cell_id, [])
        ch_count = len(station_list)
        dc_count = sum(1 for s in station_list if "DC" in str(s.get("charger_type", "")))

        # Distance to closest charger point
        min_dist = min(haversine_km((center_lat, center_lon), pt) for pt in charger_points)
        nearest_dists.append(min_dist)

        # Demand weighting: higher where chargers are clustered or in center
        cell_demand = base_demand_per_cell * (2.5 if ch_count > 0 else 1.0)

        # Composite gap calculation
        # Factors:
        # a) Charger Scarcity: 1 / (1 + count) -> 1.0 if 0 chargers, 0.5 if 1, 0.33 if 2
        # b) Distance penalty: normalized over 10 km
        # c) Demand pressure: normalized
        scarcity = 1.0 / (1.0 + ch_count)
        dist_factor = min(1.0, min_dist / 10.0)
        demand_factor = min(1.0, cell_demand / 400.0)

        gap_val = (0.40 * scarcity) + (0.35 * dist_factor) + (0.25 * demand_factor)
        coverage_val = min(1.0, ch_count / max(1, math.ceil(cell_demand / 300.0)))

        priority = "High Gap" if gap_val >= 0.65 else "Medium Gap" if gap_val >= 0.40 else "Adequate"

        # Boundary polygon vertices for Leaflet: list of [lat, lon]
        raw_boundary = h3.cell_to_boundary(cell_id)
        boundary_coords = [[round(lat, 6), round(lon, 6)] for lat, lon in raw_boundary]

        hex_cells.append({
            "cell_id": cell_id,
            "resolution": res,
            "center": [round(center_lat, 6), round(center_lon, 6)],
            "boundary": boundary_coords,
            "charger_count": ch_count,
            "fast_charger_count": dc_count,
            "ev_demand_proxy": int(cell_demand),
            "distance_to_nearest_charger_km": round(min_dist, 2),
            "coverage": round(coverage_val, 3),
            "gap_score": round(gap_val, 3),
            "priority": priority,
        })

    # Sort descending by gap score so high-deficit cells appear first
    hex_cells.sort(key=lambda c: -c["gap_score"])

    high_count = sum(1 for c in hex_cells if c["priority"] == "High Gap")
    med_count = sum(1 for c in hex_cells if c["priority"] == "Medium Gap")
    low_count = sum(1 for c in hex_cells if c["priority"] == "Adequate")
    avg_dist = round(sum(nearest_dists) / len(nearest_dists), 2) if nearest_dists else 0.0

    return {
        "resolution": res,
        "total_cells": len(hex_cells),
        "cells": hex_cells,
        "summary": {
            "high_gap_cells": high_count,
            "medium_gap_cells": med_count,
            "adequate_cells": low_count,
            "avg_nearest_charger_km": avg_dist,
        },
        "formula": "gap_score = 0.40 * (1/(1+chargers)) + 0.35 * min(1, dist_km/10) + 0.25 * min(1, demand/400)",
        "assumptions": [
            f"H3 hexagonal spatial partitioning at resolution {res} (~{5.16 if res == 7 else 0.74} km² per hexagon).",
            "Distance to nearest charger is straight-line Haversine distance from cell centroid to closest station.",
            "EV demand is an allocated spatial proxy based on district VAHAN totals, not household micro-survey.",
        ],
    }

