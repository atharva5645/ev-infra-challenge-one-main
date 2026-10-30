import { useEffect, useState, type FormEvent } from 'react'
import { CircleDot, RotateCcw, Scale, Wallet, AlertCircle, MapPin, CheckCircle2 } from 'lucide-react'
import { loadStates, optimizeBudget } from '../services/chargerApi'
import type { CandidateSite, OptimizePayload, OptimizeResponse } from '../types/planning'
import type { StateOption } from '../types/station'

type Objective = OptimizePayload['objective']
type WeightKey = keyof OptimizePayload['weights']
const initialWeights: Record<Objective, OptimizePayload['weights']> = {
  maximum_coverage: { coverage: 0.6, gap_reduction: 0.25, equity: 0.15 },
  maximum_gap_reduction: { coverage: 0.15, gap_reduction: 0.7, equity: 0.15 },
  balanced_equity: { coverage: 0.34, gap_reduction: 0.33, equity: 0.33 },
}
const initial = { state: '', budget: '25000000', acShare: '70', acCost: '1500000', dcCost: '3500000' }
const inr = (value: number) => `₹${value.toLocaleString('en-IN')}`
const objectiveLabels: Record<Objective, string> = {
  maximum_coverage: 'Maximum candidate-area coverage',
  maximum_gap_reduction: 'Maximum relative gap reduction',
  balanced_equity: 'Balanced equity',
}

