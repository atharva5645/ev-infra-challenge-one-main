from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.explainability import DataSourceItem, ExplainabilityMeta


class DistrictOption(BaseModel):
    name: str
    station_count: int = Field(ge=0)
    city_count: int = Field(ge=0)


class DistrictDirectoryMeta(BaseModel):
    state: str
    district_count: int = Field(ge=0)
    city_count: int = Field(ge=0)
    source: str
    snapshot_date: str
    attribution: str
    data_sources: list[DataSourceItem] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DistrictDirectoryResponse(BaseModel):
    success: bool = True
    data: list[DistrictOption]
    meta: DistrictDirectoryMeta


class GapWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station_scarcity: float = Field(default=0.50, ge=0, le=1)
    target_shortfall: float = Field(default=0.30, ge=0, le=1)
    vehicle_compatibility: float = Field(default=0.20, ge=0, le=1)

    @model_validator(mode="after")
    def weights_have_positive_sum(self):
        if self.station_scarcity + self.target_shortfall + self.vehicle_compatibility <= 0:
            raise ValueError("At least one scoring weight must be greater than zero.")
        return self


class GapAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str = Field(min_length=1, max_length=100)
    district: str = Field(min_length=1, max_length=120)
    vehicle_class: Literal["2W", "3W", "4W"] | None = None
    target_stations_per_district: int = Field(default=25, ge=1, le=10000)
    weights: GapWeights = Field(default_factory=GapWeights)


class GapFactor(BaseModel):
    key: Literal["station_scarcity", "target_shortfall", "vehicle_compatibility"]
    label: str
    value: float = Field(ge=0, le=1)
    requested_weight: float = Field(ge=0, le=1)
    applied_weight: float = Field(ge=0, le=1)
    explanation: str


class GapAssessmentResult(BaseModel):
    state: str
    district: str
    vehicle_class: Literal["2W", "3W", "4W"] | None
    score: float = Field(ge=0, le=100)
    priority: Literal["High", "Medium", "Monitor"]
    district_station_count: int = Field(ge=0)
    highest_district_station_count: int = Field(ge=0)
    district_rank_by_station_count: int = Field(ge=1)
    districts_in_state: int = Field(ge=1)
    compatible_records_loaded: int = Field(ge=0)
    class_records_loaded: int = Field(ge=0)
    valid_coordinate_records_loaded: int = Field(ge=0)
    compatibility_sample_coverage_pct: float = Field(ge=0, le=100)
    records_available_in_filtered_district_query: int = Field(ge=0)
    total_state_station_rows: int = Field(ge=0)
    district_distribution_source: str
    factors: list[GapFactor]
    explanation: list[str]


class GapAssessmentMeta(BaseModel):
    source: str
    publisher: str
    snapshot_date: str
    attribution: str
    target_stations_per_district: int
    scoring_method: str
    priority_thresholds: dict[str, int]
    coverage_note: str
    limitations: list[str]
    data_sources: list[DataSourceItem] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GapAssessmentResponse(BaseModel):
    success: bool = True
    data: GapAssessmentResult
    meta: GapAssessmentMeta


class SummaryDatum(BaseModel):
    name: str
    value: int = Field(ge=0)
    auxiliary_value: int | None = Field(default=None, ge=0)


class AnalyticsSummaryData(BaseModel):
    metrics: dict[str, int]
    states: list[dict]
    state_distribution: list[SummaryDatum]
    connector_distribution: list[SummaryDatum]
    operator_distribution: list[SummaryDatum]
    district_distribution: list[SummaryDatum]
    charger_type_distribution: list[SummaryDatum]
    power_distribution: list[SummaryDatum]
    geographic_points: list[dict]


class AnalyticsSummaryMeta(BaseModel):
    source: str
    publisher: str
    source_url: str | None = None
    snapshot_date: str
    snapshot_label: str
    attribution: str
    generated_at: str
    upstream_refreshed_at: str
    cache_age_seconds: int = Field(ge=0)
    stale: bool = False
    refresh_requested: bool = False
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
    total_pages: int = Field(ge=0)
    total_dataset_stations: int = Field(ge=0)
    total_matching_stations: int = Field(ge=0)
    records_loaded: int = Field(ge=0)
    active_filters: dict
    metric_scopes: dict[str, str]
    limitations: list[str]
    errors: list[str]
    data_sources: list[DataSourceItem] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)


class AnalyticsSummaryResponse(BaseModel):
    success: bool = True
    data: AnalyticsSummaryData
    meta: AnalyticsSummaryMeta


# --- New VAHAN, Hex Metrics, and Class Disparity Response Models ---

class EvRegistrationRecord(BaseModel):
    state_code: str | None = None
    district_name: str
    vehicle_class: str
    reporting_period: str
    ev_count: int = Field(ge=0)
    source_name: str


class EvRegistrationsSummary(BaseModel):
    total_evs: int
    two_wheeler_count: int
    three_wheeler_count: int
    four_wheeler_count: int
    bus_count: int
    two_wheeler_share_pct: float
    three_wheeler_share_pct: float
    four_wheeler_share_pct: float
    bus_share_pct: float


class EvRegistrationsResponse(BaseModel):
    success: bool = True
    data: list[EvRegistrationRecord]
    summary: EvRegistrationsSummary
    meta: ExplainabilityMeta


class HexCell(BaseModel):
    cell_id: str
    resolution: int
    center: list[float]
    boundary: list[list[float]]
    charger_count: int = Field(ge=0)
    fast_charger_count: int = Field(ge=0)
    ev_demand_proxy: int = Field(ge=0)
    distance_to_nearest_charger_km: float = Field(ge=0)
    coverage: float = Field(ge=0, le=1)
    gap_score: float = Field(ge=0, le=1)
    priority: Literal["High Gap", "Medium Gap", "Adequate"]


class HexMetricsSummary(BaseModel):
    high_gap_cells: int
    medium_gap_cells: int
    adequate_cells: int
    avg_nearest_charger_km: float


class HexMetricsData(BaseModel):
    resolution: int
    total_cells: int
    cells: list[HexCell]
    summary: HexMetricsSummary
    formula: str
    assumptions: list[str]


class HexMetricsResponse(BaseModel):
    success: bool = True
    data: HexMetricsData
    meta: ExplainabilityMeta


class DistrictDisparityRow(BaseModel):
    district: str
    total_stations: int
    stations_4w: int
    stations_2w3w: int
    ev_count_4w: int
    ev_count_2w3w: int
    total_evs: int
    ev_per_station_4w: float
    ev_per_station_2w3w: float
    gap_score_4w: float
    gap_score_2w3w: float
    gap_score_all: float
    rank_4w: int
    rank_2w3w: int
    rank_all_vehicles: int
    rank_divergence: int
    disparity_label: Literal["Severe 2W/3W Deficit", "Moderate 2W/3W Deficit", "Balanced Infrastructure"]


class ClassComparisonData(BaseModel):
    state: str
    total_districts_analyzed: int
    fleet_share_2w3w_pct: float
    fleet_share_4w_pct: float
    districts_with_severe_disparity_count: int
    district_comparisons: list[DistrictDisparityRow]
    policy_takeaways: list[str]
    assumptions: list[str]


class ClassComparisonResponse(BaseModel):
    success: bool = True
    data: ClassComparisonData
    meta: ExplainabilityMeta
