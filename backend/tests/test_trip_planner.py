import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.models.trip import TripPlanRequest
from app.services.trip_planner import calculate_trip_plan, find_corridor, list_corridors


def trip_request(**overrides):
    payload = {
        "corridor_id": "test-corridor",
        "origin": "Origin",
        "destination": "Destination",
        "vehicle_class": "4W",
        "battery_capacity_kwh": 50,
        "starting_soc_pct": 90,
        "reserve_pct": 15,
        "consumption_kwh_per_100km": 16,
        "station_search_distance_km": 20,
    }
    payload.update(overrides)
    return TripPlanRequest(**payload)


def simple_corridor():
    return {
        "id": "test-corridor",
        "origin": "Origin",
        "destination": "Destination",
        "route_geometry": [(0.0, 0.0), (0.0, 1.0)],
        "road_factor": 1.0,
    }


def station_record(station_id, longitude):
    return {
        "id": station_id, "name": station_id, "latitude": 0.0, "longitude": longitude,
        "state": "Test State", "district": "Test District", "charger_type": "AC",
        "power_kw": 22.0, "total_chargers": 1, "total_connectors": 1,
        "supported_vehicle_classes": ["4W"], "source": "Illustrative test fixture",
        "snapshot_date": "2025-10-26",
    }


class TripCalculationTests(unittest.TestCase):
    def test_feasible_trip_uses_required_energy_and_soc_formulas(self):
        request = trip_request()
        result = calculate_trip_plan(request, simple_corridor(), [], [], [])
        self.assertGreater(result["route_distance_km"], 110)
        self.assertAlmostEqual(result["journey_energy_kwh"], result["route_distance_km"] * 16 / 100, places=2)
        self.assertAlmostEqual(result["available_battery_energy_kwh"], 45.0)
        self.assertAlmostEqual(result["reserve_energy_kwh"], 7.5)
        self.assertTrue(result["feasible_with_recommended_stops"])
        self.assertIsNotNone(result["estimated_arrival_soc_without_charging_pct"])

    def test_infeasible_initial_charge_recommends_reachable_stops(self):
        request = trip_request(battery_capacity_kwh=10, starting_soc_pct=100, reserve_pct=10, consumption_kwh_per_100km=20)
        stations = [station_record("station-1", 0.3), station_record("station-2", 0.7)]
        result = calculate_trip_plan(request, simple_corridor(), stations, [], [])
        self.assertTrue(result["requires_charging"])
        self.assertTrue(result["feasible_with_recommended_stops"])
        self.assertEqual(len(result["charging_stops"]), 2)
        self.assertGreaterEqual(result["estimated_arrival_soc_after_plan_pct"], request.reserve_pct)

    def test_infeasible_trip_with_no_stations_does_not_return_arrival_soc(self):
        request = trip_request(battery_capacity_kwh=10, starting_soc_pct=90, reserve_pct=15, consumption_kwh_per_100km=30)
        result = calculate_trip_plan(request, simple_corridor(), [], [], [])
        self.assertTrue(result["requires_charging"])
        self.assertFalse(result["feasible_with_recommended_stops"])
        self.assertEqual(result["charging_stops"], [])
        self.assertIsNone(result["estimated_arrival_soc_after_plan_pct"])
        self.assertTrue(any("No station" in warning for warning in result["warnings"]))

    def test_vehicle_compatibility_is_considered_for_stop_recommendation(self):
        request = trip_request(battery_capacity_kwh=10, starting_soc_pct=100, reserve_pct=10, consumption_kwh_per_100km=20)
        station = {**station_record("wrong-class", 0.3), "supported_vehicle_classes": ["2W"]}
        result = calculate_trip_plan(request, simple_corridor(), [station], [], [])
        self.assertEqual(result["near_route_stations"][0]["compatibility_status"], "Not listed")
        self.assertEqual(result["charging_stops"], [])
        self.assertFalse(result["feasible_with_recommended_stops"])

    def test_invalid_capacity_soc_reserve_and_consumption_rejected(self):
        with self.assertRaises(ValidationError):
            trip_request(battery_capacity_kwh=0)
        with self.assertRaises(ValidationError):
            trip_request(starting_soc_pct=15, reserve_pct=15)
        with self.assertRaises(ValidationError):
            trip_request(consumption_kwh_per_100km=0)

    def test_representative_corridors_are_available_and_unknown_id_is_missing(self):
        corridors = list_corridors()
        self.assertGreaterEqual(len(corridors), 3)
        self.assertIsNone(find_corridor("unknown-corridor"))


class TripEndpointErrorTests(unittest.TestCase):
    def test_unknown_corridor_returns_404_without_station_fetch(self):
        from app.main import app

        payload = {
            "corridor_id": "unknown-corridor", "origin": "Origin", "destination": "Destination",
            "vehicle_class": "4W", "battery_capacity_kwh": 50, "starting_soc_pct": 90,
            "reserve_pct": 15, "consumption_kwh_per_100km": 16,
        }
        with TestClient(app) as client:
            response = client.post("/api/v1/trip/plan", json=payload)
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())


if __name__ == "__main__":
    unittest.main()
