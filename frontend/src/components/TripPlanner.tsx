import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import { AlertTriangle, BatteryCharging, MapPin, Navigation, RotateCcw, Route } from 'lucide-react'
import { loadTripCorridors, planTrip } from '../services/chargerApi'
import type { TripCorridor, TripPlanPayload, TripPlanResponse, TripStation } from '../types/trip'

const defaults = { corridorId: '', vehicleClass: '4W' as TripPlanPayload['vehicle_class'], vehicleModel: '', capacity: '50', startSoc: '90', reserve: '15', consumption: '16', searchDistance: '35' }
const fmt = (value: number, digits = 1) => value.toLocaleString('en-IN', { maximumFractionDigits: digits })

export default function TripPlanner() {
  const [corridors, setCorridors] = useState<TripCorridor[]>([])
  const [form, setForm] = useState(defaults)
  const [result, setResult] = useState<TripPlanResponse | null>(null)
  const [loadingCorridors, setLoadingCorridors] = useState(true)
  const [planning, setPlanning] = useState(false)
  const [error, setError] = useState('')
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoadingCorridors(true)
    loadTripCorridors(controller.signal).then((items) => {
      setCorridors(items)
      setForm((previous) => ({ ...previous, corridorId: previous.corridorId || items[0]?.id || '' }))
      setError('')
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not load representative corridors.')
    }).finally(() => { if (!controller.signal.aborted) setLoadingCorridors(false) })
    return () => controller.abort()
  }, [retryKey])

  const corridor = useMemo(() => corridors.find((item) => item.id === form.corridorId), [corridors, form.corridorId])
  const trip = result?.data

  function change<K extends keyof typeof defaults>(key: K, value: (typeof defaults)[K]) {
    setForm((previous) => ({ ...previous, [key]: value }))
    setResult(null)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!corridor) return
    setError('')
    setPlanning(true)
    setResult(null)
    try {
      const payload: TripPlanPayload = {
        corridor_id: corridor.id,
        origin: corridor.origin,
        destination: corridor.destination,
        vehicle_class: form.vehicleClass,
        vehicle_model: form.vehicleModel.trim() || undefined,
        battery_capacity_kwh: Number(form.capacity),
        starting_soc_pct: Number(form.startSoc),
        reserve_pct: Number(form.reserve),
        consumption_kwh_per_100km: Number(form.consumption),
        station_search_distance_km: Number(form.searchDistance),
      }
      const planned = await planTrip(payload)
      setResult(planned)
      try { sessionStorage.setItem('ev-infra:last-trip-plan', JSON.stringify({ generatedAt: new Date().toISOString(), request: payload, response: planned })) } catch { /* The current trip remains usable even if browser storage is unavailable. */ }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The trip could not be planned.')
    } finally {
      setPlanning(false)
    }
  }

  function reset() {
    setForm({ ...defaults, corridorId: corridors[0]?.id || '' })
    setResult(null)
    setError('')
  }

  return <div className="trip-page">
    <div className="planning-intro">
      <div><span className="planning-kicker"><Route size={13} /> EV JOURNEY ENERGY ESTIMATE</span><h2>Plan a representative corridor trip</h2><p>Estimate route energy, reserve feasibility and directory stations near a sample corridor.</p></div>
      <span className="planning-status planning-status-illustrative"><Navigation size={13} /> Corridor simulation</span>
    </div>
    <div className="planning-notice"><AlertTriangle size={15} /><span>No live routing provider is configured. The route and distance are representative estimates; station locations come from a dated directory sample and do not show live operational or availability status.</span></div>
    {error && <div className="analytics-alert trip-error" role="alert"><span>{error}</span><button onClick={() => setRetryKey((value) => value + 1)}>Retry</button></div>}

    <div className="trip-layout">
      <form className="trip-form" onSubmit={submit}>
        <div className="planning-form-heading"><div><h3>Trip and vehicle inputs</h3><p>Vehicle consumption is an editable estimate.</p></div><button type="button" className="planning-reset" onClick={reset}><RotateCcw size={12} /> Reset</button></div>
        <label className="planning-field"><span>Representative corridor</span><select required value={form.corridorId} disabled={loadingCorridors || !corridors.length} onChange={(event) => change('corridorId', event.target.value)}>
          <option value="">{loadingCorridors ? 'Loading corridors...' : 'Choose a corridor'}</option>{corridors.map((item) => <option key={item.id} value={item.id}>{item.name} · ~{fmt(item.estimated_distance_km)} km</option>)}
        </select></label>
        <div className="trip-origin-destination">
          <label className="planning-field"><span>Origin</span><input readOnly value={corridor?.origin || ''} placeholder="Select a corridor" /></label>
          <label className="planning-field"><span>Destination</span><input readOnly value={corridor?.destination || ''} placeholder="Select a corridor" /></label>
        </div>
        <div className="planning-field-grid">
          <label className="planning-field"><span>Vehicle class</span><select value={form.vehicleClass} onChange={(event) => change('vehicleClass', event.target.value as TripPlanPayload['vehicle_class'])}><option value="2W">2W · two-wheelers</option><option value="3W">3W · three-wheelers</option><option value="4W">4W · cars / four-wheelers</option></select></label>
          <label className="planning-field"><span>Vehicle model <small>(optional)</small></span><input value={form.vehicleModel} maxLength={100} placeholder="Enter model or leave blank" onChange={(event) => change('vehicleModel', event.target.value)} /></label>
          <label className="planning-field"><span>Battery capacity (kWh)</span><input required type="number" min="0.1" max="500" step="0.1" value={form.capacity} onChange={(event) => change('capacity', event.target.value)} /></label>
          <label className="planning-field"><span>Energy use (kWh / 100 km)</span><input required type="number" min="0.1" max="200" step="0.1" value={form.consumption} onChange={(event) => change('consumption', event.target.value)} /></label>
          <label className="planning-field"><span>Starting battery SoC (%)</span><input required type="number" min="0" max="100" step="1" value={form.startSoc} onChange={(event) => change('startSoc', event.target.value)} /></label>
          <label className="planning-field"><span>Minimum arrival reserve (%)</span><input required type="number" min="0" max="100" step="1" value={form.reserve} onChange={(event) => change('reserve', event.target.value)} /><small>Must be lower than starting SoC</small></label>
          <label className="planning-field"><span>Station search distance (km)</span><input required type="number" min="1" max="200" step="1" value={form.searchDistance} onChange={(event) => change('searchDistance', event.target.value)} /><small>Straight-line distance from sample corridor</small></label>
        </div>
        <button className="planning-submit" type="submit" disabled={!corridor || loadingCorridors || planning}>{planning ? <><span className="planning-spinner" /> Analyzing corridor...</> : <><BatteryCharging size={15} /> Plan trip</>}</button>
        <p className="trip-form-note">Use your vehicle's observed consumption when available. The backend validates all energy and SoC values before planning.</p>
      </form>

      <section className="trip-results" aria-live="polite">
        {!trip && !planning && <div className="planning-empty"><Route size={25} /><h3>Choose a corridor and vehicle inputs</h3><p>Trip energy will be calculated from the selected corridor estimate. Charging stops use the existing station directory sample.</p></div>}
        {planning && <div className="planning-empty"><span className="planning-spinner" /><h3>Checking route energy and stations</h3><p>Loading a capped, cached station sample for the corridor states.</p></div>}
        {trip && result && <>
          <div className="trip-result-head"><div><span className="planning-kicker">REPRESENTATIVE CORRIDOR · NOT LIVE ROUTING</span><h3>{trip.origin} → {trip.destination}</h3><p>{fmt(trip.route_distance_km)} km estimated · {trip.vehicle_class}{trip.vehicle_model ? ` · ${trip.vehicle_model}` : ''}</p></div><span className={`trip-feasibility ${trip.feasible_with_recommended_stops ? 'trip-feasible' : 'trip-infeasible'}`}>{trip.feasible_with_recommended_stops ? 'Feasible on assumptions' : 'Not feasible on sample'}</span></div>

          {trip.warnings.length > 0 && <div className="trip-warning-list" role="status">{trip.warnings.map((warning) => <p key={warning}><AlertTriangle size={13} />{warning}</p>)}</div>}

          <div className="trip-kpis">
            <article><span>Estimated route distance</span><strong>{fmt(trip.route_distance_km)} km</strong><small>Representative corridor estimate</small></article>
            <article><span>Journey energy</span><strong>{fmt(trip.journey_energy_kwh, 2)} kWh</strong><small>Route distance × user consumption</small></article>
            <article><span>Starting energy</span><strong>{fmt(trip.available_battery_energy_kwh, 2)} kWh</strong><small>{fmt(trip.starting_soc_pct, 0)}% of {fmt(trip.battery_capacity_kwh)} kWh</small></article>
            <article><span>Arrival SoC estimate</span><strong>{trip.estimated_arrival_soc_after_plan_pct == null ? '—' : `${fmt(trip.estimated_arrival_soc_after_plan_pct)}%`}</strong><small>{trip.requires_charging ? 'After recommended stop plan' : 'Without charging stops'}</small></article>
          </div>

          {trip.candidate_dead_zone_sites && trip.candidate_dead_zone_sites.length > 0 && (
            <div style={{
              background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, padding: 16,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap',
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#b45309', fontWeight: 700, fontSize: '0.95rem' }}>
                  <AlertTriangle size={18} />
                  {trip.candidate_dead_zone_sites.length} Highway Dead Zones Identified on {corridor?.name}
                </div>
                <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#78350f' }}>
                  Unserved 50 km segments along the route have been interpolated into high-suitability candidate sites for charging equipment installation.
                </p>
              </div>
              <button
                type="button"
                style={{
                  padding: '9px 18px', background: '#d97706', color: '#ffffff', border: 'none',
                  borderRadius: 8, fontWeight: 600, fontSize: '0.85rem', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 6,
                }}
                onClick={() => {
                  sessionStorage.setItem('pending_dead_zones', JSON.stringify(trip.candidate_dead_zone_sites))
                  window.dispatchEvent(new CustomEvent('switch-to-budget-optimizer', { detail: { sites: trip.candidate_dead_zone_sites } }))
                }}
              >
                Transfer Dead Zones to Budget Optimizer →
              </button>
            </div>
          )}

          <div className="trip-map-card"><div className="planning-section-heading"><strong>Corridor and sampled charging stations</strong><span>{trip.near_route_stations.length} within search distance</span></div><TripMap trip={result} /><div className="trip-map-legend"><span><i className="trip-legend-route" /> Representative corridor</span><span><i className="trip-legend-station" /> Sampled station record</span><span><i className="trip-legend-stop" /> Recommended stop</span></div></div>

          <div className="trip-result-columns">
            <div className="trip-result-card">
              <div className="planning-section-heading"><strong>Charging stops</strong><span>{trip.charging_stops.length} recommended</span></div>
              {!trip.charging_stops.length && <p className="trip-muted">{trip.requires_charging ? 'No reachable station stop was found in the retrieved sample.' : 'The supplied starting charge can complete this corridor above the reserve; no stop is required.'}</p>}
              {trip.charging_stops.map((stop) => <article className="trip-stop" key={stop.id}><div className="trip-stop-number">{stop.stop_order}</div><div className="trip-stop-copy"><strong>{stop.name}</strong><span>{stop.district}, {stop.state} · {fmt(stop.route_progress_km)} km into corridor</span><small>Coordinates {stop.latitude.toFixed(5)}, {stop.longitude.toFixed(5)}</small><small>{stop.charger_type} · {stop.compatibility_status} for {trip.vehicle_class} · directory record, not live status</small><small>Est. arrival {fmt(stop.estimated_arrival_soc_pct)}% SoC · charge-to-full estimate {fmt(stop.estimated_recharge_to_full_kwh, 1)} kWh</small><small>{stop.source} · snapshot {stop.snapshot_date}</small></div></article>)}
            </div>
            <div className="trip-result-card">
              <div className="planning-section-heading"><strong>Sampled corridor coverage</strong><span>{trip.source_records_loaded} loaded / {trip.source_records_matching.toLocaleString('en-IN')} matching</span></div>
              <div className="trip-coverage-list">{trip.coverage_segments.map((segment) => <div className={segment.coverage_status === 'no_sampled_station_found' ? 'trip-coverage-gap' : 'trip-coverage-ok'} key={`${segment.start_km}-${segment.end_km}`}><span>{fmt(segment.start_km)}–{fmt(segment.end_km)} km</span><b>{segment.sampled_station_count ? `${segment.sampled_station_count} sampled` : 'No sample found'}</b></div>)}</div>
              <p className="trip-muted">A “no sample found” segment describes only the first 100 records per state, not proof that the area has no stations.</p>
            </div>
          </div>

          <div className="trip-result-card">
            <div className="planning-section-heading"><strong>Other stations near this corridor</strong><span>Up to {trip.near_route_stations.length} sampled directory records</span></div>
            {!trip.near_route_stations.length && <p className="trip-muted">No sampled station record falls within the configured search distance.</p>}
            <div className="trip-station-list">{trip.near_route_stations.map((station) => <TripStationRow key={station.id} station={station} vehicleClass={trip.vehicle_class} />)}</div>
          </div>

          <div className="trip-result-card trip-assumptions"><strong>Calculation, source and limitations</strong><p>{trip.formula}</p><p>Available battery = {fmt(trip.available_battery_energy_kwh, 2)} kWh; reserve = {fmt(trip.reserve_energy_kwh, 2)} kWh; energy above reserve before charging = {fmt(trip.usable_energy_before_charging_kwh, 2)} kWh. Estimated stop detour energy: {fmt(trip.estimated_detour_energy_kwh, 2)} kWh.</p><ul>{trip.assumptions.map((item) => <li key={item}>{item}</li>)}</ul><p><b>{result.meta.station_source}</b> · snapshot {result.meta.snapshot_date}. {result.meta.station_sample_scope}</p><ul>{result.meta.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
        </>}
      </section>
    </div>
  </div>
}

function TripStationRow({ station, vehicleClass }: { station: TripStation; vehicleClass: string }) {
  return <article className="trip-station-row"><div><MapPin size={13} /><strong>{station.name}</strong><span>{station.district}, {station.state}</span></div><div className="trip-station-meta"><span>{fmt(station.distance_from_route_km)} km from sample line</span><span>Coordinates {station.latitude.toFixed(5)}, {station.longitude.toFixed(5)}</span><span>{station.charger_type} · {station.compatibility_status} for {vehicleClass}</span><small>{station.total_chargers} chargers · {station.total_connectors} connectors · {station.source}, {station.snapshot_date}</small><small>Availability status is not supplied by this directory.</small></div></article>
}

function TripMap({ trip }: { trip: TripPlanResponse }) {
  const points = trip.data.route_geometry
  const center = points[Math.floor(points.length / 2)] ?? points[0]
  const boundsPoints: [number, number][] = [...points, ...trip.data.near_route_stations.map((station) => [station.latitude, station.longitude] as [number, number])]
  return <MapContainer className="trip-leaflet-map" center={center} zoom={7} scrollWheelZoom>
    <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
    <TripMapBounds points={boundsPoints} />
    <Polyline positions={points} pathOptions={{ color: '#078f85', weight: 5, opacity: 0.85, dashArray: '9 7' }} />
    {trip.data.near_route_stations.map((station) => {
      const stop = trip.data.charging_stops.some((item) => item.id === station.id)
      return <CircleMarker key={station.id} center={[station.latitude, station.longitude]} radius={stop ? 8 : 5} pathOptions={{ color: '#fff', weight: 2, fillColor: stop ? '#168452' : station.compatibility_status === 'Not listed' ? '#a8b3c0' : '#129f94', fillOpacity: 0.95 }}>
        <Popup><strong>{station.name}</strong><br />{station.district}, {station.state}<br />Coordinates {station.latitude.toFixed(5)}, {station.longitude.toFixed(5)}<br />{fmt(station.distance_from_route_km)} km from sample line<br />{station.source}, snapshot {station.snapshot_date}<br />Operational / live availability status not provided.</Popup>
      </CircleMarker>
    })}
  </MapContainer>
}

function TripMapBounds({ points }: { points: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (points.length > 1) map.fitBounds(points, { padding: [22, 22], maxZoom: 9 })
  }, [map, points])
  return null
}
