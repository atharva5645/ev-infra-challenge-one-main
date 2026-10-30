import type { DataSourceItem, VehicleClass } from './station'

export type RequirementsPayload = {
  state: string
  vehicle_class: VehicleClass
  current_ev_population: number
  projected_ev_population: number
  planning_horizon_year: number
  target_ev_per_station: number
  target_coverage_pct: number
  ac_allocation_pct: number
  ac_cost_per_station_inr: number
  dc_cost_per_station_inr: number
}

export type RequirementsResponse = {
  success: boolean
  data: {
    state: string
    vehicle_class: VehicleClass
    current_ev_population: number
    projected_ev_population: number
    planning_horizon_year: number
    existing_stations: number
    existing_count_unit: 'stations'
    target_ev_per_station: number
    target_coverage_pct: number
    covered_projected_ev_population: number
    required_stations: number
    additional_stations: number
    additional_ac_stations: number
    additional_dc_stations: number
    estimated_ac_investment_inr: number
    estimated_dc_investment_inr: number
    estimated_total_investment_inr: number
    current_planning_capacity_pct: number
    priority: 'High' | 'Medium' | 'Maintain'
    formula: string
    assumptions: string[]
  }
  meta: {
    source: string
    snapshot_date: string
    source_url?: string | null
    geography_scope: string
    count_unit: 'stations'
    limitations: string[]
    data_sources?: DataSourceItem[]
    assumptions_used?: string[]
    generated_at?: string
  }
}

export type CandidateSite = {
  candidate_id: string
  site_name?: string
  state?: string
  district?: string
  latitude?: number
  longitude?: number
  estimated_cost_inr?: number
  suitability_score?: number
  origin_type?: string
  notes?: string
}

export type OptimizePayload = {
  state: string
  available_budget_inr: number
  objective: 'maximum_coverage' | 'maximum_gap_reduction' | 'balanced_equity'
  ac_allocation_pct: number
  ac_cost_per_station_inr: number
  dc_cost_per_station_inr: number
  weights: { coverage: number; gap_reduction: number; equity: number }
  candidate_sites?: CandidateSite[]
}

export type RecommendedArea = {
  candidate_id: string
  state: string
  district: string
  installation_count: number
  existing_station_rows: number
  estimated_cost_inr: number
  deployment_type: 'AC' | 'DC'
  relative_benefit_score: number
  benefit_cost_ratio: number
  reason: string
  illustrative_candidate: boolean
  origin_type?: string
  site_name?: string
  latitude?: number
  longitude?: number
}

export type OptimizeResponse = {
  success: boolean
  data: {
    state: string
    objective: string
    available_budget_inr: number
    budget_used_inr: number
    remaining_budget_inr: number
    proposed_installations: number
    ac_allocation_pct: number
    weights_applied: { coverage: number; gap_reduction: number; equity: number }
    estimated_ac_installations: number
    estimated_dc_installations: number
    baseline_candidate_areas_covered: number
    estimated_candidate_areas_covered: number
    estimated_candidate_coverage_before_pct: number
    estimated_candidate_coverage_after_pct: number
    estimated_relative_benefit_gain_pct: number
    recommendations: RecommendedArea[]
    ranked_candidates: Array<{
      candidate_id: string
      district: string
      existing_station_rows: number
      estimated_cost_inr: number
      relative_benefit_score: number
      benefit_cost_ratio: number
      reason: string
      origin_type?: string
      site_name?: string
      latitude?: number
      longitude?: number
    }>
    scoring_method: string
    empty_reason?: string | null
  }
  meta: {
    source: string
    snapshot_date: string
    candidate_scope: string
    station_count_unit: 'station rows'
    limitations: string[]
    data_sources?: DataSourceItem[]
    assumptions_used?: string[]
    generated_at?: string
  }
}
