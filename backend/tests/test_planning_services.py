import unittest
from unittest.mock import patch

from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.models.planning import BudgetWeights, OptimizeRequest, RequirementsRequest
from app.services.budget_optimizer import optimize_budget
from app.services.gap_assessment import calculate_gap_assessment
from app.services.requirements_estimator import calculate_requirements


def requirements_input(**overrides):
    payload = {
        "state": "Karnataka",
        "vehicle_class": "4W",
        "current_ev_population": 1000,
        "projected_ev_population": 12000,
        "planning_horizon_year": 2030,
        "target_ev_per_station": 500,
        "target_coverage_pct": 100,
        "ac_allocation_pct": 70,
        "ac_cost_per_station_inr": 1000,
        "dc_cost_per_station_inr": 3000,
    }
    payload.update(overrides)
    return RequirementsRequest(**payload)


def optimizer_input(**overrides):
    payload = {
        "state": "Karnataka",
        "available_budget_inr": 100,
        "objective": "balanced_equity",
        "ac_allocation_pct": 50,
        "ac_cost_per_station_inr": 10,
        "dc_cost_per_station_inr": 30,
        "weights": {"coverage": 0.34, "gap_reduction": 0.33, "equity": 0.33},
    }
    payload.update(overrides)
    return OptimizeRequest(**payload)


class RequirementEstimatorTests(unittest.TestCase):
    def test_required_additional_ac_dc_and_investment(self):
        result = calculate_requirements(requirements_input(), existing_stations=10)
        self.assertEqual(result["required_stations"], 24)
        self.assertEqual(result["additional_stations"], 14)
        self.assertEqual(result["additional_ac_stations"], 10)
        self.assertEqual(result["additional_dc_stations"], 4)
        self.assertEqual(result["estimated_total_investment_inr"], 22000)

    def test_coverage_target_applies_to_projected_population(self):
        result = calculate_requirements(requirements_input(target_coverage_pct=50), existing_stations=0)
        self.assertEqual(result["covered_projected_ev_population"], 6000)
        self.assertEqual(result["required_stations"], 12)

    def test_zero_population_does_not_divide_by_zero(self):
        result = calculate_requirements(requirements_input(current_ev_population=0, projected_ev_population=0), existing_stations=0)
        self.assertEqual(result["required_stations"], 0)
        self.assertEqual(result["additional_stations"], 0)
        self.assertEqual(result["estimated_total_investment_inr"], 0)

    def test_negative_existing_station_count_rejected(self):
        with self.assertRaises(ValueError):
            calculate_requirements(requirements_input(), existing_stations=-1)

    def test_invalid_ratio_and_percentages_rejected(self):
        with self.assertRaises(ValidationError):
            requirements_input(target_ev_per_station=0)
        with self.assertRaises(ValidationError):
            requirements_input(ac_allocation_pct=101)
        with self.assertRaises(ValidationError):
            requirements_input(target_coverage_pct=0)
        with self.assertRaises(ValidationError):
            requirements_input(ac_allocation_pct=100, ac_cost_per_station_inr=0)


class BudgetOptimizerTests(unittest.TestCase):
    def test_recommendations_never_exceed_budget_and_mix_costs_are_exact(self):
        districts = [
            {"name": "High Count", "station_count": 100, "city_count": 3},
            {"name": "Low Count", "station_count": 0, "city_count": 1},
            {"name": "Medium Count", "station_count": 50, "city_count": 2},
        ]
        result = optimize_budget(optimizer_input(), districts)
        self.assertLessEqual(result["budget_used_inr"], result["available_budget_inr"])
        self.assertEqual(result["remaining_budget_inr"], result["available_budget_inr"] - result["budget_used_inr"])
        self.assertEqual(result["recommendations"][0]["district"], "Low Count")
        self.assertEqual(sum(row["estimated_cost_inr"] for row in result["recommendations"]), result["budget_used_inr"])
        self.assertEqual(result["estimated_ac_installations"] + result["estimated_dc_installations"], result["proposed_installations"])

    def test_budget_too_small_returns_no_installations(self):
        result = optimize_budget(optimizer_input(available_budget_inr=9), [{"name": "A", "station_count": 0, "city_count": 1}])
        self.assertEqual(result["proposed_installations"], 0)
        self.assertEqual(result["budget_used_inr"], 0)
        self.assertEqual(result["remaining_budget_inr"], 9)
        self.assertTrue(result["empty_reason"])

    def test_empty_candidate_data_is_a_valid_empty_scenario(self):
        result = optimize_budget(optimizer_input(), [])
        self.assertEqual(result["ranked_candidates"], [])
        self.assertEqual(result["recommendations"], [])
        self.assertEqual(result["proposed_installations"], 0)
        self.assertIn("No district candidates", result["empty_reason"])

    def test_invalid_weights_and_all_zero_cost_rejected(self):
        with self.assertRaises(ValidationError):
            BudgetWeights(coverage=0, gap_reduction=0, equity=0)
        with self.assertRaises(ValidationError):
            optimizer_input(ac_allocation_pct=100, ac_cost_per_station_inr=0)


