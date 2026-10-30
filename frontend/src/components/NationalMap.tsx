import { useEffect, useMemo, useState } from 'react'
import { Circle, MapContainer, Marker, Polygon, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import { ChevronLeft, ChevronRight, LocateFixed, RotateCcw, Search, SlidersHorizontal } from 'lucide-react'
import { demoStations } from '../data/demoStations'
import { loadChargers, loadHexMetrics, loadStates } from '../services/chargerApi'
import type { ChargerPageMeta, HexCell, MapStation, StateOption, VehicleClass } from '../types/station'

const indiaCenter: [number, number] = [22.7, 79.1]
const stateCenters: Record<string, [number, number]> = {
  'Andaman and Nicobar Islands': [11.7, 92.7], 'Andhra Pradesh': [15.9, 79.7], 'Arunachal Pradesh': [28.2, 94.7], Assam: [26.2, 92.9], Bihar: [25.9, 85.4], Chandigarh: [30.7, 76.8], Chhattisgarh: [21.3, 82.0],
  'Dadra and Nagar Haveli and Daman and Diu': [20.2, 72.9], Delhi: [28.6, 77.2], Goa: [15.3, 74.0], Gujarat: [22.3, 71.8], Haryana: [29.0, 76.0], 'Himachal Pradesh': [31.8, 77.2], Jharkhand: [23.6, 85.5], Karnataka: [15.0, 76.2], Kerala: [10.4, 76.3], Ladakh: [34.2, 77.6], Lakshadweep: [10.0, 72.6], 'Madhya Pradesh': [23.5, 78.5], Maharashtra: [19.3, 75.7], Manipur: [24.7, 93.9], Meghalaya: [25.5, 91.3], Mizoram: [23.2, 92.8], Nagaland: [26.1, 94.5], Odisha: [20.5, 84.4], Puducherry: [11.9, 79.8], Punjab: [31.0, 75.4], Rajasthan: [26.8, 73.8], Sikkim: [27.5, 88.5], 'Tamil Nadu': [11.1, 78.4], Telangana: [17.9, 79.0], Tripura: [23.8, 91.3], 'Uttar Pradesh': [27.0, 80.8], Uttarakhand: [30.1, 79.2], 'West Bengal': [23.0, 87.7], 'Jammu and Kashmir': [33.8, 76.5],
}

const gapZones = [
  { center: [21.1458, 79.0882] as [number, number], radius: 31000, name: 'Nagpur illustrative gap zone', note: 'Example planning overlay only; not a computed national gap score.' },
  { center: [12.2958, 76.6394] as [number, number], radius: 24000, name: 'Mysuru illustrative gap zone', note: 'Example planning overlay only; not a computed national gap score.' },
  { center: [22.5726, 88.3639] as [number, number], radius: 28000, name: 'Kolkata illustrative gap zone', note: 'Example planning overlay only; not a computed national gap score.' },
]

function confidenceColor(value?: number) {
  if (value === undefined) return '#8b99ad'
  if (value >= 0.8) return '#12835d'
  if (value >= 0.65) return '#d09125'
  return '#cc5b5b'
}

function stationIcon(station: MapStation, confidenceLayer: boolean) {
  const color = confidenceLayer ? confidenceColor(station.confidence) : station.isDemo ? '#bf8127' : '#079b91'
  return L.divIcon({
    className: 'station-marker-wrap',
    html: `<span class="station-marker" style="--marker-color:${color}"><span></span></span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  })
}

function clusterIcon(count: number, demoOnly: boolean) {
  const color = demoOnly ? '#bf8127' : '#087f78'
  return L.divIcon({
    className: 'station-cluster-wrap',
    html: `<span class="station-cluster" style="--cluster-color:${color}">${count}</span>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  })
}

function MapViewController({ state }: { state: string }) {
  const map = useMap()
  useEffect(() => {
    if (state && stateCenters[state]) map.flyTo(stateCenters[state], state === 'Delhi' || state === 'Chandigarh' || state === 'Puducherry' ? 8 : 6, { duration: 0.7 })
    else map.flyTo(indiaCenter, 4, { duration: 0.7 })
  }, [map, state])
  useEffect(() => {
    const timer = window.setTimeout(() => map.invalidateSize(), 100)
    return () => window.clearTimeout(timer)
  }, [map])
  return null
}

function StationDetails({ station }: { station: MapStation }) {
  const classes = station.supportedVehicleClasses
  return <div className="station-popup">
    {station.isDemo && <div className="popup-demo">ILLUSTRATIVE DEMO FALLBACK</div>}
    <strong>{station.name}</strong>
    <span>{station.district}, {station.state}</span>
    <dl>
      {station.operator && <div><dt>Operator</dt><dd>{station.operator}</dd></div>}
      <div><dt>Charger type</dt><dd>{station.chargerType}</dd></div>
      {station.powerKw !== undefined && <div><dt>Maximum gun power</dt><dd>{station.powerKw} kW</dd></div>}
      <div><dt>Vehicle compatibility</dt><dd>{classes?.length ? classes.join(', ') : 'Not specified by source'}</dd></div>
      {station.totalChargers !== undefined && <div><dt>Chargers / connectors</dt><dd>{station.totalChargers} / {station.totalConnectors ?? 'N/A'}</dd></div>}
      {station.address && <div className="popup-address"><dt>Address</dt><dd>{station.address}</dd></div>}
      {station.snapshotDate && <div><dt>Snapshot date</dt><dd>{station.snapshotDate}</dd></div>}
      <div><dt>Station ID</dt><dd>{station.id}</dd></div>
      <div><dt>Source</dt><dd>{station.source}</dd></div>
    </dl>
    <small>{station.isDemo ? 'Synthetic example; not a verified station listing.' : 'Directory snapshot only; this does not show real-time availability.'}</small>
  </div>
}

function stationGroups(stations: MapStation[], map: L.Map, zoom: number) {
  const buckets = new Map<string, MapStation[]>()
  for (const station of stations) {
    const point = map.project([station.latitude, station.longitude], zoom)
    const key = `${Math.floor(point.x / 48)}:${Math.floor(point.y / 48)}`
    const bucket = buckets.get(key) ?? []
    bucket.push(station)
    buckets.set(key, bucket)
  }
  return [...buckets.values()]
}

function ClusteredStationMarkers({ stations, confidenceLayer }: { stations: MapStation[]; confidenceLayer: boolean }) {
  const map = useMap()
  const [zoom, setZoom] = useState(map.getZoom())
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) })
  const groups = useMemo(() => stationGroups(stations, map, zoom), [stations, map, zoom])

  return <>{groups.map((group) => {
    if (group.length === 1) {
      const station = group[0]
      return <Marker key={station.id} position={[station.latitude, station.longitude]} icon={stationIcon(station, confidenceLayer)}>
        <Popup><StationDetails station={station} /></Popup>
      </Marker>
    }
    const center: [number, number] = [group.reduce((sum, item) => sum + item.latitude, 0) / group.length, group.reduce((sum, item) => sum + item.longitude, 0) / group.length]
    const demoOnly = group.every((item) => item.isDemo)
    const bounds = L.latLngBounds(group.map((item) => [item.latitude, item.longitude] as [number, number]))
    return <Marker key={`${group[0].id}-cluster-${zoom}`} position={center} icon={clusterIcon(group.length, demoOnly)}
      eventHandlers={{ click: () => { if (zoom < 17) map.fitBounds(bounds.pad(0.3), { maxZoom: Math.min(17, zoom + 4) }) } }}>
      <Popup><div className="cluster-popup"><strong>{group.length} stations in this map cluster</strong><span>Zoom in to separate nearby locations.</span>
        <ul>{group.slice(0, 8).map((item) => <li key={item.id}>{item.operator || item.name} - {item.city || item.district}</li>)}</ul>
        {group.length > 8 && <small>and {group.length - 8} more in this cluster</small>}
      </div></Popup>
    </Marker>
  })}</>
}

