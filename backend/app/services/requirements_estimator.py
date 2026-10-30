from __future__ import annotations

import math
from typing import Any

from app.models.planning import RequirementsRequest


def calculate_requirements(request: RequirementsRequest, existing_stations: int) -> dict[str, Any]:
    """Estimate station need using user-supplied EV counts and explicit ratios."""
    if existing_stations < 0:
        raise ValueError("Existing station count cannot be negative.")
    covered_population = math.ceil(request.projected_ev_population * request.target_coverage_pct / 100)
    required = math.ceil(covered_population / request.target_ev_per_station)
    additional = max(0, required - existing_stations)
    ac_count = math.floor(additional * request.ac_allocation_pct / 100 + 0.5)
    dc_count = additional - ac_count
    ac_investment = ac_count * request.ac_cost_per_station_inr
    dc_investment = dc_count * request.dc_cost_per_station_inr
    current_capacity = (
        100.0 if request.current_ev_population == 0
        else min(100.0, existing_stations * request.target_ev_per_station / request.current_ev_population * 100)
    )
    additional_share = additional / required if required else 0
    priority = "High" if additional_share >= 0.6 else "Medium" if additional_share >= 0.25 else "Maintain"

    return {
        "state": request.state,
        "vehicle_class": request.vehicle_class,
        "current_ev_population": request.current_ev_population,
        "projected_ev_population": request.projected_ev_population,
        "planning_horizon_year": request.planning_horizon_year,
        "existing_stations": existing_stations,
        "target_ev_per_station": request.target_ev_per_station,
        "target_coverage_pct": request.target_coverage_pct,
        "covered_projected_ev_population": covered_population,
        "required_stations": required,
        "additional_stations": additional,
        "additional_ac_stations": ac_count,
        "additional_dc_stations": dc_count,
        "estimated_ac_investment_inr": ac_investment,
        "estimated_dc_investment_inr": dc_investment,
        "estimated_total_investment_inr": ac_investment + dc_investment,
        "current_planning_capacity_pct": round(current_capacity, 1),
        "priority": priority,
        "formula": (
            "Required stations = ceiling(projected EV population × target coverage fraction ÷ target EVs per station); "
            "additional stations = max(0, required stations − existing station rows)."
        ),
        "assumptions": [
            "EV population counts are user-entered planning inputs, not official registration data.",
            "The target coverage percentage scales the projected EV population before applying the target EV-to-station ratio.",
            "One planned station is the costing unit; it is not an individual charger, gun, or connector.",
            "Estimated AC investment = additional AC stations × AC cost per station; estimated DC investment = additional DC stations × DC cost per station; total investment is their sum.",
            "AC/DC allocation is rounded to the nearest whole station; DC receives the remainder so totals match.",
            "Unit costs are user-entered estimates per deployed station and do not include site-specific civil works or grid upgrades unless the user includes them.",
            "Priority is Maintain below 25% additional share, Medium from 25% to below 60%, and High at 60% or above; this is a planning label, not an official classification.",
            "Current planning capacity proxy = min(100%, existing station rows × target EVs per station ÷ current EV population); when current EV population is zero it reports 100% because the denominator is zero. It is not geographic or service coverage.",
        ],
    }
