from __future__ import annotations

import math
from typing import Any

from app.models.trip import TripPlanRequest


DISTANCE_METHOD = "Representative corridor polyline length multiplied by a corridor road-distance factor; not turn-by-turn road routing."
COVERAGE_SEGMENT_KM = 50.0
MAX_RECOMMENDED_STOPS = 10

_CORRIDORS: tuple[dict[str, Any], ...] = (
    {
        "id": "bengaluru-mysuru", "name": "Bengaluru to Mysuru", "origin": "Bengaluru, Karnataka", "destination": "Mysuru, Karnataka",
        "states": ["Karnataka"], "road_factor": 1.12,
        "route_geometry": [(12.9716, 77.5946), (12.85, 77.48), (12.72, 77.28), (12.62, 77.18), (12.52, 76.90), (12.42, 76.78), (12.2958, 76.6394)],
    },
    {
        "id": "delhi-agra", "name": "Delhi to Agra", "origin": "Delhi", "destination": "Agra, Uttar Pradesh",
        "states": ["Delhi", "Uttar Pradesh"], "road_factor": 1.13,
        "route_geometry": [(28.6139, 77.2090), (28.35, 77.32), (28.15, 77.45), (27.90, 77.67), (27.55, 77.72), (27.1767, 78.0081)],
    },
    {
        "id": "mumbai-pune", "name": "Mumbai to Pune", "origin": "Mumbai, Maharashtra", "destination": "Pune, Maharashtra",
        "states": ["Maharashtra"], "road_factor": 1.17,
        "route_geometry": [(19.0760, 72.8777), (19.12, 73.02), (19.18, 73.23), (18.96, 73.40), (18.75, 73.41), (18.5204, 73.8567)],
    },
    {
        "id": "chennai-puducherry", "name": "Chennai to Puducherry", "origin": "Chennai, Tamil Nadu", "destination": "Puducherry",
        "states": ["Tamil Nadu", "Puducherry"], "road_factor": 1.09,
        "route_geometry": [(13.0827, 80.2707), (12.82, 80.24), (12.62, 80.20), (12.39, 80.10), (12.15, 79.93), (11.9416, 79.8083)],
    },
    {
        "id": "hyderabad-vijayawada", "name": "Hyderabad to Vijayawada", "origin": "Hyderabad, Telangana", "destination": "Vijayawada, Andhra Pradesh",
        "states": ["Telangana", "Andhra Pradesh"], "road_factor": 1.13,
        "route_geometry": [(17.3850, 78.4867), (17.25, 78.62), (17.05, 78.87), (16.85, 79.28), (16.57, 79.65), (16.20, 80.35), (16.5062, 80.6480)],
    },
)


def haversine_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, first)
    lat2, lon2 = map(math.radians, second)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def list_corridors() -> list[dict[str, Any]]:
    return [
        {**row, "estimated_distance_km": round(sum(haversine_km(a, b) for a, b in zip(row["route_geometry"], row["route_geometry"][1:])) * row["road_factor"], 1), "distance_method": DISTANCE_METHOD}
        for row in _CORRIDORS
    ]


def find_corridor(corridor_id: str) -> dict[str, Any] | None:
    return next((row for row in list_corridors() if row["id"] == corridor_id), None)


def _project_station(
    latitude: float, longitude: float, geometry: list[tuple[float, float]], road_factor: float,
) -> tuple[float, float]:
    """Return nearest route-line distance and estimated progress along the corridor."""
    best_lateral = float("inf")
    best_progress = 0.0
    cumulative_geo_km = 0.0
    for start, end in zip(geometry, geometry[1:]):
        segment_geo_km = haversine_km(start, end)
        mean_lat_rad = math.radians((start[0] + end[0] + latitude) / 3)
        km_per_lon = 111.32 * math.cos(mean_lat_rad)
        dx = (end[1] - start[1]) * km_per_lon
        dy = (end[0] - start[0]) * 111.32
        px = (longitude - start[1]) * km_per_lon
        py = (latitude - start[0]) * 111.32
        length_sq = dx * dx + dy * dy
        fraction = 0.0 if length_sq == 0 else min(1.0, max(0.0, (px * dx + py * dy) / length_sq))
        closest = (start[0] + fraction * (end[0] - start[0]), start[1] + fraction * (end[1] - start[1]))
        lateral = haversine_km((latitude, longitude), closest)
        if lateral < best_lateral:
            best_lateral = lateral
            best_progress = (cumulative_geo_km + segment_geo_km * fraction) * road_factor
        cumulative_geo_km += segment_geo_km
    return best_lateral, best_progress