export default function NationalMap() {
  const [state, setState] = useState('')
  const [vehicleClass, setVehicleClass] = useState<VehicleClass | ''>('')
  const [query, setQuery] = useState('')
  const [stationsOn, setStationsOn] = useState(true)
  const [gapsOn, setGapsOn] = useState(true)
  const [confidenceOn, setConfidenceOn] = useState(false)
  const [hexOn, setHexOn] = useState(false)
  const [hexCells, setHexCells] = useState<HexCell[]>([])
  const [hexLoading, setHexLoading] = useState(false)
  const [tilesUnavailable, setTilesUnavailable] = useState(false)
  const [records, setRecords] = useState<MapStation[]>([])
  const [meta, setMeta] = useState<ChargerPageMeta | null>(null)
  const [stateOptions, setStateOptions] = useState<StateOption[]>([])
  const [mode, setMode] = useState<'loading' | 'api' | 'fallback'>('loading')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryVersion, setRetryVersion] = useState(0)
  const [page, setPage] = useState(1)

  useEffect(() => {
    const controller = new AbortController()
    loadStates(controller.signal).then(setStateOptions).catch(() => {
      if (!controller.signal.aborted) setStateOptions([])
    })
    return () => controller.abort()
  }, [retryVersion])

  useEffect(() => {
    if (!hexOn) return
    const controller = new AbortController()
    setHexLoading(true)
    loadHexMetrics(state || 'Karnataka', undefined, 7, controller.signal)
      .then((res) => {
        if (!controller.signal.aborted) setHexCells(res.data.cells)
      })
      .catch(() => {
        if (!controller.signal.aborted) setHexCells([])
      })
      .finally(() => {
        if (!controller.signal.aborted) setHexLoading(false)
      })
    return () => controller.abort()
  }, [hexOn, state])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    loadChargers({ state: state || undefined, page, limit: 100, signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return
        setRecords(result.stations)
        setMeta(result.meta)
        setMode('api')
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        setError(reason instanceof Error ? reason.message : 'Could not load the charger directory.')
        setMeta(null)
        setRecords(demoStations)
        setMode('fallback')
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [state, page, retryVersion])

  const activeStations = mode === 'fallback' ? demoStations : records
  const filteredStations = useMemo(() => activeStations.filter((station) => {
    const matchesState = !state || station.state === state
    const matchesClass = !vehicleClass || station.supportedVehicleClasses?.includes(vehicleClass)
    const needle = query.trim().toLowerCase()
    const matchesSearch = !needle || `${station.name} ${station.operator || ''} ${station.district} ${station.state} ${station.id}`.toLowerCase().includes(needle)
    return matchesState && matchesClass && matchesSearch
  }), [activeStations, state, vehicleClass, query])
  const loadedCount = mode === 'api' ? records.length : activeStations.length
  const knownConfidence = filteredStations.filter((station) => station.confidence !== undefined).length
  const hasHighConfidence = filteredStations.some((station) => station.confidence !== undefined && station.confidence >= 0.8)
  const hasMediumConfidence = filteredStations.some((station) => station.confidence !== undefined && station.confidence >= 0.65 && station.confidence < 0.8)
  const hasLowConfidence = filteredStations.some((station) => station.confidence !== undefined && station.confidence < 0.65)
  const hasMissingConfidence = filteredStations.some((station) => station.confidence === undefined)
  const states = stateOptions.length ? stateOptions : [...new Set(activeStations.map((station) => station.state))].sort().map((name) => ({ name, code: name, stations: 0 }))

  function resetFilters() {
    setState('')
    setVehicleClass('')
    setQuery('')
    setPage(1)
  }

  function chooseState(value: string) {
    setState(value)
    setPage(1)
  }

  function retryApi() {
    setRetryVersion((value) => value + 1)
  }

  const pageCount = mode === 'api' ? (meta?.totalPages ?? 0) : 1
  const pageLoadingLabel = mode === 'loading' ? 'Loading the BEE station directory...' : ''
  const showEmpty = !loading && filteredStations.length === 0

  return <div className="map-dashboard">
    <div className="map-stats">
      <div className="map-stat"><span>Visible on this page</span><strong>{filteredStations.length}</strong></div>
      <div className="map-stat"><span>Records loaded</span><strong>{loadedCount}</strong></div>
      <div className="map-stat"><span>{mode === 'api' ? 'API query total' : 'Fallback demo records'}</span><strong>{mode === 'api' ? meta?.totalAvailable.toLocaleString('en-IN') ?? 'N/A' : demoStations.length}</strong></div>
      <span className={`data-notice ${mode === 'fallback' ? 'fallback-notice' : ''}`}>{mode === 'api' ? 'BEE snapshot - 26 Oct 2025' : mode === 'loading' ? 'Connecting to API' : 'Illustrative fallback'}</span>
    </div>

    <div className="map-toolbar">
      <label className="map-search"><Search size={15} /><input aria-label="Search loaded stations" placeholder="Search loaded page" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      <label className="map-select"><span>State</span><select value={state} onChange={(event) => chooseState(event.target.value)}><option value="">All India</option>{states.map((item) => <option value={item.name} key={item.code}>{item.name}</option>)}</select></label>
      <label className="map-select"><span>Vehicle</span><select value={vehicleClass} onChange={(event) => setVehicleClass(event.target.value as VehicleClass | '')}><option value="">All classes</option><option value="2W">2W</option><option value="3W">3W</option><option value="4W">4W</option></select></label>
      <button className="reset-map-filters" onClick={resetFilters} title="Reset search and filters"><RotateCcw size={14} /><span>Reset</span></button>
      {mode === 'api' && pageCount > 1 && <div className="map-pagination" aria-label="Station directory pages">
        <button disabled={loading || page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} aria-label="Previous page"><ChevronLeft size={14} /></button>
        <span>{meta?.page ?? page}/{pageCount}</span>
        <button disabled={loading || page >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))} aria-label="Next page"><ChevronRight size={14} /></button>
      </div>}
    </div>

    {mode === 'fallback' && <div className="api-fallback-banner" role="status"><span><strong>API unavailable.</strong> Showing {demoStations.length} illustrative demo stations instead of official directory records. {error}</span><button onClick={retryApi}>Retry API</button></div>}

    <div className="map-frame">
      <MapContainer center={indiaCenter} zoom={4} minZoom={3} maxZoom={18} maxBounds={[[4, 65], [38, 100]]} maxBoundsViscosity={0.7} scrollWheelZoom className="india-map">
        <MapViewController state={state} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          eventHandlers={{ tileerror: () => setTilesUnavailable(true), tileload: () => setTilesUnavailable(false) }}
        />
        {gapsOn && gapZones.map((zone) => <Circle key={zone.name} center={zone.center} radius={zone.radius} pathOptions={{ color: '#d39137', fillColor: '#e5b765', fillOpacity: 0.2, weight: 1.5, dashArray: '5 5' }}>
          <Popup><div className="gap-popup"><strong>{zone.name}</strong><span>{zone.note}</span></div></Popup>
        </Circle>)}
        {hexOn && hexCells.map((cell) => {
          const fillColor = cell.priority === 'High Gap' ? '#dc2626' : cell.priority === 'Medium Gap' ? '#d97706' : '#059669'
          return (
            <Polygon
              key={cell.cell_id}
              positions={cell.boundary}
              pathOptions={{ color: fillColor, fillColor, fillOpacity: 0.35, weight: 1.5 }}
            >
              <Popup>
                <div className="gap-popup">
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <strong>⬡ H3 Hex (Res {cell.resolution})</strong>
                    <span style={{ fontSize: '0.75rem', padding: '2px 6px', borderRadius: 4, background: fillColor, color: '#fff', fontWeight: 600 }}>{cell.priority}</span>
                  </div>
                  <div style={{ fontSize: '0.85rem', marginBottom: 2 }}><strong>Gap Score:</strong> {(cell.gap_score * 100).toFixed(1)} / 100</div>
                  <div style={{ fontSize: '0.85rem', marginBottom: 2 }}><strong>Stations:</strong> {cell.charger_count} ({cell.fast_charger_count} DC fast)</div>
                  <div style={{ fontSize: '0.85rem', marginBottom: 2 }}><strong>Nearest Station:</strong> {cell.distance_to_nearest_charger_km} km</div>
                  <div style={{ fontSize: '0.85rem', marginBottom: 4 }}><strong>EV Demand Proxy:</strong> {cell.ev_demand_proxy.toLocaleString('en-IN')}</div>
                  <small style={{ color: '#64748b', fontSize: '0.7rem' }}>Cell: {cell.cell_id}</small>
                </div>
              </Popup>
            </Polygon>
          )
        })}
        {stationsOn && <ClusteredStationMarkers stations={filteredStations} confidenceLayer={confidenceOn} />}
      </MapContainer>

      <div className="map-layer-card">
        <div className="layer-heading"><SlidersHorizontal size={14} /><strong>Map layers</strong></div>
        <label><input type="checkbox" checked={stationsOn} onChange={(event) => setStationsOn(event.target.checked)} /><span className="layer-dot station-dot" />Charging stations</label>
        <label><input type="checkbox" checked={gapsOn} onChange={(event) => setGapsOn(event.target.checked)} /><span className="layer-dot gap-dot" />Illustrative gap zones</label>
        <label><input type="checkbox" checked={hexOn} onChange={(event) => setHexOn(event.target.checked)} /><span className="layer-dot" style={{ background: '#8b5cf6' }} />H3 Hex Spatial Layer (Res 7)</label>
        {hexOn && (
          <div className="confidence-legend">
            <span><i style={{ background: '#dc2626' }} />High Gap</span>
            <span><i style={{ background: '#d97706' }} />Medium</span>
            <span><i style={{ background: '#059669' }} />Adequate</span>
            {hexLoading && <small style={{ color: '#6366f1' }}>Computing H3 cells…</small>}
          </div>
        )}
        <label><input type="checkbox" checked={confidenceOn} onChange={(event) => setConfidenceOn(event.target.checked)} /><span className="layer-dot confidence-dot" />Charger confidence</label>
        {confidenceOn && (knownConfidence > 0 ? <div className="confidence-legend">
          {hasHighConfidence && <span><i className="high" />High</span>}
          {hasMediumConfidence && <span><i className="medium" />Medium</span>}
          {hasLowConfidence && <span><i className="low" />Low</span>}
          {hasMissingConfidence && <span><i className="unknown" />No data</span>}
          <small>Illustrative demo scores only</small>
        </div> : <div className="confidence-unavailable">No confidence scores are provided in the BEE snapshot.</div>)}
      </div>

      <button className="india-reset" onClick={() => resetFilters()} title="Return to India view"><LocateFixed size={15} /><span>India</span></button>
      {(stationsOn || gapsOn) && <div className="map-legend">
        {stationsOn && <span><i className={`legend-station ${mode === 'fallback' ? 'legend-demo' : ''}`} />{mode === 'fallback' ? 'Demo station' : 'BEE station'}</span>}
        {gapsOn && <span><i className="legend-gap" />Illustrative zone</span>}
      </div>}
      <div className="map-results">{filteredStations.length} visible on this page</div>
      {tilesUnavailable && <div className="tile-warning" role="status">Map tiles are unreachable. Station markers and overlays remain available.</div>}
      {(loading || pageLoadingLabel) && <div className="map-loading" role="status">{pageLoadingLabel}</div>}
      {showEmpty && <div className="map-empty" role="status">No stations match these filters on the loaded page.</div>}
    </div>

    <div className="map-data-footer">
      <div className="map-attribution">{mode === 'api' && meta
        ? <><strong>{meta.source}</strong> - {meta.publisher} - Snapshot {meta.snapshotLabel}. {meta.attribution}
          <span>Loaded {meta.loaded} records on page {meta.page} of {meta.totalPages}; the API query total is {meta.totalAvailable.toLocaleString('en-IN')} records. Local search and vehicle filters apply only to this loaded page, which is not the complete directory. This is a dated station directory, not real-time availability.</span></>
        : <><strong>Illustrative fallback dataset</strong> - {demoStations.length} synthetic station examples; not verified listings and not official statistics. {mode === 'fallback' ? 'Live API connection is unavailable.' : 'Connecting to backend...'}</>}
      </div>
      {mode === 'fallback' && <span className="fallback-tag">DEMO FALLBACK</span>}
    </div>
  </div>
}
