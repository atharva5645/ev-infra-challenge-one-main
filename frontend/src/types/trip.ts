import type { DataSourceItem } from './station'

export type TripCorridor = {
  id: string
  name: string
  origin: string
  destination: string
  states: string[]
  route_geometry: [number, number][]
  estimated_distance_km: number
  distance_method: string
}

export type TripPlanPayload = {
  corridor_id: string
  origin: string
  destination: string
  vehicle_class: '2W' | '3W' | '4W'
  vehicle_model?: string
  battery_capacity_kwh: number
  starting_soc_pct: number
  reserve_pct: number
  consumption_kwh_per_100km: number
  station_search_distance_km: number
}

export type TripStation = {
  id: string
  name: string
  latitude: number
  longitude: number
  state: string
  district: string
  charger_type: string
  power_kw?: number | null
  total_chargers: number
  total_connectors: number
  supported_vehicle_classes: string[]
  compatibility_status: 'Compatible' | 'Unknown' | 'Not listed'
  source: string
  snapshot_date: string
  distance_from_route_km: number
  route_progress_km: number
}

export type CorridorDeadZone = {
  candidate_id: string
  site_name: string
  corridor_id: string
  corridor_name: string
  state: string
  district: string
  latitude: number
  longitude: number
  segment_start_km: number
  segment_end_km: number
  estimated_cost_inr: number
  suitability_score: number
  origin_type: string
  notes: string
}

export type TripPlanResponse = {
  success: boolean
  data: {
    corridor_id: string
    origin: string
    destination: string
    vehicle_class: '2W' | '3W' | '4W'
    vehicle_model?: string | null
    battery_capacity_kwh: number
    starting_soc_pct: number
    reserve_pct: number
    consumption_kwh_per_100km: number
    route_type: 'representative_corridor_simulation'
    route_distance_km: number
    route_geometry: [number, number][]
    journey_energy_kwh: number
    estimated_detour_energy_kwh: number
    total_estimated_energy_kwh: number
    available_battery_energy_kwh: number
    reserve_energy_kwh: number
    usable_energy_before_charging_kwh: number
    estimated_arrival_soc_without_charging_pct?: number | null
    estimated_arrival_soc_after_plan_pct?: number | null
    requires_charging: boolean
    feasible_with_recommended_stops: boolean
    charging_stops: Array<TripStation & {
      stop_order: number
      estimated_arrival_soc_pct: number
      estimated_recharge_to_full_kwh: number
      estimated_round_trip_detour_km: number
    }>
    near_route_stations: TripStation[]
    coverage_segments: Array<{
      start_km: number
      end_km: number
      sampled_station_count: number
      coverage_status: 'sampled_station_nearby' | 'no_sampled_station_found'
    }>
    candidate_dead_zone_sites?: CorridorDeadZone[]
    state_samples: Array<{ state: string; records_loaded: number; total_matching_records: number; total_pages: number }>
    source_records_loaded: number
    source_records_matching: number
    formula: string
    assumptions: string[]
    warnings: string[]
  }
  meta: {
    station_source: string
    snapshot_date: string
    station_sample_scope: string
    limitations: string[]
    data_sources?: DataSourceItem[]
    assumptions_used?: string[]
    generated_at?: string
  }
}