def _make_station_candidate(
    station: dict[str, Any], vehicle_class: str, geometry: list[tuple[float, float]], road_factor: float,
    search_distance_km: float,
) -> dict[str, Any] | None:
    lateral_km, progress_km = _project_station(station["latitude"], station["longitude"], geometry, road_factor)
    if lateral_km > search_distance_km:
        return None
    supported = station.get("supported_vehicle_classes") or []
    compatibility = "Compatible" if vehicle_class in supported else "Unknown" if not supported else "Not listed"
    return {
        "id": station["id"], "name": station["name"], "latitude": station["latitude"], "longitude": station["longitude"],
        "state": station["state"], "district": station["district"], "charger_type": station["charger_type"],
        "power_kw": station.get("power_kw"), "total_chargers": station["total_chargers"],
        "total_connectors": station["total_connectors"], "supported_vehicle_classes": supported,
        "compatibility_status": compatibility, "source": station["source"], "snapshot_date": station["snapshot_date"],
        "distance_from_route_km": round(lateral_km, 2), "route_progress_km": round(progress_km, 2),
        "_lateral_km": lateral_km,
    }


def _interpolate_corridor_point(geometry: list[tuple[float, float]], road_factor: float, progress_km: float) -> tuple[float, float]:
    """Find lat, lon coordinate along polyline at the target progress km."""
    target_geo_km = progress_km / max(0.01, road_factor)
    accumulated = 0.0
    for start, end in zip(geometry, geometry[1:]):
        seg_dist = haversine_km(start, end)
        if accumulated + seg_dist >= target_geo_km:
            fraction = (target_geo_km - accumulated) / seg_dist if seg_dist > 0 else 0.0
            fraction = max(0.0, min(1.0, fraction))
            lat = start[0] + fraction * (end[0] - start[0])
            lon = start[1] + fraction * (end[1] - start[1])
            return (lat, lon)
        accumulated += seg_dist
    return geometry[-1]


