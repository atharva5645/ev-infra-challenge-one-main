export type VehicleClass = '2W' | '3W' | '4W'

export type DataSourceItem = {
  name: string
  type: 'official_snapshot' | 'synthetic_proxy' | 'derived_calculation' | 'user_input'
  snapshot_date?: string
  publisher?: string
  attribution?: string
  disclaimer?: string
}

export type ExplainabilityMeta = {
  data_sources?: DataSourceItem[]
  assumptions_used?: string[]
  generated_at?: string
}

export type MapStation = {
  id: string
  name: string
  latitude: number
  longitude: number
  state: string
  stateCode?: string
  district: string
  city?: string
  operator?: string
  address?: string
  chargerType: string
  standards?: string[]
  powerKw?: number
  totalChargers?: number
  totalConnectors?: number
  vehicleClasses?: string[]
  supportedVehicleClasses: VehicleClass[] | null
  source: string
  snapshotDate?: string
  isDemo: boolean
  confidence?: number
}

export type ChargerPageMeta = {
  page: number
  limit: number
  loaded: number
  totalAvailable: number
  totalPages: number
  source: string
  publisher: string
  sourceUrl?: string
  snapshotDate: string
  snapshotLabel: string
  attribution: string
  data_sources?: DataSourceItem[]
  assumptions_used?: string[]
  generated_at?: string
}

export type StateOption = {
  name: string
  code: string
  stations: number
  chargers?: number
  dc_stations?: number
  car_fast_dc_stations?: number
  type?: string
}

export type DistrictOption = { name: string; station_count: number; city_count: number }

export type GapWeights = {
  station_scarcity: number
  target_shortfall: number
  vehicle_compatibility: number
}

export type GapAssessmentPayload = {
  state: string
  district: string
  vehicle_class: VehicleClass | null
  target_stations_per_district: number
  weights: GapWeights
}

export type GapFactor = {
  key: string
  label: string
  value: number
  requested_weight: number
  applied_weight: number
  explanation: string
}

export type GapAssessmentResponse = {
  success: boolean
  data: {
    state: string
    district: string
    vehicle_class: VehicleClass | null
    score: number
    priority: 'High' | 'Medium' | 'Monitor'
    district_station_count: number
    highest_district_station_count: number
    district_rank_by_station_count: number
    districts_in_state: number
    compatible_records_loaded: number
    class_records_loaded: number
    valid_coordinate_records_loaded: number
    compatibility_sample_coverage_pct: number
    records_available_in_filtered_district_query: number
    total_state_station_rows: number
    district_distribution_source: string
    factors: GapFactor[]
    explanation: string[]
  }
  meta: {
    source: string
    publisher: string
    snapshot_date: string
    attribution: string
    target_stations_per_district: number
    scoring_method: string
    priority_thresholds: Record<string, number>
    coverage_note: string
    limitations: string[]
    data_sources?: DataSourceItem[]
    assumptions_used?: string[]
    generated_at?: string
  }
}

export type AnalyticsDatum = { name: string; value: number; auxiliary_value?: number | null }
export type AnalyticsSummary = {
  success: boolean
  data: {
    metrics: Record<string, number>
    states: StateOption[]
    state_distribution: AnalyticsDatum[]
    connector_distribution: AnalyticsDatum[]
    operator_distribution: AnalyticsDatum[]
    district_distribution: AnalyticsDatum[]
    charger_type_distribution: AnalyticsDatum[]
    power_distribution: AnalyticsDatum[]
    geographic_points: Array<Pick<MapStation, 'id' | 'name' | 'state' | 'district' | 'latitude' | 'longitude'>>
  }
  meta: {
    source: string
    publisher: string
    source_url?: string | null
    snapshot_date: string
    snapshot_label: string
    attribution: string
    generated_at: string
    upstream_refreshed_at: string
    cache_age_seconds: number
    stale: boolean
    refresh_requested: boolean
    page: number
    limit: number
    total_pages: number
    total_dataset_stations: number
    total_matching_stations: number
    records_loaded: number
    active_filters: { state?: string | null; district?: string | null; vehicle_class?: VehicleClass | null; upstream_vehicle?: string | null }
    metric_scopes: Record<string, string>
    limitations: string[]
    errors: string[]
    data_sources?: DataSourceItem[]
    assumptions_used?: string[]
  }
}

export type HexCell = {
  cell_id: string
  resolution: number
  center: [number, number]
  boundary: [number, number][]
  charger_count: number
  fast_charger_count: number
  ev_demand_proxy: number
  distance_to_nearest_charger_km: number
  coverage: number
  gap_score: number
  priority: 'High Gap' | 'Medium Gap' | 'Adequate'
}

export type HexMetricsResponse = {
  success: boolean
  data: {
    resolution: number
    total_cells: number
    cells: HexCell[]
    summary: {
      high_gap_cells: number
      medium_gap_cells: number
      adequate_cells: number
      avg_nearest_charger_km: number
    }
    formula: string
    assumptions: string[]
  }
  meta: ExplainabilityMeta
}

export type DistrictDisparityRow = {
  district: string
  total_stations: number
  stations_4w: number
  stations_2w3w: number
  ev_count_4w: number
  ev_count_2w3w: number
  total_evs: number
  ev_per_station_4w: number
  ev_per_station_2w3w: number
  gap_score_4w: number
  gap_score_2w3w: number
  gap_score_all: number
  rank_4w: number
  rank_2w3w: number
  rank_all_vehicles: number
  rank_divergence: number
  disparity_label: 'Severe 2W/3W Deficit' | 'Moderate 2W/3W Deficit' | 'Balanced Infrastructure'
}

export type ClassComparisonResponse = {
  success: boolean
  data: {
    state: string
    total_districts_analyzed: number
    fleet_share_2w3w_pct: number
    fleet_share_4w_pct: number
    districts_with_severe_disparity_count: number
    district_comparisons: DistrictDisparityRow[]
    policy_takeaways: string[]
    assumptions: string[]
  }
  meta: ExplainabilityMeta
}

export type EvRegistrationRecord = {
  state_code?: string | null
  district_name: string
  vehicle_class: string
  reporting_period: string
  ev_count: number
  source_name: string
}

export type EvRegistrationsResponse = {
  success: boolean
  data: EvRegistrationRecord[]
  summary: {
    total_evs: number
    two_wheeler_count: number
    three_wheeler_count: number
    four_wheeler_count: number
    bus_count: number
    two_wheeler_share_pct: number
    three_wheeler_share_pct: number
    four_wheeler_share_pct: number
    bus_share_pct: number
  }
  meta: ExplainabilityMeta
}
