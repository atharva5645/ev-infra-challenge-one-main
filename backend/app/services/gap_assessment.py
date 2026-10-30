from __future__ import annotations

from typing import Any


def calculate_gap_assessment(
    *,
    state: str,
    district: str,
    vehicle_class: str | None,
    target_stations_per_district: int,
    weights: dict[str, float],
    districts: list[dict[str, Any]],
    compatible_station_records: list[dict[str, Any]],
    records_available_in_filtered_district_query: int,
    total_state_station_rows: int,
) -> dict[str, Any]:
    """Calculate a deterministic station-distribution proxy, not a coverage model."""
    selected = next((row for row in districts if row["name"].casefold() == district.casefold()), None)
    if selected is None:
        raise ValueError("The selected district is not present in the upstream state directory.")

    station_counts = [int(row["station_count"]) for row in districts]
    highest_count = max(station_counts, default=0)
    district_count = int(selected["station_count"])
    station_scarcity = 1.0 - (district_count / highest_count) if highest_count else 0.0
    target_shortfall = max(0.0, (target_stations_per_district - district_count) / target_stations_per_district)

    district_records = [
        row for row in compatible_station_records
        if str(row.get("district", "")).casefold() == selected["name"].casefold()
    ]
    class_known = [row for row in district_records if row.get("vehicle_classes")]
    class_compatible = [row for row in class_known if vehicle_class in (row.get("supported_vehicle_classes") or [])]
    compatibility_gap = None
    if vehicle_class and class_known:
        compatibility_gap = 1.0 - (len(class_compatible) / len(class_known))

    factor_specs = [
        ("station_scarcity", "Relative station scarcity", station_scarcity,
         "1 - district station rows / highest district station rows in the selected state's directory."),
        ("target_shortfall", "Illustrative target shortfall", target_shortfall,
         f"max(0, (illustrative target {target_stations_per_district} - district rows) / target)."),
    ]
    if compatibility_gap is not None:
        factor_specs.append((
            "vehicle_compatibility", "Vehicle compatibility gap", compatibility_gap,
            f"1 - compatible records / records with compatibility data in the loaded {selected['name']} page.",
        ))

    active_weight_sum = sum(weights[key] for key, *_ in factor_specs)
    if active_weight_sum <= 0:
        # This can happen only when vehicle compatibility is the sole enabled
        # factor but this source page has no compatibility values.
        raise ValueError("No configured scoring weight has supporting data for this analysis.")

    factors: list[dict[str, Any]] = []
    weighted_score = 0.0
    for key, label, value, explanation in factor_specs:
        requested_weight = weights[key]
        applied_weight = requested_weight / active_weight_sum
        weighted_score += value * applied_weight
        factors.append({
            "key": key,
            "label": label,
            "value": round(value, 4),
            "requested_weight": requested_weight,
            "applied_weight": round(applied_weight, 4),
            "explanation": explanation,
        })

    score = round(weighted_score * 100, 1)
    priority = "High" if score >= 70 else "Medium" if score >= 40 else "Monitor"
    ordered_counts = sorted((int(row["station_count"]) for row in districts), reverse=True)
    rank = 1 + sum(1 for count in ordered_counts if count > district_count)
    class_loaded = len(class_known) if vehicle_class else 0
    compatible_loaded = len(class_compatible) if vehicle_class else 0
    # Compatibility observations come from a capped /stations query. Use that
    # query's matching total as the denominator, not the /cities aggregate:
    # these upstream directory views can disagree and the sample can exceed
    # the aggregate count for a district.
    sample_coverage_pct = (
        min(100.0, class_loaded / records_available_in_filtered_district_query * 100)
        if records_available_in_filtered_district_query > 0 else 0.0
    )

    explanation = [
        f"The directory lists {district_count:,} station rows for {selected['name']}; this is rank {rank} of {len(districts)} districts by listed station rows in {state}.",
        f"The illustrative planning target is {target_stations_per_district} station rows per district; change it to see how the assumption affects the score.",
    ]
    if vehicle_class:
        if class_known:
            explanation.append(
                f"{len(class_compatible)} of {len(class_known)} loaded records with compatibility data support {vehicle_class}; compatibility is estimated from at most 100 valid-coordinate station records."
            )
        else:
            explanation.append("The source page has no vehicle-compatibility values for this district, so that factor is excluded and remaining weights are renormalized.")
    if station_scarcity >= 0.5:
        explanation.append("This district's listed station count is at most half the highest district count in the state directory.")
    if district_count < target_stations_per_district:
        explanation.append("The listed count is below the illustrative per-district target.")
    if not any("This district's listed" in item or "below the illustrative" in item for item in explanation):
        explanation.append("The available station-count proxy does not flag a strong relative shortfall under the selected assumptions.")
    if district_count != records_available_in_filtered_district_query:
        explanation.append(
            f"The upstream district directory reports {district_count:,} station rows while the filtered station endpoint reports {records_available_in_filtered_district_query:,} matching records; these source views do not reconcile. The gap score uses the district-directory count, and the filtered query is used only for compatibility evidence."
        )

    return {
        "state": state,
        "district": selected["name"],
        "vehicle_class": vehicle_class,
        "score": score,
        "priority": priority,
        "district_station_count": district_count,
        "highest_district_station_count": highest_count,
        "district_rank_by_station_count": rank,
        "districts_in_state": len(districts),
        "compatible_records_loaded": compatible_loaded,
        "class_records_loaded": class_loaded,
        "valid_coordinate_records_loaded": len(district_records),
        "compatibility_sample_coverage_pct": round(sample_coverage_pct, 2),
        "records_available_in_filtered_district_query": records_available_in_filtered_district_query,
        "total_state_station_rows": total_state_station_rows,
        "district_distribution_source": "Upstream /v1/cities state directory, station rows summed by district.",
        "factors": factors,
        "explanation": explanation,
    }
