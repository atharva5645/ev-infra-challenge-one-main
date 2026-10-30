import type {
  AnalyticsSummary,
  ChargerPageMeta,
  ClassComparisonResponse,
  DistrictOption,
  EvRegistrationsResponse,
  GapAssessmentPayload,
  GapAssessmentResponse,
  HexMetricsResponse,
  MapStation,
  StateOption,
  VehicleClass,
} from '../types/station'
import type { CandidateSite, OptimizePayload, OptimizeResponse, RequirementsPayload, RequirementsResponse } from '../types/planning'
import type { TripCorridor, TripPlanPayload, TripPlanResponse } from '../types/trip'

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')
).replace(/\/$/, '')

type RawCharger = {
  id: string
  name: string
  latitude: number
  longitude: number
  state: string
  state_code?: string | null
  district: string
  city?: string | null
  operator?: string | null
  address?: string | null
  charger_type: string
  standards?: string[]
  power_kw?: number | null
  total_chargers?: number
  total_connectors?: number
  vehicle_classes?: string[]
  supported_vehicle_classes?: VehicleClass[]
  source: string
  snapshot_date?: string
  is_demo: boolean
}

type ChargersResponse = {
  success: boolean
  data: RawCharger[]
  meta: {
    page: number
    limit: number
    loaded: number
    total_available: number
    total_pages: number
    source: string
    publisher: string
    source_url?: string | null
    snapshot_date: string
    snapshot_label: string
    attribution: string
  }
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers: { Accept: 'application/json', ...init.headers } })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new Error('Could not reach the local FastAPI backend. Check that it is running, then retry.')
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = payload?.detail
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((issue) => issue?.msg).filter(Boolean).join(' ')
      : detail?.message || detail?.error?.message || detail?.upstream?.error?.message || payload?.message
    const retryAfter = response.headers.get('Retry-After')
    throw new Error(`${message || `Charger API request failed (${response.status})`}${retryAfter ? ` Retry after ${retryAfter}s.` : ''}`)
  }
  if (!payload || payload.success !== true || payload.data === undefined) {
    throw new Error('The FastAPI backend returned an invalid response.')
  }
  return payload as T
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(path, { signal })
}

function normalizeCharger(raw: RawCharger): MapStation {
  if (!raw.id || !raw.state || !Number.isFinite(raw.latitude) || !Number.isFinite(raw.longitude)
      || raw.latitude < -90 || raw.latitude > 90 || raw.longitude < -180 || raw.longitude > 180) {
    throw new Error('A charger record from the backend failed coordinate or identity validation.')
  }
  return {
    id: raw.id,
    name: raw.name || raw.operator || raw.id,
    latitude: raw.latitude,
    longitude: raw.longitude,
    state: raw.state,
    stateCode: raw.state_code || undefined,
    district: raw.district || 'District unavailable',
    city: raw.city || undefined,
    operator: raw.operator || undefined,
    address: raw.address || undefined,
    chargerType: raw.charger_type || raw.standards?.join(' / ') || 'Not specified',
    standards: raw.standards || [],
    powerKw: typeof raw.power_kw === 'number' ? raw.power_kw : undefined,
    totalChargers: raw.total_chargers,
    totalConnectors: raw.total_connectors,
    vehicleClasses: raw.vehicle_classes || [],
    supportedVehicleClasses: raw.supported_vehicle_classes || [],
    source: raw.source,
    snapshotDate: raw.snapshot_date,
    isDemo: raw.is_demo,
  }
}

export async function loadChargers(options: {
  state?: string
  district?: string
  page?: number
  limit?: number
  signal?: AbortSignal
}): Promise<{ stations: MapStation[]; meta: ChargerPageMeta }> {
  const params = new URLSearchParams({ page: String(options.page ?? 1), limit: String(options.limit ?? 100) })
  if (options.state) params.set('state', options.state)
  if (options.district) params.set('district', options.district)
  const result = await getJson<ChargersResponse>(`/api/v1/chargers?${params}`, options.signal)
  const meta = result.meta
  if (!Number.isInteger(meta.total_available) || !Number.isInteger(meta.loaded) || !Number.isInteger(meta.total_pages)) {
    throw new Error('The FastAPI backend returned invalid pagination metadata.')
  }
  return {
    stations: result.data.map(normalizeCharger),
    meta: {
      page: meta.page,
      limit: meta.limit,
      loaded: meta.loaded,
      totalAvailable: meta.total_available,
      totalPages: meta.total_pages,
      source: meta.source,
      publisher: meta.publisher,
      sourceUrl: meta.source_url || undefined,
      snapshotDate: meta.snapshot_date,
      snapshotLabel: meta.snapshot_label,
      attribution: meta.attribution,
    },
  }
}

