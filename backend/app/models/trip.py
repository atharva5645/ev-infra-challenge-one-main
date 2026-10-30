from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.explainability import DataSourceItem, ExplainabilityMeta


class TripCorridor(BaseModel):
    id: str
    name: str
    origin: str
    destination: str
    states: list[str]
    route_geometry: list[tuple[float, float]]
    estimated_distance_km: float = Field(gt=0)
    distance_method: str


class TripCorridorsResponse(BaseModel):
    success: bool = True
    data: list[TripCorridor]
    meta: ExplainabilityMeta | None = None


class TripPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corridor_id: str = Field(min_length=1, max_length=80)
    origin: str = Field(min_length=1, max_length=100)
    destination: str = Field(min_length=1, max_length=100)
    vehicle_class: Literal["2W", "3W", "4W"]
    vehicle_model: str | None = Field(default=None, max_length=100)
    battery_capacity_kwh: float = Field(gt=0, le=500)
    starting_soc_pct: float = Field(ge=0, le=100)
    reserve_pct: float = Field(ge=0, le=100)
    consumption_kwh_per_100km: float = Field(gt=0, le=200)
    station_search_distance_km: float = Field(gt=0, le=200, default=35)

    @model_validator(mode="after")
    def soc_must_exceed_reserve(self):
        if self.starting_soc_pct <= self.reserve_pct:
            raise ValueError("Starting state of charge must be greater than the minimum arrival reserve.")
        return self


class TripStation(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    state: str
    district: str
    charger_type: str
    power_kw: float | None = None
    total_chargers: int
    total_connectors: int
    supported_vehicle_classes: list[str]
    compatibility_status: Literal["Compatible", "Unknown", "Not listed"]
    source: str
    snapshot_date: str
    distance_from_route_km: float = Field(ge=0)
    route_progress_km: float = Field(ge=0)


class TripChargingStop(TripStation):
    stop_order: int = Field(ge=1)
    estimated_arrival_soc_pct: float = Field(ge=0, le=100)
    estimated_recharge_to_full_kwh: float = Field(ge=0)
    estimated_round_trip_detour_km: float = Field(ge=0)


class TripCoverageSegment(BaseModel):
    start_km: float = Field(ge=0)
    end_km: float = Field(gt=0)
    sampled_station_count: int = Field(ge=0)
    coverage_status: Literal["sampled_station_nearby", "no_sampled_station_found"]


class TripStateSample(BaseModel):
    state: str
    records_loaded: int = Field(ge=0)
    total_matching_records: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class TripPlanResult(BaseModel):
    corridor_id: str
    origin: str
    destination: str
    vehicle_class: Literal["2W", "3W", "4W"]
    vehicle_model: str | None
    battery_capacity_kwh: float
    starting_soc_pct: float
    reserve_pct: float
    consumption_kwh_per_100km: float
    route_type: Literal["representative_corridor_simulation"]
    route_distance_km: float = Field(gt=0)
    route_geometry: list[tuple[float, float]]
    journey_energy_kwh: float = Field(ge=0)
    estimated_detour_energy_kwh: float = Field(ge=0)
    total_estimated_energy_kwh: float = Field(ge=0)
    available_battery_energy_kwh: float = Field(ge=0)
    reserve_energy_kwh: float = Field(ge=0)
    usable_energy_before_charging_kwh: float = Field(ge=0)
    estimated_arrival_soc_without_charging_pct: float | None = Field(default=None, ge=0, le=100)
    estimated_arrival_soc_after_plan_pct: float | None = Field(default=None, ge=0, le=100)
    requires_charging: bool
    feasible_with_recommended_stops: bool
    charging_stops: list[TripChargingStop]
    near_route_stations: list[TripStation]
    coverage_segments: list[TripCoverageSegment]
    state_samples: list[TripStateSample]
    source_records_loaded: int = Field(ge=0)
    source_records_matching: int = Field(ge=0)
    formula: str
    assumptions: list[str]
    warnings: list[str]
    candidate_dead_zone_sites: list[dict] = Field(default_factory=list)


class TripPlanMeta(BaseModel):
    station_source: str
    snapshot_date: str
    station_sample_scope: str
    limitations: list[str]
    data_sources: list[DataSourceItem] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TripPlanResponse(BaseModel):
    success: bool = True
    data: TripPlanResult
    meta: TripPlanMeta
