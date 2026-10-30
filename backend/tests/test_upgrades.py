import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.services.hex_analytics import compute_hex_metrics
from app.services.class_disparity import analyze_class_disparity
from app.services.budget_optimizer import optimize_budget
from app.models.planning import OptimizeRequest


class UpgradeFeaturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check_operational(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "operational")

    def test_ev_registrations_endpoint_and_shares(self):
        resp = self.client.get("/api/v1/analytics/ev-registrations?state=Karnataka")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("data", data)
        self.assertIn("summary", data)
        self.assertIn("meta", data)
        summary = data["summary"]
        self.assertGreater(summary["total_evs"], 0)
        # Check that 2W dominates (>50%)
        self.assertGreater(summary["two_wheeler_share_pct"], 50.0)
        # Check explainability metadata
        self.assertGreater(len(data["meta"]["data_sources"]), 0)
        self.assertIn("generated_at", data["meta"])

    def test_hex_metrics_computation_and_boundaries(self):
        sample_stations = [
            {"id": "s1", "latitude": 12.9716, "longitude": 77.5946, "charger_type": "DC fast"},
            {"id": "s2", "latitude": 12.9698, "longitude": 77.7500, "charger_type": "AC"},
            {"id": "s3", "latitude": 12.8452, "longitude": 77.6602, "charger_type": "DC fast"},
        ]
        result = compute_hex_metrics(sample_stations, resolution=7, district_ev_demand=4000)
        self.assertEqual(result["resolution"], 7)
        self.assertGreater(result["total_cells"], 0)
        # Verify hex boundary vertices
        first_cell = result["cells"][0]
        self.assertEqual(len(first_cell["boundary"]), 6)  # Standard hexagon has 6 vertices
        self.assertIn("gap_score", first_cell)
        self.assertIn("distance_to_nearest_charger_km", first_cell)
        self.assertIn("priority", first_cell)
        self.assertIn(first_cell["priority"], ["High Gap", "Medium Gap", "Adequate"])

    def test_hex_metrics_api_endpoint(self):
        resp = self.client.get("/api/v1/analytics/hex-metrics?state=Karnataka&resolution=7")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("cells", data["data"])
        self.assertIn("data_sources", data["meta"])

    def test_class_disparity_analysis(self):
        districts = [
            {"name": "Metro District", "station_count": 50},
            {"name": "Suburban District", "station_count": 5},
        ]
        stations = {
            "metro district": [{"supported_vehicle_classes": ["4W"], "vehicle_classes": ["car"]}] * 45
            + [{"supported_vehicle_classes": ["2W"], "vehicle_classes": ["two_three_wheeler"]}] * 5,
            "suburban district": [{"supported_vehicle_classes": ["2W", "3W"], "vehicle_classes": ["two_three_wheeler"]}] * 5,
        }
        vahan_counts = {
            "metro district": {"Two-wheeler": 12000, "Three-wheeler": 3000, "Four-wheeler": 2000},
            "suburban district": {"Two-wheeler": 4000, "Three-wheeler": 1000, "Four-wheeler": 100},
        }
        result = analyze_class_disparity("Karnataka", districts, stations, vahan_counts)
        self.assertEqual(result["total_districts_analyzed"], 2)
        self.assertGreater(result["fleet_share_2w3w_pct"], 80.0)
        comp = result["district_comparisons"]
        # Metro district with mostly 4W chargers should have high 2W/3W deficit
        metro_row = next(r for r in comp if r["district"] == "Metro District")
        self.assertGreater(metro_row["ev_per_station_2w3w"], metro_row["ev_per_station_4w"])

    def test_class_comparison_api_endpoint(self):
        resp = self.client.get("/api/v1/analytics/class-comparison?state=Karnataka")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("district_comparisons", data["data"])
        self.assertIn("policy_takeaways", data["data"])

    def test_trip_planner_generates_dead_zones_and_feeds_optimizer(self):
        resp = self.client.get("/api/v1/planning/candidate-sites?include_corridor_dead_zones=true")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        sites = data["data"]
        self.assertGreater(len(sites), 0)
        dead_zone_sites = [s for s in sites if s.get("origin_type") == "trip_dead_zone"]
        self.assertGreater(len(dead_zone_sites), 0)

        # Test feeding candidate sites into Budget Optimizer
        req = OptimizeRequest(
            state="Karnataka",
            available_budget_inr=10_000_000,
            objective="maximum_gap_reduction",
            ac_allocation_pct=50,
            ac_cost_per_station_inr=1_500_000,
            dc_cost_per_station_inr=2_500_000,
            candidate_sites=dead_zone_sites[:3],
        )
        districts = [
            {"name": "Bengaluru Urban", "station_count": 100},
            {"name": "Mysuru", "station_count": 20},
        ]
        opt_res = optimize_budget(req, districts)
        self.assertGreater(opt_res["proposed_installations"], 0)
        # Ensure candidate sites are present in ranked list
        ranked = opt_res["ranked_candidates"]
        has_dead_zone = any(c.get("origin_type") == "trip_dead_zone" for c in ranked)
        self.assertTrue(has_dead_zone)

    def test_explainability_in_chargers_and_states(self):
        c_resp = self.client.get("/api/v1/chargers?limit=5")
        self.assertEqual(c_resp.status_code, 200)
        c_meta = c_resp.json()["meta"]
        self.assertIn("data_sources", c_meta)
        self.assertIn("assumptions_used", c_meta)
        self.assertIn("generated_at", c_meta)

        s_resp = self.client.get("/api/v1/states")
        self.assertEqual(s_resp.status_code, 200)
        s_meta = s_resp.json()["meta"]
        self.assertIn("data_sources", s_meta)
        self.assertIn("assumptions_used", s_meta)
        self.assertIn("generated_at", s_meta)


if __name__ == "__main__":
    unittest.main()

