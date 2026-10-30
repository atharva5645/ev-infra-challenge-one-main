import { useEffect, useRef, useState } from 'react'
import { Activity, BatteryCharging, MapPin, RefreshCw, RadioTower } from 'lucide-react'
import { loadAnalyticsSummary } from '../services/chargerApi'
import type { AnalyticsDatum, AnalyticsSummary, VehicleClass } from '../types/station'

function BarChart({ data, emptyLabel = 'No records in this selection.' }: { data: AnalyticsDatum[]; emptyLabel?: string }) {
  const visible = [...data].sort((a, b) => b.value - a.value || a.name.localeCompare(b.name)).slice(0, 8)
  const max = Math.max(1, ...visible.map((item) => item.value))
  const rowHeight = 23
  const height = Math.max(48, visible.length * rowHeight + 8)
  if (!visible.length) return <div className="chart-empty">{emptyLabel}</div>
  return <svg className="bar-chart" viewBox={`0 0 480 ${height}`} role="img" aria-label="Horizontal bar chart">
    {visible.map((item, index) => {
      const y = index * rowHeight + 4
      const width = Math.max(2, (item.value / max) * 265)
      return <g key={item.name}>
        <title>{`${item.name}: ${item.value.toLocaleString('en-IN')}${typeof item.auxiliary_value === 'number' ? `; ${item.auxiliary_value.toLocaleString('en-IN')} guns` : ''}`}</title>
        <text x="0" y={y + 13} className="chart-label">{item.name.length > 20 ? `${item.name.slice(0, 19)}...` : item.name}</text>
        <rect x="145" y={y + 2} width="265" height="13" rx="6.5" className="bar-track" />
        <rect x="145" y={y + 2} width={width} height="13" rx="6.5" className="bar-fill" />
        <text x="420" y={y + 13} className="chart-value">{item.value.toLocaleString('en-IN')}</text>
      </g>
    })}
  </svg>
}

function GeographicPlot({ summary }: { summary: AnalyticsSummary }) {
  const points = summary.data.geographic_points
  if (!points.length) return <div className="chart-empty">No coordinates in this selection.</div>
  const left = 36, top = 12, width = 422, height = 150
  const x = (longitude: number) => left + ((longitude - 68) / 30) * width
  const y = (latitude: number) => top + ((38 - latitude) / 32) * height
  return <svg className="geo-plot" viewBox="0 0 480 190" role="img" aria-label="Loaded station coordinates by longitude and latitude">
    {[0, 1, 2, 3].map((step) => <g key={step}>
      <line x1={left} x2={left + width} y1={top + step * (height / 3)} y2={top + step * (height / 3)} className="geo-grid" />
      <text x="2" y={top + step * (height / 3) + 4} className="geo-axis">{Math.round(38 - step * (32 / 3))}N</text>
      <text x={left + step * (width / 3) - 9} y="181" className="geo-axis">{68 + step * 10}E</text>
    </g>)}
    {points.map((point) => <circle key={point.id} cx={x(point.longitude)} cy={y(point.latitude)} r="3.5" className="geo-point">
      <title>{`${point.name}, ${point.district}, ${point.state} (${point.latitude}, ${point.longitude})`}</title>
    </circle>)}
    <text x="192" y="189" className="geo-axis-title">Longitude</text>
  </svg>
}

const number = (value?: number) => typeof value === 'number' ? value.toLocaleString('en-IN') : '—'
const formatDateTime = (value?: string) => value ? new Date(value).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : 'Unavailable'

