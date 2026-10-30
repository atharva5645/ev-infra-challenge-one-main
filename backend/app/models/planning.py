from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.explainability import DataSourceItem, ExplainabilityMeta

VehicleClass = Literal["2W", "3W", "4W"]


class RequirementsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str = Field(min_length=1, max_length=100)
    vehicle_class: VehicleClass
    current_ev_population: int = Field(ge=0, le=1_000_000_000)
    projected_ev_population: int = Field(ge=0, le=1_000_000_000)
    planning_horizon_year: int = Field(ge=2026, le=2100)
    target_ev_per_station: int = Field(gt=0, le=10_000_000)
    target_coverage_pct: float = Field(gt=0, le=100)
    ac_allocation_pct: float = Field(ge=0, le=100)
    ac_cost_per_station_inr: int = Field(ge=0, le=10_000_000_000)
    dc_cost_per_station_inr: int = Field(ge=0, le=10_000_000_000)

    @model_validator(mode="after")
    def positive_blended_cost(self):
        ac = self.ac_allocation_pct / 100
        if ac * self.ac_cost_per_station_inr + (1 - ac) * self.dc_cost_per_station_inr <= 0:
            raise ValueError("At least one station type used by the selected AC/DC allocation must have a positive cost.")
        return self


class RequirementsResult(BaseModel):
    state: str
    vehicle_class: VehicleClass
    current_ev_population: int
    projected_ev_population: int
    planning_horizon_year: int
    existing_stations: int
    existing_count_unit: Literal["stations"] = "stations"
    target_ev_per_station: int
    target_coverage_pct: float
    covered_projected_ev_population: int
    required_stations: int
    additional_stations: int
    additional_ac_stations: int
    additional_dc_stations: int
    estimated_ac_investment_inr: int
    estimated_dc_investment_inr: int
    estimated_total_investment_inr: int
    current_planning_capacity_pct: float
    priority: Literal["High", "Medium", "Maintain"]
    formula: str
    assumptions: list[str]


class RequirementsMeta(BaseModel):
    source: str
    snapshot_date: str
    source_url: str | None = None
    geography_scope: str
    count_unit: Literal["stations"] = "stations"
    limitations: list[str]
    data_sources: list[DataSourceItem] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RequirementsResponse(BaseModel):
    success: bool = True
    data: RequirementsResult
    meta: RequirementsMeta


class BudgetWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage: float = Field(default=0.33, ge=0, le=1)
    gap_reduction: float = Field(default=0.33, ge=0, le=1)
    equity: float = Field(default=0.34, ge=0, le=1)

    @model_validator(mode="after")
    def positive_sum(self):
        if self.coverage + self.gap_reduction + self.equity <= 0:
            raise ValueError("At least one optimization weight must be greater than zero.")
        return self


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str = Field(min_length=1, max_length=100)
    available_budget_inr: int = Field(ge=0, le=1_000_000_000_000_000)
    objective: Literal["maximum_coverage", "maximum_gap_reduction", "balanced_equity"] = "balanced_equity"
    ac_allocation_pct: float = Field(default=70, ge=0, le=100)
    ac_cost_per_station_inr: int = Field(default=1_500_000, ge=0, le=10_000_000_000)
    dc_cost_per_station_inr: int = Field(default=3_500_000, ge=0, le=10_000_000_000)
    weights: BudgetWeights | None = None
    candidate_sites: list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def positive_blended_cost(self):
        ac = self.ac_allocation_pct / 100
        if ac * self.ac_cost_per_station_inr + (1 - ac) * self.dc_cost_per_station_inr <= 0:
            raise ValueError("At least one station type used by the selected AC/DC allocation must have a positive cost.")
        return self


class RecommendedArea(BaseModel):
    candidate_id: str
    state: str
    district: str
    installation_count: int = Field(ge=1)
    existing_station_rows: int = Field(ge=0)
    estimated_cost_inr: int = Field(ge=0)
    deployment_type: Literal["AC", "DC"] = "AC"
    relative_benefit_score: float = Field(ge=0, le=1)
    benefit_cost_ratio: float = Field(ge=0)
    reason: str
    illustrative_candidate: bool = True
    origin_type: str = "district_package"
    site_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class OptimizeResult(BaseModel):
    state: str
    objective: str
    available_budget_inr: int
    budget_used_inr: int
    remaining_budget_inr: int
    proposed_installations: int
    ac_allocation_pct: float
    weights_applied: dict[str, float]
    estimated_ac_installations: int
    estimated_dc_installations: int
    baseline_candidate_areas_covered: int
    estimated_candidate_areas_covered: int
    estimated_candidate_coverage_before_pct: float
    estimated_candidate_coverage_after_pct: float
    estimated_relative_benefit_gain_pct: float
    recommendations: list[RecommendedArea]
    ranked_candidates: list[RecommendedArea]
    scoring_method: str
    empty_reason: str | None = None


class OptimizeMeta(BaseModel):
    source: str
    snapshot_date: str
    candidate_scope: str
    station_count_unit: Literal["station rows"] = "station rows"
    limitations: list[str]
    data_sources: list[DataSourceItem] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OptimizeResponse(BaseModel):
    success: bool = True
    data: OptimizeResult
    meta: OptimizeMeta
