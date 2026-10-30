from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


class DataSourceItem(BaseModel):
    name: str
    type: Literal["official_snapshot", "synthetic_proxy", "derived_calculation", "user_input"]
    snapshot_date: str | None = None
    publisher: str | None = None
    attribution: str | None = None
    disclaimer: str | None = None


class ExplainabilityMeta(BaseModel):
    data_sources: list[DataSourceItem] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


BEE_DATA_SOURCE = DataSourceItem(
    name="BEE Public EV Charging Stations Directory",
    type="official_snapshot",
    snapshot_date="2025-10-26",
    publisher="Bureau of Energy Efficiency (BEE), Ministry of Power, Government of India",
    attribution="Data: Bureau of Energy Efficiency (BEE), Ministry of Power, Government of India - 'EV Public Charging Stations Data till 26th October 2025'.",
)

VAHAN_DATA_SOURCE = DataSourceItem(
    name="MoRTH / VAHAN EV Registration Trends",
    type="synthetic_proxy",
    snapshot_date="2025-10-01",
    publisher="Calibrated proxy based on Ministry of Road Transport and Highways (MoRTH) macro statistics",
    attribution="Calibrated to MoRTH national EV distribution benchmarks (~62% 2W, ~30% 3W, ~7% 4W, ~1% Bus).",
    disclaimer="Synthetic VAHAN-style proxy calibrated to national trends for competitive hackathon evaluation. Not a live MoRTH database dump.",
)

H3_DATA_SOURCE = DataSourceItem(
    name="Uber H3 Hexagonal Spatial Index",
    type="derived_calculation",
    snapshot_date="2025-10-26",
    publisher="Uber Technologies / H3 Spatial Library (Resolution 7 & 8)",
    attribution="Discrete Global Grid System (DGGS) H3 resolution 7 (~5.16 km²) & resolution 8 (~0.74 km²).",
)