export default function DecisionDashboard() {
  const [state, setState] = useState('')
  const [district, setDistrict] = useState('')
  const [vehicleClass, setVehicleClass] = useState<VehicleClass | ''>('')
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const refreshPending = useRef(false)
  const [error, setError] = useState('')
  const [stale, setStale] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const shouldRefresh = refreshPending.current
    refreshPending.current = false
    setLoading(true)
    setError('')
    loadAnalyticsSummary({ state: state || undefined, district: district || undefined, vehicleClass: vehicleClass || undefined, refresh: shouldRefresh, signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return
        setSummary(result)
        setStale(false)
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        setError(reason instanceof Error ? reason.message : 'Could not load the analytics summary.')
        if (summary) setStale(true)
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      })
    return () => controller.abort()
  // summary is intentionally excluded: keeping the last good result during loading/failure avoids request loops.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, district, vehicleClass, reloadKey])

  const data = summary?.data
  const meta = summary?.meta
  const filters = meta?.active_filters
  const districtOptions = data?.district_distribution ?? []
  const activeFiltersMatch = (filters?.state ?? '') === state
    && (filters?.district ?? '') === district
    && (filters?.vehicle_class ?? '') === vehicleClass

  return <div className="analytics-page">
    <div className="analytics-topline">
      <div><strong>Directory snapshot</strong><span>{meta ? `${meta.source} · ${meta.snapshot_label}` : 'Loading source details...'}</span></div>
      <span className="analytics-status">BEE SNAPSHOT</span>
    </div>
    <div className="analytics-source-note">Source: BEE public charging-station dataset dated 26 October 2025, republished through a third-party API. This is a dated directory snapshot, not a live charger-availability feed.</div>
    {error && <div className={`analytics-alert ${stale ? 'analytics-alert-stale' : ''}`} role="alert">
      <span><strong>{stale ? 'Showing last successfully loaded data.' : 'Analytics API unavailable.'}</strong> {error}</span>
      <button onClick={() => setReloadKey((value) => value + 1)}>Retry</button>
    </div>}
    <div className="analytics-filters">
      <label><span>State / UT</span><select value={state} onChange={(event) => { setState(event.target.value); setDistrict('') }}><option value="">All India</option>{(data?.states ?? []).map((item) => <option key={item.code} value={item.name}>{item.name}</option>)}</select></label>
      <label><span>District</span><select value={district} disabled={!state} onChange={(event) => setDistrict(event.target.value)}><option value="">All districts</option>{districtOptions.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label>
      <label><span>Vehicle</span><select value={vehicleClass} onChange={(event) => setVehicleClass(event.target.value as VehicleClass | '')}><option value="">All classes</option><option value="2W">2W</option><option value="3W">3W</option><option value="4W">4W</option></select></label>
      <button className="analytics-reset" disabled={loading} onClick={() => { refreshPending.current = true; setReloadKey((value) => value + 1) }}><RefreshCw size={12} className={loading ? 'spin' : ''} /> Refresh data</button>
      <button className="analytics-reset" onClick={() => { setState(''); setDistrict(''); setVehicleClass('') }}>Reset filters</button>
      {loading && <span className="analytics-loading"><RefreshCw size={13} className="spin" /> Updating records</span>}
    </div>

    {!data && !loading && <div className="analytics-empty">No analytics data is available. Retry when the API is reachable.</div>}
    {data && meta && <>
      <div className="decision-kpis">
        <article><div className="decision-kpi-icon"><RadioTower size={17} /></div><span>Stations in source snapshot</span><strong>{number(data.metrics.total_dataset_stations)}</strong><small>Full dataset count · /v1/meta</small></article>
        <article><div className="decision-kpi-icon"><Activity size={17} /></div><span>Matching directory records</span><strong>{number(meta.total_matching_stations)}</strong><small>Upstream query total for active filters</small></article>
        <article><div className="decision-kpi-icon"><MapPin size={17} /></div><span>Records loaded</span><strong>{number(meta.records_loaded)}</strong><small>Page {meta.page} of {number(meta.total_pages)} · max {meta.limit}</small></article>
        <article><div className="decision-kpi-icon"><BatteryCharging size={17} /></div><span>Rows with power data</span><strong>{number(data.metrics.stations_with_power)}</strong><small>Of {number(meta.records_loaded)} loaded rows</small></article>
      </div>

      <div className="analytics-scope">The page contains <b>{number(meta.records_loaded)}</b> rows of <b>{number(meta.total_matching_stations)}</b> matching directory records. The snapshot metadata reports <b>{number(data.metrics.total_dataset_stations)}</b> stations across all records. Filtered station charts use only this page; national summary charts remain nationwide. {vehicleClass && (vehicleClass === '4W' ? 'Vehicle filter: 4W (upstream car class).' : `Vehicle filter: ${vehicleClass}; upstream combines 2W and 3W records.`)}</div>

      <div className="dashboard-chart-grid">
        <section className="dashboard-chart-card state-chart-card"><header><div><h2>State / UT distribution</h2><p>Full upstream state directory; nationwide and unfiltered</p></div><span className="chart-scope-tag">NATIONAL DIRECTORY</span></header><BarChart data={data.state_distribution} /></section>
        <section className="dashboard-chart-card"><header><div><h2>Connector types</h2><p>Station counts by connector type; nationwide</p></div><span className="chart-scope-tag">NATIONAL DIRECTORY</span></header><BarChart data={data.connector_distribution} /></section>
        <section className="dashboard-chart-card"><header><div><h2>Operators</h2><p>Station counts by operator; nationwide</p></div><span className="chart-scope-tag">NATIONAL DIRECTORY</span></header><BarChart data={data.operator_distribution} /></section>
        <section className="dashboard-chart-card"><header><div><h2>Charger types</h2><p>Current loaded valid-coordinate station page</p></div><span className="chart-scope-tag">{number(meta.records_loaded)} ROWS</span></header><BarChart data={data.charger_type_distribution} /></section>
        {state && <section className="dashboard-chart-card"><header><div><h2>District directory: {state}</h2><p>Counts aggregated from the full upstream city directory</p></div><span className="chart-scope-tag">STATE DIRECTORY</span></header><BarChart data={data.district_distribution} /></section>}
        <section className="dashboard-chart-card geo-chart-card"><header><div><h2>Geographic distribution</h2><p>Station coordinates in the current loaded page</p></div><span className="chart-scope-tag">PAGE SAMPLE</span></header><GeographicPlot summary={summary} /><div className="geo-footnote">Each dot is one retrieved station record. This page is not a complete national spatial sample.</div></section>
        <section className="dashboard-chart-card"><header><div><h2>Power distribution</h2><p>Maximum single-gun power per loaded station where supplied</p></div><span className="chart-scope-tag">PAGE SAMPLE</span></header><BarChart data={data.power_distribution} emptyLabel="Power values are unavailable for these records." /></section>
      </div>

      <div className="dashboard-limitations">
        <strong>Coverage and gap analysis are not available as verified national results.</strong>
        <span>No EV registrations, population, road-access, utilization, uptime or travel-demand datasets are integrated. A charger directory alone cannot validate infrastructure coverage or need. {meta.limitations.join(' ')}</span>
        <small>Source: {meta.publisher}. Snapshot {meta.snapshot_label}. Summary generated {formatDateTime(meta.generated_at)}; oldest included upstream response refreshed {formatDateTime(meta.upstream_refreshed_at)}. {meta.attribution}</small>
      </div>
      {!activeFiltersMatch && <div className="analytics-scope">The visible response belongs to the previous filter selection while updated data loads or after a request error.</div>}
      {stale && <div className="analytics-scope">Displayed values are retained from the last successful request and may not match the active filters.</div>}
    </>}
  </div>
}