def _coverage_segments(distance_km: float, stations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segment_count = max(1, math.ceil(distance_km / COVERAGE_SEGMENT_KM))
    output = []
    for index in range(segment_count):
        start_km = index * COVERAGE_SEGMENT_KM
        end_km = min(distance_km, (index + 1) * COVERAGE_SEGMENT_KM)
        matches = sum(1 for station in stations if start_km <= station["route_progress_km"] <= end_km)
        output.append({
            "start_km": round(start_km, 1), "end_km": round(end_km, 1), "sampled_station_count": matches,
            "coverage_status": "sampled_station_nearby" if matches else "no_sampled_station_found",
        })
    return output


def calculate_trip_plan(
    request: TripPlanRequest,
    corridor: dict[str, Any],
    source_stations: list[dict[str, Any]],
    state_samples: list[dict[str, Any]],
    source_warnings: list[str] | None = None,
) -> dict[str, Any]:
    geometry = [tuple(point) for point in corridor["route_geometry"]]
    road_factor = corridor["road_factor"]
    distance_km = sum(haversine_km(a, b) for a, b in zip(geometry, geometry[1:])) * road_factor
    journey_energy = distance_km * request.consumption_kwh_per_100km / 100
    capacity = request.battery_capacity_kwh
    available_energy = capacity * request.starting_soc_pct / 100
    reserve_energy = capacity * request.reserve_pct / 100
    usable_energy = max(0.0, available_energy - reserve_energy)
    requires_charging = journey_energy > usable_energy + 1e-9

    near_stations: list[dict[str, Any]] = []
    for station in source_stations:
        candidate = _make_station_candidate(station, request.vehicle_class, geometry, road_factor, request.station_search_distance_km)
        if candidate:
            near_stations.append(candidate)
    near_stations.sort(key=lambda item: (item["route_progress_km"], item["distance_from_route_km"], item["name"].casefold()))
    eligible = [item for item in near_stations if item["compatibility_status"] != "Not listed"]
    warnings = list(source_warnings or [])
    if not near_stations:
        warnings.append(f"No station from the retrieved sample was found within {request.station_search_distance_km:g} km of the corridor geometry.")
    if near_stations and not eligible:
        warnings.append("Nearby sampled records explicitly omit this vehicle class; none is recommended as a compatible stop.")

    coverage = _coverage_segments(distance_km, near_stations)
    if any(row["coverage_status"] == "no_sampled_station_found" for row in coverage):
        warnings.append(f"One or more {COVERAGE_SEGMENT_KM:g} km corridor segments contain no sampled directory station within the configured search distance; the station sample is incomplete.")

    stops: list[dict[str, Any]] = []
    current_progress = 0.0
    current_lateral = 0.0
    current_soc = request.starting_soc_pct
    used_ids: set[str] = set()
    arrival_after_plan: float | None = None
    plan_feasible = not requires_charging
    if not requires_charging:
        arrival_after_plan = request.starting_soc_pct - journey_energy / capacity * 100
    else:
        for _ in range(min(MAX_RECOMMENDED_STOPS, len(eligible))):
            remaining_distance = max(0.0, distance_km - current_progress + current_lateral)
            leg_energy_to_destination = remaining_distance * request.consumption_kwh_per_100km / 100
            current_usable = max(0.0, (current_soc - request.reserve_pct) * capacity / 100)
            if leg_energy_to_destination <= current_usable + 1e-9:
                arrival_after_plan = current_soc - leg_energy_to_destination / capacity * 100
                plan_feasible = True
                break

            reachable = []
            for candidate in eligible:
                if candidate["id"] in used_ids or candidate["route_progress_km"] <= current_progress + 0.5:
                    continue
                approach_distance = (
                    candidate["route_progress_km"] - current_progress + current_lateral + candidate["_lateral_km"]
                )
                energy_to_stop = approach_distance * request.consumption_kwh_per_100km / 100
                if energy_to_stop <= current_usable + 1e-9:
                    reachable.append((candidate, approach_distance, energy_to_stop))
            if not reachable:
                break

            candidate, approach_distance, energy_to_stop = max(
                reachable, key=lambda option: (option[0]["route_progress_km"] - option[0]["_lateral_km"], -option[0]["_lateral_km"])
            )
            arrival_soc = max(0.0, current_soc - energy_to_stop / capacity * 100)
            stops.append({
                **{key: value for key, value in candidate.items() if not key.startswith("_")},
                "stop_order": len(stops) + 1,
                "estimated_arrival_soc_pct": round(arrival_soc, 1),
                "estimated_recharge_to_full_kwh": round(max(0.0, capacity - capacity * arrival_soc / 100), 2),
                "estimated_round_trip_detour_km": round(candidate["_lateral_km"] * 2, 2),
            })
            used_ids.add(candidate["id"])
            current_progress = candidate["route_progress_km"]
            current_lateral = candidate["_lateral_km"]
            current_soc = 100.0  # The simulation assumes the vehicle charges back to full at each stop.

        if not plan_feasible:
            remaining_distance = max(0.0, distance_km - current_progress + current_lateral)
            remaining_energy = remaining_distance * request.consumption_kwh_per_100km / 100
            current_usable = max(0.0, (current_soc - request.reserve_pct) * capacity / 100)
            if remaining_energy <= current_usable + 1e-9:
                arrival_after_plan = current_soc - remaining_energy / capacity * 100
                plan_feasible = True
        if not plan_feasible:
            warnings.append("The retrieved station sample does not contain a sequence of reachable charging stops that maintains the configured reserve. Do not start this trip on the supplied assumptions.")
        elif stops:
            warnings.append("Recommended stops assume the vehicle can charge to 100% at each location; charger status, compatibility, access and charging time are not verified live.")
            if any(stop["compatibility_status"] == "Unknown" for stop in stops):
                warnings.append("At least one recommended directory record has unknown vehicle-class compatibility; verify connector support before travel.")

    detour_distance_km = sum(stop["estimated_round_trip_detour_km"] for stop in stops)
    detour_energy_kwh = detour_distance_km * request.consumption_kwh_per_100km / 100
    arrival_without_charge = None
    if not requires_charging:
        arrival_without_charge = round(max(0.0, request.starting_soc_pct - journey_energy / capacity * 100), 1)

    dead_zones: list[dict[str, Any]] = []
    corr_name = corridor.get("name") or corridor.get("id") or "Corridor"
    for seg in coverage:
        if seg["coverage_status"] == "no_sampled_station_found":
            mid_km = (seg["start_km"] + seg["end_km"]) / 2
            mid_lat, mid_lon = _interpolate_corridor_point(geometry, road_factor, mid_km)
            dead_zones.append({
                "candidate_id": f"DZ-{corridor.get('id', 'corr')}-{int(seg['start_km'])}-{int(seg['end_km'])}",
                "site_name": f"{corr_name} Highway Site (KM {int(seg['start_km'])}-{int(seg['end_km'])})",
                "corridor_id": corridor.get("id", "corridor"),
                "corridor_name": corr_name,
                "state": corridor.get("states", ["India"])[0] if corridor.get("states") else "India",
                "district": "Highway Corridor",
                "latitude": round(mid_lat, 6),
                "longitude": round(mid_lon, 6),
                "segment_start_km": seg["start_km"],
                "segment_end_km": seg["end_km"],
                "estimated_cost_inr": 2500000,
                "suitability_score": 0.94,
                "origin_type": "trip_dead_zone",
                "notes": f"Highway charging gap identified along {corr_name} between KM {seg['start_km']} and {seg['end_km']}. Installing a dual-gun 60 kW DC charger bridges this corridor gap.",
            })

    cleaned_stations = [{key: value for key, value in row.items() if not key.startswith("_")} for row in near_stations]
    return {
        "corridor_id": corridor["id"], "origin": corridor["origin"], "destination": corridor["destination"],
        "vehicle_class": request.vehicle_class, "vehicle_model": request.vehicle_model,
        "battery_capacity_kwh": capacity, "starting_soc_pct": request.starting_soc_pct, "reserve_pct": request.reserve_pct,
        "consumption_kwh_per_100km": request.consumption_kwh_per_100km,
        "route_type": "representative_corridor_simulation", "route_distance_km": round(distance_km, 1),
        "route_geometry": geometry, "journey_energy_kwh": round(journey_energy, 2),
        "estimated_detour_energy_kwh": round(detour_energy_kwh, 2),
        "total_estimated_energy_kwh": round(journey_energy + detour_energy_kwh, 2),
        "available_battery_energy_kwh": round(available_energy, 2), "reserve_energy_kwh": round(reserve_energy, 2),
        "usable_energy_before_charging_kwh": round(usable_energy, 2),
        "estimated_arrival_soc_without_charging_pct": arrival_without_charge,
        "estimated_arrival_soc_after_plan_pct": round(arrival_after_plan, 1) if arrival_after_plan is not None else None,
        "requires_charging": requires_charging, "feasible_with_recommended_stops": plan_feasible,
        "charging_stops": stops, "near_route_stations": cleaned_stations,
        "coverage_segments": coverage, "state_samples": state_samples,
        "source_records_loaded": sum(row["records_loaded"] for row in state_samples),
        "source_records_matching": sum(row["total_matching_records"] for row in state_samples),
        "candidate_dead_zone_sites": dead_zones,
        "formula": "Journey energy (kWh) = estimated corridor distance (km) × consumption (kWh/100 km) ÷ 100. Available battery energy = battery capacity × starting SoC. Reserve energy = battery capacity × reserve percentage.",
        "assumptions": [
            DISTANCE_METHOD,
            f"Station proximity and corridor coverage use a {request.station_search_distance_km:g} km straight-line buffer from the illustrative route polyline.",
            f"Coverage warnings divide the route into {COVERAGE_SEGMENT_KM:g} km bins and use only retrieved valid-coordinate station rows.",
            "The station API returns at most the first 100 matching valid-coordinate records per corridor state; nearby stations can be absent from this sample.",
            "Stop detours are estimated as twice the straight-line distance from the station to the corridor; this is not road detour distance.",
            "A recommended charging stop assumes charging back to 100%; charge time, access, operational status and real-time availability are not provided.",
            "No elevation, traffic, weather, payload, speed or regenerative braking model is integrated; energy consumption is user-entered.",
        ],
        "warnings": warnings,
    }