export default function BudgetOptimizer() {
  const [states, setStates] = useState<StateOption[]>([])
  const [values, setValues] = useState(initial)
  const [objective, setObjective] = useState<Objective>('balanced_equity')
  const [weights, setWeights] = useState(initialWeights.balanced_equity)
  const [result, setResult] = useState<OptimizeResponse | null>(null)
  const [loadingStates, setLoadingStates] = useState(true)
  const [optimizing, setOptimizing] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [transferredSites, setTransferredSites] = useState<CandidateSite[]>([])
  const [includeDeadZones, setIncludeDeadZones] = useState(true)

  useEffect(() => {
    function checkStorage() {
      try {
        const stored = sessionStorage.getItem('pending_dead_zones')
        if (stored) {
          const parsed = JSON.parse(stored) as CandidateSite[]
          if (Array.isArray(parsed) && parsed.length > 0) {
            setTransferredSites(parsed)
            if (!values.state && parsed[0]?.state) {
              setValues((prev) => ({ ...prev, state: parsed[0].state || '' }))
            }
          }
        }
      } catch {
        // ignore storage parse errors
      }
    }
    checkStorage()
    window.addEventListener('storage', checkStorage)
    return () => window.removeEventListener('storage', checkStorage)
  }, [values.state])

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

  function changeWeight(key: WeightKey, value: number) {
    setWeights((previous) => ({ ...previous, [key]: value / 100 }))
    setResult(null)
  }

  function changeObjective(value: Objective) {
    setObjective(value)
    setWeights(initialWeights[value])
    setResult(null)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setOptimizing(true)
    setResult(null)
    try {
      const sitesToInclude = includeDeadZones && transferredSites.length > 0
        ? transferredSites.filter((s) => !values.state || !s.state || s.state.toLowerCase() === values.state.toLowerCase())
        : undefined
      setResult(await optimizeBudget({
        state: values.state,
        available_budget_inr: Number(values.budget),
        objective,
        ac_allocation_pct: Number(values.acShare),
        ac_cost_per_station_inr: Number(values.acCost),
        dc_cost_per_station_inr: Number(values.dcCost),
        weights,
        candidate_sites: sitesToInclude && sitesToInclude.length > 0 ? sitesToInclude : undefined,
      }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The budget scenario could not be calculated.')
    } finally {
      setOptimizing(false)
    }
  }

  const scenario = result?.data
  const budgetUsedPct = scenario && scenario.available_budget_inr > 0 ? scenario.budget_used_inr / scenario.available_budget_inr * 100 : 0

  return <div className="planning-page">
    <div className="planning-intro">
      <div><span className="planning-kicker"><Scale size={13} /> BUDGET-CONSTRAINED SCENARIO</span><h2>Prioritize illustrative district opportunities</h2><p>Rank hypothetical one-station packages using directory station counts, an editable deployment mix and a fixed budget.</p></div>
      <span className="planning-status planning-status-illustrative"><CircleDot size={13} /> Illustrative candidates</span>
    </div>
    <div className="planning-notice"><Wallet size={15} /><span>Districts come from the source directory, but these are not verified host sites. The score is a transparent relative station-scarcity proxy; demand, grid readiness, land access and site-specific costs are unavailable.</span></div>
    
    {transferredSites.length > 0 && (
      <div className="analytics-alert" style={{ background: '#fef3c7', borderColor: '#f59e0b', color: '#92400e', marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 1rem', borderRadius: 8, border: '1px solid #f59e0b' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <MapPin size={18} style={{ color: '#d97706', flexShrink: 0 }} />
          <div>
            <strong>Cross-Module Link: {transferredSites.length} Highway Dead Zone Candidate{transferredSites.length > 1 ? 's' : ''} Transferred from Trip Planner</strong>
            <div style={{ fontSize: '0.85rem', marginTop: 2 }}>
              High-deficit corridor segments converted into candidate deployment packages for budget ranking.
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <label style={{ display: 'inline-flex', alignItems: 'center', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
            <input
              type="checkbox"
              checked={includeDeadZones}
              onChange={(e) => setIncludeDeadZones(e.target.checked)}
              style={{ marginRight: 6 }}
            />
            Include in Optimizer
          </label>
          <button
            type="button"
            onClick={() => {
              sessionStorage.removeItem('pending_dead_zones')
              setTransferredSites([])
            }}
            style={{ background: 'transparent', border: 'none', color: '#b45309', cursor: 'pointer', textDecoration: 'underline', fontSize: '0.85rem' }}
          >
            Clear
          </button>
        </div>
      </div>
    )}

    {error && <div className="analytics-alert planning-error" role="alert"><span>{error}</span><button onClick={() => setRetry((value) => value + 1)}>Retry state directory</button></div>}

    <div className="planning-layout optimizer-layout">
      <form className="planning-form" onSubmit={submit}>
        <div className="planning-form-heading"><div><h3>Optimization inputs</h3><p>Run a reproducible budget scenario.</p></div><button type="button" className="planning-reset" onClick={() => { setValues(initial); setObjective('balanced_equity'); setWeights(initialWeights.balanced_equity); setResult(null); setError('') }}><RotateCcw size={12} /> Reset</button></div>
        <label className="planning-field"><span>State / UT</span><select required value={values.state} disabled={loadingStates || !states.length} onChange={(event) => change('state', event.target.value)}>
          <option value="">{loadingStates ? 'Loading states...' : 'Choose a state / UT'}</option>{states.map((item) => <option key={item.code} value={item.name}>{item.name}</option>)}
        </select></label>
        <label className="planning-field"><span>Available budget (₹)</span><input required type="number" min="0" max="1000000000000000" step="100000" value={values.budget} onChange={(event) => change('budget', event.target.value)} /><small>INR budget cap for the proposed packages</small></label>
        <label className="planning-field"><span>Optimization objective</span><select value={objective} onChange={(event) => changeObjective(event.target.value as Objective)}>{Object.entries(objectiveLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>

        <div className="planning-section-heading"><strong>Deployment mix and cost assumptions</strong><span>Editable INR per station</span></div>
        <label className="planning-field planning-range-field"><span>AC share <b>{values.acShare}%</b><small>DC share {100 - (Number(values.acShare) || 0)}%</small></span><input type="range" min="0" max="100" step="5" value={values.acShare} onChange={(event) => change('acShare', event.target.value)} /></label>
        <div className="planning-field-grid planning-cost-grid">
          <label className="planning-field"><span>AC cost / station (₹)</span><input required type="number" min="0" max="10000000000" step="10000" value={values.acCost} onChange={(event) => change('acCost', event.target.value)} /></label>
          <label className="planning-field"><span>DC cost / station (₹)</span><input required type="number" min="0" max="10000000000" step="10000" value={values.dcCost} onChange={(event) => change('dcCost', event.target.value)} /></label>
        </div>

        <div className="planning-section-heading"><strong>Benefit weights</strong><span>Normalized by the service</span></div>
        <WeightSlider label="Candidate-area coverage" value={weights.coverage} onChange={(value) => changeWeight('coverage', value)} />
        <WeightSlider label="Relative gap reduction" value={weights.gap_reduction} onChange={(value) => changeWeight('gap_reduction', value)} />
        <WeightSlider label="Equity" value={weights.equity} onChange={(value) => changeWeight('equity', value)} />
        <p className="weights-note">Presets vary by objective. You can adjust the weights; each must remain between 0 and 100%, and at least one must be positive.</p>
        <button className="planning-submit" type="submit" disabled={!values.state || loadingStates || optimizing || Object.values(weights).every((value) => value === 0)}>{optimizing ? <><span className="planning-spinner" /> Ranking candidates...</> : <><Scale size={15} /> Run optimization</>}</button>
      </form>

      <section className="planning-results optimizer-results" aria-live="polite">
        {!scenario && !optimizing && <div className="planning-empty"><Wallet size={25} /><h3>Configure a budget scenario</h3><p>The service will retrieve the selected state's district station directory, rank one hypothetical package per district and stay within the budget.</p></div>}
        {optimizing && <div className="planning-empty"><span className="planning-spinner" /><h3>Ranking district opportunities</h3><p>Using the cached state directory and your selected objective, weights and budget.</p></div>}
        {scenario && result && <>
          <div className="planning-result-head"><div><span className="planning-kicker">BUDGET SCENARIO</span><h3>{scenario.state}</h3><p>{objectiveLabels[scenario.objective as Objective]} · snapshot {result.meta.snapshot_date}</p></div><span className="planning-status planning-status-illustrative">HEURISTIC</span></div>
          <div className="planning-result-kpis">
            <article><span>Budget used</span><strong>{inr(scenario.budget_used_inr)}</strong><small>Of {inr(scenario.available_budget_inr)}</small></article>
            <article><span>Budget remaining</span><strong>{inr(scenario.remaining_budget_inr)}</strong><small>Never exceeds available budget</small></article>
            <article><span>Proposed installations</span><strong>{scenario.proposed_installations.toLocaleString('en-IN')}</strong><small>{scenario.estimated_ac_installations} AC · {scenario.estimated_dc_installations} DC</small></article>
            <article><span>Relative opportunity gain</span><strong>{scenario.estimated_relative_benefit_gain_pct}%</strong><small>Share of candidate benefit score ranked</small></article>
          </div>
          <div className="planning-result-card">
            <div className="planning-section-heading"><strong>Budget allocation</strong><span>{inr(scenario.budget_used_inr)} used</span></div>
            <div className="planning-budget-track"><i style={{ width: `${budgetUsedPct}%` }} /></div>
            <div className="planning-allocation-legend"><span><i className="allocation-ac" /> AC packages <b>{scenario.estimated_ac_installations}</b></span><span><i className="allocation-dc" /> DC packages <b>{scenario.estimated_dc_installations}</b></span></div>
          </div>
          <div className="planning-result-card">
            <div className="planning-section-heading"><strong>Candidate-area scenario</strong><span>Illustrative relative proxy</span></div>
            <div className="planning-before-after"><div><span>Baseline</span><b>{scenario.estimated_candidate_coverage_before_pct}%</b><small>{scenario.baseline_candidate_areas_covered} hypothetical areas covered</small></div><div className="planning-comparison-arrow">→</div><div><span>Estimated scenario</span><b>{scenario.estimated_candidate_coverage_after_pct}%</b><small>{scenario.estimated_candidate_areas_covered} of {scenario.ranked_candidates.length} areas receive one package</small></div></div>
            <p className="planning-footnote">Coverage here means the share of listed district candidates receiving one proposed package. It is not measured road, population or geographic service coverage.</p>
          </div>
          <div className="planning-result-card">
            <div className="planning-section-heading"><strong>Recommended areas</strong><span>{scenario.recommendations.length} selected</span></div>
            {!scenario.recommendations.length && <p className="planning-footnote">{scenario.empty_reason || 'No candidate package was selected.'}</p>}
            <ol className="planning-recommendations">
              {scenario.recommendations.map((item) => (
                <li key={item.candidate_id} style={item.origin_type === 'trip_dead_zone' ? { borderLeft: '4px solid #f59e0b', paddingLeft: 10 } : undefined}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <strong>{item.site_name || item.district}</strong>
                      {item.origin_type === 'trip_dead_zone' && (
                        <span style={{ background: '#fef3c7', color: '#b45309', fontSize: '0.72rem', padding: '1px 6px', borderRadius: 4, fontWeight: 700 }}>
                          🛣️ HIGHWAY DEAD ZONE
                        </span>
                      )}
                    </div>
                    <span>{item.deployment_type} station · {item.existing_station_rows.toLocaleString('en-IN')} existing directory station rows</span>
                    <small>{item.reason}</small>
                  </div>
                  <b>{inr(item.estimated_cost_inr)}</b>
                </li>
              ))}
            </ol>
          </div>
          <div className="planning-result-card planning-formula">
            <strong>Ranking method</strong>
            <p>{scenario.scoring_method}</p>
            <p>Applied weights: coverage {Math.round(scenario.weights_applied.coverage * 100)}%, gap reduction {Math.round(scenario.weights_applied.gap_reduction * 100)}%, equity {Math.round(scenario.weights_applied.equity * 100)}%. One hypothetical package is considered per district. No diminishing-returns curve is shown because the candidate source supplies no verified site-level or demand data.</p>
            
            {result.meta.data_sources && result.meta.data_sources.length > 0 && (
              <div style={{ marginTop: 12, borderTop: '1px solid #e2e8f0', paddingTop: 8 }}>
                <strong>Data Sources & Explainability</strong>
                <ul style={{ margin: '4px 0 0 16px', fontSize: '0.85rem' }}>
                  {result.meta.data_sources.map((ds) => (
                    <li key={ds.name}><b>{ds.name}</b> ({ds.type}): {ds.disclaimer || ds.publisher || ds.attribution || 'Verified reference'}</li>
                  ))}
                </ul>
                {result.meta.assumptions_used && (
                  <p style={{ fontSize: '0.82rem', color: '#64748b', marginTop: 6 }}>
                    <b>Key Assumptions:</b> {result.meta.assumptions_used.join('; ')}
                  </p>
                )}
                {result.meta.generated_at && (
                  <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: 4 }}>
                    Generated at: {new Date(result.meta.generated_at).toLocaleString('en-IN')}
                  </div>
                )}
              </div>
            )}

            <strong>Candidate data and limitations</strong>
            <p>{result.meta.candidate_scope} · {result.meta.source} · {result.meta.station_count_unit}.</p>
            <ul>{result.meta.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
        </>}
      </section>
    </div>
  </div>
}

function WeightSlider({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label className="planning-weight"><span>{label}<b>{Math.round(value * 100)}%</b></span><input type="range" min="0" max="100" step="5" value={Math.round(value * 100)} onChange={(event) => onChange(Number(event.target.value))} /></label>
}
