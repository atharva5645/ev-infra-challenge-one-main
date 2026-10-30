import { useEffect, useState, type FormEvent } from 'react'
import { AlertTriangle, Calculator, RotateCcw, Zap, Sparkles } from 'lucide-react'
import { estimateRequirements, loadEvRegistrations, loadStates } from '../services/chargerApi'
import type { RequirementsResponse } from '../types/planning'
import type { StateOption, VehicleClass } from '../types/station'

const initial = {
  state: '', vehicleClass: '4W' as VehicleClass, currentEv: '', projectedEv: '', horizon: '2030',
  ratio: '1000', coverage: '100', acShare: '70', acCost: '1500000', dcCost: '3500000',
}
const inr = (value: number) => `₹${value.toLocaleString('en-IN')}`

export default function ChargerPlanner() {
  const [states, setStates] = useState<StateOption[]>([])
  const [values, setValues] = useState(initial)
  const [result, setResult] = useState<RequirementsResponse | null>(null)
  const [loadingStates, setLoadingStates] = useState(true)
  const [loadingVahan, setLoadingVahan] = useState(false)
  const [vahanBaselineInfo, setVahanBaselineInfo] = useState<string | null>(null)
  const [calculating, setCalculating] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoadingStates(true)
    loadStates(controller.signal).then((items) => { setStates(items); setError('') }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not load states from the station directory.')
    }).finally(() => { if (!controller.signal.aborted) setLoadingStates(false) })
    return () => controller.abort()
  }, [retry])

  function change(key: keyof typeof initial, value: string) {
    setValues((previous) => ({ ...previous, [key]: value }))
    setResult(null)
  }

  async function fetchVahanBaseline() {
    if (!values.state) return
    setLoadingVahan(true)
    try {
      const res = await loadEvRegistrations({ state: values.state, vehicleClass: values.vehicleClass })
      if (res && res.summary) {
        let current = res.summary.total_evs
        if (values.vehicleClass === '2W' && res.summary.two_wheeler_count) {
          current = res.summary.two_wheeler_count
        } else if (values.vehicleClass === '3W' && res.summary.three_wheeler_count) {
          current = res.summary.three_wheeler_count
        } else if (values.vehicleClass === '4W' && res.summary.four_wheeler_count) {
          current = res.summary.four_wheeler_count
        }
        const multiplier = values.vehicleClass === '2W' ? 2.8 : values.vehicleClass === '3W' ? 2.4 : 2.2
        const projected = Math.round(current * multiplier)
        setValues((prev) => ({
          ...prev,
          currentEv: String(current),
          projectedEv: prev.projectedEv && prev.projectedEv !== '0' ? prev.projectedEv : String(projected),
        }))
        setVahanBaselineInfo(
          `MoRTH VAHAN-calibrated baseline: ${current.toLocaleString('en-IN')} ${values.vehicleClass} EVs in ${values.state} (projected ${projected.toLocaleString('en-IN')} by ${values.horizon}).`
        )
      }
    } catch {
      // fallback
    } finally {
      setLoadingVahan(false)
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setCalculating(true)
    setResult(null)
    try {
      setResult(await estimateRequirements({
        state: values.state,
        vehicle_class: values.vehicleClass,
        current_ev_population: Number(values.currentEv),
        projected_ev_population: Number(values.projectedEv),
        planning_horizon_year: Number(values.horizon),
        target_ev_per_station: Number(values.ratio),
        target_coverage_pct: Number(values.coverage),
        ac_allocation_pct: Number(values.acShare),
        ac_cost_per_station_inr: Number(values.acCost),
        dc_cost_per_station_inr: Number(values.dcCost),
      }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The requirement estimate could not be calculated.')
    } finally {
      setCalculating(false)
    }
  }

  const selectedState = states.find((item) => item.name === values.state)
  const estimate = result?.data
  const acShare = estimate?.additional_stations ? estimate.additional_ac_stations / estimate.additional_stations * 100 : 0

  return <div className="planning-page">
    <div className="planning-intro">
      <div><span className="planning-kicker"><Calculator size={13} /> TRANSPARENT PLANNING ESTIMATE</span><h2>Estimate charging-station requirements</h2><p>Enter the EV population assumptions and a station planning ratio to calculate future station needs and budget.</p></div>
      <span className="planning-status"><Zap size={13} /> Station-level estimate</span>
    </div>
    <div className="planning-notice"><AlertTriangle size={15} /><span>EV counts and installation costs are planning inputs, not official registration figures or procurement quotes. The upstream directory reports <b>stations</b>; a station is not the same as a charger unit or connector.</span></div>
    {error && <div className="analytics-alert planning-error" role="alert"><span>{error}</span><button onClick={() => setRetry((value) => value + 1)}>Retry state directory</button></div>}

    <div className="planning-layout">
      <form className="planning-form" onSubmit={submit}>
        <div className="planning-form-heading"><div><h3>Planning inputs</h3><p>All values are sent to the requirements service.</p></div><button type="button" className="planning-reset" onClick={() => { setValues(initial); setResult(null); setError(''); setVahanBaselineInfo(null) }}><RotateCcw size={12} /> Reset</button></div>

        {vahanBaselineInfo && (
          <div style={{ background: '#f0fdf4', border: '1px solid #86efac', color: '#166534', padding: '0.6rem 0.85rem', borderRadius: 6, fontSize: '0.82rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Sparkles size={16} style={{ color: '#16a34a', flexShrink: 0 }} />
            <span>{vahanBaselineInfo}</span>
          </div>
        )}

        <div className="planning-field-grid">
          <label className="planning-field"><span>State / UT</span><select required value={values.state} disabled={loadingStates || !states.length} onChange={(event) => { change('state', event.target.value); setVahanBaselineInfo(null) }}>
            <option value="">{loadingStates ? 'Loading states...' : 'Choose a state / UT'}</option>{states.map((item) => <option key={item.code} value={item.name}>{item.name}</option>)}
          </select></label>
          <label className="planning-field"><span>Vehicle class</span><select value={values.vehicleClass} onChange={(event) => { change('vehicleClass', event.target.value); setVahanBaselineInfo(null) }}><option value="2W">2W · two-wheelers</option><option value="3W">3W · three-wheelers</option><option value="4W">4W · cars / four-wheelers</option></select></label>
          <label className="planning-field">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Current EV population</span>
              {values.state && (
                <button
                  type="button"
                  onClick={fetchVahanBaseline}
                  disabled={loadingVahan}
                  style={{
                    background: '#e0e7ff',
                    border: '1px solid #c7d2fe',
                    color: '#3730a3',
                    borderRadius: 4,
                    padding: '2px 8px',
                    fontSize: '0.73rem',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                  title="Auto-fill baseline from VAHAN registration proxy"
                >
                  {loadingVahan ? 'Loading...' : '⚡ Use VAHAN EV Proxy'}
                </button>
              )}
            </div>
            <input required type="number" min="0" max="1000000000" step="1" value={values.currentEv} placeholder="Enter current count" onChange={(event) => change('currentEv', event.target.value)} />
            <small>Populated from VAHAN proxy or custom input</small>
          </label>
          <label className="planning-field"><span>Expected EV population</span><input required type="number" min="0" max="1000000000" step="1" value={values.projectedEv} placeholder="Enter horizon count" onChange={(event) => change('projectedEv', event.target.value)} /><small>At the selected planning horizon</small></label>
          <label className="planning-field"><span>Planning horizon year</span><input required type="number" min="2026" max="2100" step="1" value={values.horizon} onChange={(event) => change('horizon', event.target.value)} /></label>
          <label className="planning-field"><span>Target EVs per station</span><input required type="number" min="1" max="10000000" step="1" value={values.ratio} onChange={(event) => change('ratio', event.target.value)} /><small>Editable planning ratio, not an official standard</small></label>
          <label className="planning-field"><span>Target population coverage (%)</span><input required type="number" min="0.01" max="100" step="0.1" value={values.coverage} onChange={(event) => change('coverage', event.target.value)} /><small>Applied to projected population before sizing stations</small></label>
          <label className="planning-field"><span>Existing stations · selected state</span><input readOnly value={selectedState ? `${selectedState.stations.toLocaleString('en-IN')} station rows` : loadingStates ? 'Loading...' : 'Select a state'} /><small>All vehicle classes; directory snapshot count</small></label>
        </div>

        <div className="planning-section-heading"><strong>Deployment mix and estimated costs</strong><span>Editable estimates · INR per station</span></div>
        <label className="planning-field planning-range-field"><span>AC allocation <b>{values.acShare}%</b><small>DC allocation {100 - (Number(values.acShare) || 0)}%</small></span><input type="range" min="0" max="100" step="5" value={values.acShare} onChange={(event) => change('acShare', event.target.value)} /></label>
        <div className="planning-field-grid planning-cost-grid">
          <label className="planning-field"><span>Estimated AC cost / station (₹)</span><input required type="number" min="0" max="10000000000" step="10000" value={values.acCost} onChange={(event) => change('acCost', event.target.value)} /></label>
          <label className="planning-field"><span>Estimated DC cost / station (₹)</span><input required type="number" min="0" max="10000000000" step="10000" value={values.dcCost} onChange={(event) => change('dcCost', event.target.value)} /></label>
        </div>
        <button className="planning-submit" type="submit" disabled={!values.state || loadingStates || calculating}>{calculating ? <><span className="planning-spinner" /> Calculating requirements...</> : <><Calculator size={15} /> Calculate requirements</>}</button>
      </form>

      <section className="planning-results" aria-live="polite">
        {!estimate && !calculating && <div className="planning-empty"><Calculator size={25} /><h3>Set assumptions to begin</h3><p>The backend will retrieve the selected state's station count and calculate the additional station requirement from your inputs.</p></div>}
        {calculating && <div className="planning-empty"><span className="planning-spinner" /><h3>Calculating estimate</h3><p>Reading the cached state station directory and applying your planning assumptions.</p></div>}
        {estimate && result && <>
          <div className="planning-result-head"><div><span className="planning-kicker">RECOMMENDED INFRASTRUCTURE</span><h3>{estimate.state} · {estimate.vehicle_class}</h3><p>Planning horizon {estimate.planning_horizon_year} · source snapshot {result.meta.snapshot_date}</p></div><span className={`planning-priority priority-${estimate.priority.toLowerCase()}`}>{estimate.priority}</span></div>
          <div className="planning-result-kpis">
            <article><span>Existing stations</span><strong>{estimate.existing_stations.toLocaleString('en-IN')}</strong><small>Station rows · all vehicle classes</small></article>
            <article><span>Required stations</span><strong>{estimate.required_stations.toLocaleString('en-IN')}</strong><small>To meet selected target</small></article>
            <article><span>Additional stations</span><strong>{estimate.additional_stations.toLocaleString('en-IN')}</strong><small>Planning requirement</small></article>
            <article><span>Estimated investment</span><strong>{inr(estimate.estimated_total_investment_inr)}</strong><small>Editable unit-cost assumptions</small></article>
          </div>
          <div className="planning-result-card">
            <div className="planning-section-heading"><strong>AC / DC station allocation</strong><span>{estimate.additional_stations.toLocaleString('en-IN')} additional stations</span></div>
            <div className="planning-allocation-bar"><i style={{ width: `${acShare}%` }} /></div>
            <div className="planning-allocation-legend"><span><i className="allocation-ac" /> AC <b>{estimate.additional_ac_stations}</b> · {inr(estimate.estimated_ac_investment_inr)}</span><span><i className="allocation-dc" /> DC <b>{estimate.additional_dc_stations}</b> · {inr(estimate.estimated_dc_investment_inr)}</span></div>
          </div>
          <div className="planning-result-card planning-formula">
            <strong>Calculation</strong>
            <p>{estimate.formula}</p>
            <p><b>{estimate.covered_projected_ev_population.toLocaleString('en-IN')}</b> target-covered EVs ÷ <b>{estimate.target_ev_per_station.toLocaleString('en-IN')}</b> EVs/station = <b>{estimate.required_stations.toLocaleString('en-IN')}</b> required stations. Current planning capacity proxy: {estimate.current_planning_capacity_pct}%.</p>
            <ul>{estimate.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
          <div className="planning-result-card">
            <strong>Data source and explainability</strong>
            <p>{result.meta.source} · {result.meta.geography_scope}</p>
            {result.meta.data_sources && result.meta.data_sources.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <strong>Sources:</strong>
                <ul style={{ margin: '4px 0 0 16px', fontSize: '0.85rem' }}>
                  {result.meta.data_sources.map((ds) => (
                    <li key={ds.name}><b>{ds.name}</b> ({ds.type}): {ds.disclaimer || ds.publisher || ds.attribution || 'Verified reference'}</li>
                  ))}
                </ul>
              </div>
            )}
            {result.meta.assumptions_used && (
              <p style={{ fontSize: '0.82rem', color: '#64748b', marginTop: 6 }}>
                <b>Key Assumptions:</b> {result.meta.assumptions_used.join('; ')}
              </p>
            )}
            <strong>Limitations</strong>
            <ul>{result.meta.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
        </>}
      </section>
    </div>
  </div>
}