export async function loadStates(signal?: AbortSignal): Promise<StateOption[]> {
  const result = await getJson<{ success: boolean; data: StateOption[] }>('/api/v1/states', signal)
  return result.data.filter((state) => typeof state.name === 'string' && typeof state.code === 'string')
}

export async function loadDistricts(state: string, signal?: AbortSignal): Promise<{ districts: DistrictOption[]; totalCityRows: number }> {
  const params = new URLSearchParams({ state })
  const result = await getJson<{
    success: boolean
    data: DistrictOption[]
    meta: { city_count: number }
  }>(`/api/v1/districts?${params}`, signal)
  return { districts: result.data, totalCityRows: result.meta.city_count }
}

export async function analyzeGap(payload: GapAssessmentPayload, signal?: AbortSignal): Promise<GapAssessmentResponse> {
  return requestJson<GapAssessmentResponse>('/api/v1/analytics/gap-assessment', {
    method: 'POST',
    signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function loadAnalyticsSummary(options: {
  state?: string
  district?: string
  vehicleClass?: VehicleClass
  refresh?: boolean
  signal?: AbortSignal
}): Promise<AnalyticsSummary> {
  const params = new URLSearchParams({ page: '1', limit: '100' })
  if (options.state) params.set('state', options.state)
  if (options.district) params.set('district', options.district)
  if (options.vehicleClass) params.set('vehicle_class', options.vehicleClass)
  if (options.refresh) params.set('refresh', 'true')
  return getJson<AnalyticsSummary>(`/api/v1/analytics/summary?${params}`, options.signal)
}

export async function estimateRequirements(payload: RequirementsPayload, signal?: AbortSignal): Promise<RequirementsResponse> {
  return requestJson<RequirementsResponse>('/api/v1/requirements', {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
}

export async function optimizeBudget(payload: OptimizePayload, signal?: AbortSignal): Promise<OptimizeResponse> {
  return requestJson<OptimizeResponse>('/api/v1/optimize', {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
}

export async function loadTripCorridors(signal?: AbortSignal): Promise<TripCorridor[]> {
  const result = await getJson<{ success: boolean; data: TripCorridor[] }>('/api/v1/trip/corridors', signal)
  return result.data
}

export async function planTrip(payload: TripPlanPayload, signal?: AbortSignal): Promise<TripPlanResponse> {
  return requestJson<TripPlanResponse>('/api/v1/trip/plan', {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
}

export async function loadHexMetrics(state: string, district?: string, resolution = 7, signal?: AbortSignal): Promise<HexMetricsResponse> {
  const params = new URLSearchParams({ state, resolution: String(resolution) })
  if (district) params.set('district', district)
  return getJson<HexMetricsResponse>(`/api/v1/analytics/hex-metrics?${params}`, signal)
}

export async function loadClassComparison(state: string, signal?: AbortSignal): Promise<ClassComparisonResponse> {
  const params = new URLSearchParams({ state })
  return getJson<ClassComparisonResponse>(`/api/v1/analytics/class-comparison?${params}`, signal)
}

export async function loadEvRegistrations(options: {
  state?: string
  district?: string
  vehicleClass?: string
  signal?: AbortSignal
} = {}): Promise<EvRegistrationsResponse> {
  const params = new URLSearchParams()
  if (options.state) params.set('state', options.state)
  if (options.district) params.set('district', options.district)
  if (options.vehicleClass) params.set('vehicle_class', options.vehicleClass)
  return getJson<EvRegistrationsResponse>(`/api/v1/analytics/ev-registrations?${params}`, options.signal)
}

export async function loadCandidateSites(options: {
  state?: string
  includeDeadZones?: boolean
  signal?: AbortSignal
} = {}): Promise<{ success: boolean; data: CandidateSite[]; count: number }> {
  const params = new URLSearchParams()
  if (options.state) params.set('state', options.state)
  if (options.includeDeadZones !== undefined) params.set('include_corridor_dead_zones', String(options.includeDeadZones))
  return getJson<{ success: boolean; data: CandidateSite[]; count: number }>(`/api/v1/planning/candidate-sites?${params}`, options.signal)
}
