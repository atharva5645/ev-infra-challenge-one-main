from __future__ import annotations

from collections import Counter
from typing import Any


POWER_BINS = (
    ("<7 kW", 0, 7),
    ("7–<22 kW", 7, 22),
    ("22–<50 kW", 22, 50),
    ("50–<150 kW", 50, 150),
    ("150+ kW", 150, float("inf")),
)


def _count_rows(rows: list[dict[str, Any]], field: str) -> list[dict[str, int | str]]:
    counts = Counter(str(row.get(field) or "Not specified") for row in rows)
    return [{"name": name, "value": count} for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0].casefold()))]


def build_page_analytics(stations: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate charts from the fetched station page only; never extrapolate it."""
    powers = [row["power_kw"] for row in stations if isinstance(row.get("power_kw"), (int, float))]
    power_counts = [
        {"name": label, "value": sum(1 for value in powers if lower <= value < upper)}
        for label, lower, upper in POWER_BINS
    ]
    return {
        "charger_type_distribution": _count_rows(stations, "charger_type"),
        "power_distribution": power_counts,
        "geographic_points": [
            {"id": row["id"], "name": row["name"], "state": row["state"], "district": row["district"],
             "latitude": row["latitude"], "longitude": row["longitude"]}
            for row in stations
        ],
        "district_distribution": _count_rows(stations, "district"),
        "stations_with_power": len(powers),
        "districts_represented": len({row.get("district") for row in stations if row.get("district")}),
    }
