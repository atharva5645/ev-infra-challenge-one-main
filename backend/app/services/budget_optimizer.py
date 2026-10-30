from __future__ import annotations

import math
from typing import Any

from app.models.planning import BudgetWeights, OptimizeRequest


OBJECTIVE_WEIGHTS: dict[str, dict[str, float]] = {
    "maximum_coverage": {"coverage": 0.60, "gap_reduction": 0.25, "equity": 0.15},
    "maximum_gap_reduction": {"coverage": 0.15, "gap_reduction": 0.70, "equity": 0.15},
    "balanced_equity": {"coverage": 0.34, "gap_reduction": 0.33, "equity": 0.33},
}


def _candidate_rankings(
    *, state: str, districts: list[dict[str, Any]], unit_cost: int, weights: dict[str, float],
    candidate_sites: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    counts = [max(0, int(row["station_count"])) for row in districts]
    highest = max(counts, default=0)
    equity_values = [1 / (1 + count) for count in counts]
    highest_equity = max(equity_values, default=0)
    candidates = []
    for row, count, equity_value in zip(districts, counts, equity_values):
        coverage_value = 1.0  # One illustrative installation package reaches one candidate district.
        gap_value = 1.0 if highest == 0 else max(0.0, (highest - count) / highest)
        equity = equity_value / highest_equity if highest_equity else 0.0
        benefit = (
            weights["coverage"] * coverage_value
            + weights["gap_reduction"] * gap_value
            + weights["equity"] * equity
        )
        district = str(row["name"])
        candidates.append({
            "candidate_id": f"{state.casefold()}::{district.casefold()}",
            "state": state,
            "district": district,
            "installation_count": 1,
            "existing_station_rows": count,
            "estimated_cost_inr": unit_cost,
            "deployment_type": "AC",
            "relative_benefit_score": round(min(1.0, benefit), 6),
            "benefit_cost_ratio": round(min(1.0, benefit) / unit_cost, 12) if unit_cost else float("inf"),
            "reason": (
                f"One hypothetical station package could improve this district's relative position: "
                f"the directory lists {count:,} station rows versus {highest:,} in the highest-count district."
            ),
            "illustrative_candidate": True,
            "origin_type": "district_package",
        })

    # Integrate explicit candidate sites (such as Trip Planner highway dead zones)
    for site in (candidate_sites or []):
        c_cost = int(site.get("estimated_cost_inr", unit_cost))
        c_benefit = min(1.0, float(site.get("suitability_score", 0.92)))
        candidates.append({
            "candidate_id": site.get("candidate_id", f"site-{len(candidates)}"),
            "state": site.get("state", state),
            "district": site.get("district", "Highway Corridor"),
            "installation_count": 1,
            "existing_station_rows": 0,
            "estimated_cost_inr": c_cost,
            "deployment_type": "DC",
            "relative_benefit_score": round(c_benefit, 6),
            "benefit_cost_ratio": round(c_benefit / c_cost, 12) if c_cost else float("inf"),
            "reason": site.get("notes") or f"High-priority highway candidate: {site.get('site_name', 'Corridor Site')}",
            "illustrative_candidate": True,
            "origin_type": site.get("origin_type", "trip_dead_zone"),
            "site_name": site.get("site_name"),
            "latitude": site.get("latitude"),
            "longitude": site.get("longitude"),
        })

    return sorted(candidates, key=lambda item: (-item["benefit_cost_ratio"], -item["relative_benefit_score"], item["district"].casefold()))


def optimize_budget(request: OptimizeRequest, districts: list[dict[str, Any]]) -> dict[str, Any]:
    """Greedy benefit/cost ranking; illustrative relative scores, not global optimization."""
    raw_weights = request.weights.model_dump() if request.weights else OBJECTIVE_WEIGHTS[request.objective]
    weight_sum = sum(raw_weights.values())
    if weight_sum <= 0:
        raise ValueError("At least one optimization weight must be greater than zero.")
    weights = {key: value / weight_sum for key, value in raw_weights.items()}
    ac_share = request.ac_allocation_pct / 100
    unit_cost = math.ceil(
        ac_share * request.ac_cost_per_station_inr
        + (1 - ac_share) * request.dc_cost_per_station_inr
    )
    ranked = _candidate_rankings(
        state=request.state,
        districts=districts,
        unit_cost=unit_cost,
        weights=weights,
        candidate_sites=request.candidate_sites,
    )
    affordable: list[dict[str, Any]] = []
    remaining = request.available_budget_inr
    for candidate in ranked:
        next_count = len(affordable) + 1
        target_ac_count = math.floor(next_count * ac_share + 0.5)
        current_ac_count = sum(1 for item in affordable if item["deployment_type"] == "AC")
        deployment_type = "AC" if target_ac_count > current_ac_count else "DC"
        cost = request.ac_cost_per_station_inr if deployment_type == "AC" else request.dc_cost_per_station_inr
        if cost <= remaining:
            selected = {
                **candidate,
                "estimated_cost_inr": cost,
                "deployment_type": deployment_type,
                "benefit_cost_ratio": round(candidate["relative_benefit_score"] / cost, 12) if cost else float("inf"),
            }
            affordable.append(selected)
            remaining -= cost
        else:
            # Every remaining candidate takes the same next mix slot and has
            # the same unit cost, so none can be added without exceeding budget.
            break

    used = request.available_budget_inr - remaining
    selected_benefit = sum(item["relative_benefit_score"] for item in affordable)
    available_benefit = sum(item["relative_benefit_score"] for item in ranked)
    candidate_count = len(ranked)
    after_pct = (len(affordable) / candidate_count * 100) if candidate_count else 0.0
    return {
        "state": request.state,
        "objective": request.objective,
        "available_budget_inr": request.available_budget_inr,
        "budget_used_inr": used,
        "remaining_budget_inr": remaining,
        "proposed_installations": len(affordable),
        "ac_allocation_pct": request.ac_allocation_pct,
        "weights_applied": {key: round(value, 4) for key, value in weights.items()},
        "estimated_ac_installations": sum(1 for item in affordable if item["deployment_type"] == "AC"),
        "estimated_dc_installations": sum(1 for item in affordable if item["deployment_type"] == "DC"),
        "baseline_candidate_areas_covered": 0,
        "estimated_candidate_areas_covered": len(affordable),
        "estimated_candidate_coverage_before_pct": 0.0,
        "estimated_candidate_coverage_after_pct": round(after_pct, 1),
        "estimated_relative_benefit_gain_pct": round(selected_benefit / available_benefit * 100, 1) if available_benefit else 0.0,
        "recommendations": affordable,
        "ranked_candidates": ranked,
        "scoring_method": (
            "Greedy ranking by weighted relative benefit / estimated station-package cost. "
            "Benefit = coverage weight x 1 + gap weight x max(0, (state maximum rows - district rows) / state maximum rows; define as 1 when the maximum is zero) + equity weight x normalized 1/(1 + district rows). "
            "Coverage counts candidate districts with one hypothetical package; gap reduction compares district station rows with the state's highest-count district; equity uses inverse station rows. "
            "The ranking is heuristic and does not claim a globally optimal solution."
        ),
        "empty_reason": (
            "No district candidates were available from the selected state's directory."
            if not ranked else "No candidate package fits the available budget." if not affordable else None
        ),
    }