class GapAssessmentTests(unittest.TestCase):
    def test_compatibility_sample_uses_filtered_total_and_reports_count_mismatch(self):
        districts = [
            {"name": "Alpha", "station_count": 1, "city_count": 1},
            {"name": "Beta", "station_count": 20, "city_count": 1},
        ]
        records = [
            {"district": "Alpha", "vehicle_classes": ["car"], "supported_vehicle_classes": ["4W"]},
            {"district": "alpha", "vehicle_classes": ["car"], "supported_vehicle_classes": ["4W"]},
        ]
        result = calculate_gap_assessment(
            state="Example", district="Alpha", vehicle_class="4W",
            target_stations_per_district=25,
            weights={"station_scarcity": 0.5, "target_shortfall": 0.3, "vehicle_compatibility": 0.2},
            districts=districts, compatible_station_records=records,
            records_available_in_filtered_district_query=4, total_state_station_rows=21,
        )
        self.assertEqual(result["compatibility_sample_coverage_pct"], 50.0)
        self.assertTrue(any("do not reconcile" in item for item in result["explanation"]))
        self.assertLessEqual(result["compatibility_sample_coverage_pct"], 100)

    def test_gap_endpoint_accepts_directory_and_station_count_mismatch(self):
        from app.main import app

        async def fake_upstream(path, params, refresh=False):
            if path == "/v1/cities":
                return {"success": True, "data": [
                    {"city": "A", "district": "Alpha", "state": "Example", "stations": 1},
                    {"city": "B", "district": "Beta", "state": "Example", "stations": 20},
                ], "meta": {"count": 2, "source": {"name": "test source"}}}
            return {"success": True, "data": [
                {"id": "evs_123456789a", "state": "Example", "latitude": 20, "longitude": 78,
                 "district": "Alpha", "city": "A", "vehicle_classes": ["car"], "chargers": []},
                {"id": "evs_123456789b", "state": "Example", "latitude": 21, "longitude": 79,
                 "district": "Alpha", "city": "A", "vehicle_classes": ["car"], "chargers": []},
            ], "meta": {"total": 4, "total_pages": 1}}

        with patch("app.main._get_upstream_json", side_effect=fake_upstream), TestClient(app) as client:
            response = client.post("/api/v1/analytics/gap-assessment", json={
                "state": "Example", "district": "Alpha", "vehicle_class": "4W",
                "target_stations_per_district": 25,
                "weights": {"station_scarcity": 0.5, "target_shortfall": 0.3, "vehicle_compatibility": 0.2},
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(any("do not reconcile" in item for item in response.json()["data"]["explanation"]))

    def test_compatibility_sample_coverage_never_exceeds_100_percent(self):
        districts = [{"name": "Alpha", "station_count": 1, "city_count": 1}]
        records = [
            {"district": "Alpha", "vehicle_classes": ["car"], "supported_vehicle_classes": ["4W"]},
            {"district": "Alpha", "vehicle_classes": ["car"], "supported_vehicle_classes": ["4W"]},
        ]
        result = calculate_gap_assessment(
            state="Example", district="Alpha", vehicle_class="4W",
            target_stations_per_district=25,
            weights={"station_scarcity": 0.5, "target_shortfall": 0.3, "vehicle_compatibility": 0.2},
            districts=districts, compatible_station_records=records,
            records_available_in_filtered_district_query=1, total_state_station_rows=1,
        )
        self.assertEqual(result["compatibility_sample_coverage_pct"], 100.0)


class PlanningEndpointValidationTests(unittest.TestCase):
    def test_invalid_requirement_request_returns_fastapi_422(self):
        from app.main import app

        payload = {
            "state": "Karnataka", "vehicle_class": "4W", "current_ev_population": 0,
            "projected_ev_population": 100, "planning_horizon_year": 2030,
            "target_ev_per_station": 0, "target_coverage_pct": 100,
            "ac_allocation_pct": 70, "ac_cost_per_station_inr": 100,
            "dc_cost_per_station_inr": 200,
        }
        with TestClient(app) as client:
            response = client.post("/api/v1/requirements", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("detail", response.json())

    def test_invalid_optimizer_weights_return_fastapi_422(self):
        from app.main import app

        payload = {
            "state": "Karnataka", "available_budget_inr": 1000,
            "objective": "balanced_equity", "ac_allocation_pct": 70,
            "ac_cost_per_station_inr": 100, "dc_cost_per_station_inr": 200,
            "weights": {"coverage": 0, "gap_reduction": 0, "equity": 0},
        }
        with TestClient(app) as client:
            response = client.post("/api/v1/optimize", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("detail", response.json())


if __name__ == "__main__":
    unittest.main()
