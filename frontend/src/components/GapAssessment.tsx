import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { AlertTriangle, ArrowUpRight, Calculator, Layers, RefreshCw, ShieldAlert, Zap } from 'lucide-react'
import { analyzeGap, loadClassComparison, loadDistricts, loadStates } from '../services/chargerApi'
import type { ClassComparisonResponse, DistrictOption, GapAssessmentResponse, GapWeights, StateOption, VehicleClass } from '../types/station'

const initialWeights: GapWeights = { station_scarcity: 0.5, target_shortfall: 0.3, vehicle_compatibility: 0.2 }

export default function GapAssessment() {
  const [states, setStates] = useState<StateOption[]>([])
  const [districts, setDistricts] = useState<DistrictOption[]>([])
  const [state, setState] = useState('')
  const [district, setDistrict] = useState('')
  const [vehicleClass, setVehicleClass] = useState<VehicleClass | ''>('')
  const [target, setTarget] = useState(25)
  const [weights, setWeights] = useState<GapWeights>(initialWeights)
  const [result, setResult] = useState<GapAssessmentResponse | null>(null)
  const [loadingStates, setLoadingStates] = useState(true)
  const [loadingDistricts, setLoadingDistricts] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [activeTab, setActiveTab] = useState<'district' | 'disparity'>('district')
  const [disparityData, setDisparityData] = useState<ClassComparisonResponse['data'] | null>(null)
  const [loadingDisparity, setLoadingDisparity] = useState(false)

  useEffect(() => {
    if (activeTab !== 'disparity') return
    const controller = new AbortController()
    setLoadingDisparity(true)
    loadClassComparison(state || 'Karnataka', controller.signal)
      .then((res) => setDisparityData(res.data))
      .catch((err) => console.error('Disparity load failed:', err))
      .finally(() => setLoadingDisparity(false))
    return () => controller.abort()
  }, [activeTab, state])

  useEffect(() => {
    const controller = new AbortController()
    setLoadingStates(true)
    loadStates(controller.signal).then((items) => {
      setStates(items)
      setError('')
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not load the state directory.')
    }).finally(() => { if (!controller.signal.aborted) setLoadingStates(false) })
    return () => controller.abort()
  }, [retryKey])

  useEffect(() => {
    if (!state) { setDistricts([]); setDistrict(''); return }
    const controller = new AbortController()
    setLoadingDistricts(true)
    setDistrict('')
    setDistricts([])
    setResult(null)
    loadDistricts(state, controller.signal).then(({ districts: items }) => {
      setDistricts(items)
      setError('')
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not load districts for this state.')
    }).finally(() => { if (!controller.signal.aborted) setLoadingDistricts(false) })
    return () => controller.abort()
  }, [state, retryKey])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!state || !district) return
    setAnalyzing(true)
    setError('')
    setResult(null)
    try {
      setResult(await analyzeGap({
        state,
        district,
        vehicle_class: vehicleClass || null,
        target_stations_per_district: target,
        weights,
      }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The gap assessment could not be calculated.')
    } finally {
      setAnalyzing(false)
    }
  }

  function updateWeight(key: keyof GapWeights, value: number) {
    setWeights((previous) => ({ ...previous, [key]: value }))
    setResult(null)
  }

  const assessment = result?.data
  const scoreStyle = assessment ? { '--score': `${assessment.score * 3.6}deg` } as CSSProperties : undefined

  return <div className="gap-page">
    <div className="gap-intro">
      <div><span className="gap-kicker"><Calculator size={13} /> TRANSPARENT PROXY MODEL</span><h2>Assess relative station scarcity</h2><p>Compare a district's directory counts with other districts in its state using explicit, editable assumptions.</p></div>
      <div className="gap-proxy-notice"><ShieldAlert size={16} /><span>This is an exploratory station-count proxy, not a validated national infrastructure gap model.</span></div>
    </div>

    {error && <div className="analytics-alert gap-error" role="alert"><span>{error}</span><button onClick={() => setRetryKey((value) => value + 1)}>Retry</button></div>}

    <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
      <button
        type="button"
        style={{
          display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8,
          border: '1px solid #cbd5e1', cursor: 'pointer',
          background: activeTab === 'district' ? '#0f766e' : '#ffffff',
          color: activeTab === 'district' ? '#ffffff' : '#334155',
          fontWeight: 600, fontSize: '0.9rem',
        }}
        onClick={() => setActiveTab('district')}
      >
        <Calculator size={15} /> District Scarcity Assessment
      </button>
      <button
        type="button"
        style={{
          display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8,
          border: '1px solid #cbd5e1', cursor: 'pointer',
          background: activeTab === 'disparity' ? '#0f766e' : '#ffffff',
          color: activeTab === 'disparity' ? '#ffffff' : '#334155',
          fontWeight: 600, fontSize: '0.9rem',
        }}
        onClick={() => setActiveTab('disparity')}
      >
        <Zap size={15} /> India 2W/3W vs 4W Disparity Engine
      </button>
    </div>

    {activeTab === 'disparity' ? (
      <div className="gap-disparity-view" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {loadingDisparity && <div className="page-load-state"><span className="planning-spinner" /> Loading 2W/3W disparity model for {state || 'Karnataka'}…</div>}
        {disparityData && !loadingDisparity && (
          <>
            <div className="gap-score-card">
              <div className="gap-result-heading">
                <div>
                  <span className="gap-kicker">NATIONAL FLEET SKEW ANALYSIS</span>
                  <h3>{disparityData.state} EV Reality: 2W & 3W Make Up {disparityData.fleet_share_2w3w_pct}% of Fleet</h3>
                  <p>Comparing 4W-only public chargers vs. Light EV (2W/3W) charging point access</p>
                </div>
                <span className="priority-pill priority-high" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #f87171' }}>
                  {disparityData.districts_with_severe_disparity_count} Districts with Severe Deficit
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginTop: 16 }}>
                <div style={{ padding: 12, background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>2W/3W Registered Fleet Share</span>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f766e' }}>{disparityData.fleet_share_2w3w_pct}%</div>
                  <small style={{ color: '#64748b' }}>Mass-market personal and commercial mobility</small>
                </div>
                <div style={{ padding: 12, background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>4W Car Registered Share</span>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#3b82f6' }}>{disparityData.fleet_share_4w_pct}%</div>
                  <small style={{ color: '#64748b' }}>Passenger four-wheelers</small>
                </div>
                <div style={{ padding: 12, background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Districts Analyzed</span>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#1e293b' }}>{disparityData.total_districts_analyzed}</div>
                  <small style={{ color: '#64748b' }}>State-wide cross-vehicle evaluation</small>
                </div>
              </div>
            </div>

            <div className="gap-factor-card">
              <header>
                <div>
                  <h3>District Ranking Divergence Table</h3>
                  <p>Highlighting districts where 4W infrastructure adequacy masks severe 2W/3W charging deficits.</p>
                </div>
                <span>RANK DIVERGENCE</span>
              </header>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #e2e8f0', color: '#475569' }}>
                      <th style={{ padding: '8px 12px' }}>District</th>
                      <th style={{ padding: '8px 12px' }}>4W Stations</th>
                      <th style={{ padding: '8px 12px' }}>2W/3W Points</th>
                      <th style={{ padding: '8px 12px' }}>EVs/Station (4W)</th>
                      <th style={{ padding: '8px 12px' }}>EVs/Point (2W/3W)</th>
                      <th style={{ padding: '8px 12px' }}>4W Rank</th>
                      <th style={{ padding: '8px 12px' }}>2W/3W Rank</th>
                      <th style={{ padding: '8px 12px' }}>Divergence</th>
                      <th style={{ padding: '8px 12px' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {disparityData.district_comparisons.slice(0, 15).map((row) => (
                      <tr key={row.district} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>{row.district}</td>
                        <td style={{ padding: '8px 12px' }}>{row.stations_4w}</td>
                        <td style={{ padding: '8px 12px' }}>{row.stations_2w3w}</td>
                        <td style={{ padding: '8px 12px' }}>{row.ev_per_station_4w}</td>
                        <td style={{ padding: '8px 12px', fontWeight: 600, color: row.ev_per_station_2w3w > 500 ? '#b91c1c' : '#334155' }}>
                          {row.ev_per_station_2w3w}
                        </td>
                        <td style={{ padding: '8px 12px' }}>#{row.rank_4w}</td>
                        <td style={{ padding: '8px 12px' }}>#{row.rank_2w3w}</td>
                        <td style={{ padding: '8px 12px', fontWeight: 700, color: row.rank_divergence >= 4 ? '#b91c1c' : row.rank_divergence > 0 ? '#d97706' : '#059669' }}>
                          {row.rank_divergence > 0 ? `+${row.rank_divergence}` : row.rank_divergence}
                        </td>
                        <td style={{ padding: '8px 12px' }}>
                          <span style={{
                            padding: '3px 8px', borderRadius: 4, fontSize: '0.75rem', fontWeight: 600,
                            background: row.disparity_label === 'Severe 2W/3W Deficit' ? '#fee2e2' : row.disparity_label === 'Moderate 2W/3W Deficit' ? '#fef3c7' : '#ecfdf5',
                            color: row.disparity_label === 'Severe 2W/3W Deficit' ? '#991b1b' : row.disparity_label === 'Moderate 2W/3W Deficit' ? '#92400e' : '#065f46',
                          }}>
                            {row.disparity_label}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="gap-methodology-card">
              <h3>Policy Takeaways for Planners & Evaluators</h3>
              <ul>
                {disparityData.policy_takeaways.map((item, idx) => (
                  <li key={idx} style={{ marginBottom: 6 }}>{item}</li>
                ))}
              </ul>
              <small>Calibrated to MoRTH VAHAN national statistics & BEE charging directory.</small>
            </div>
          </>
        )}
      </div>
    ) : (
    <div className="gap-content-grid">
      <form className="gap-form-card" onSubmit={submit}>
        <div className="gap-form-heading"><div><h3>Assessment inputs</h3><p>All results are reproducible from these inputs.</p></div><span>1 state + 1 district</span></div>

        <label className="gap-field"><span>State / UT</span><select required value={state} disabled={loadingStates || !states.length} onChange={(event) => { setState(event.target.value); setResult(null); setError('') }}>
          <option value="">{loadingStates ? 'Loading states...' : 'Choose a state / UT'}</option>{states.map((item) => <option value={item.name} key={item.code}>{item.name}</option>)}
        </select></label>
        <label className="gap-field"><span>District</span><select required value={district} disabled={!state || loadingDistricts || !districts.length} onChange={(event) => { setDistrict(event.target.value); setResult(null) }}>
          <option value="">{!state ? 'Choose state first' : loadingDistricts ? 'Loading districts...' : 'Choose a district'}</option>{districts.map((item) => <option value={item.name} key={item.name}>{item.name} ({item.station_count.toLocaleString('en-IN')})</option>)}
        </select></label>
        {state && !loadingDistricts && districts.length > 0 && <small className="field-note">District counts are from the upstream state city directory.</small>}

        <label className="gap-field"><span>Vehicle class <small>(optional)</small></span><select value={vehicleClass} onChange={(event) => { setVehicleClass(event.target.value as VehicleClass | ''); setResult(null) }}>
          <option value="">All classes</option><option value="2W">2W - two-wheelers</option><option value="3W">3W - three-wheelers</option><option value="4W">4W - cars / four-wheelers</option>
        </select></label>

        <label className="gap-field target-field"><span>Illustrative target station rows per district</span><div><input type="number" min={1} max={10000} value={target} onChange={(event) => { setTarget(Number(event.target.value)); setResult(null) }} /><small>Assumption, not an official standard</small></div></label>

        <div className="weight-heading"><strong>Scoring weights</strong><span>Normalized to 100% at calculation</span></div>
        <WeightSlider label="Relative station scarcity" value={weights.station_scarcity} onChange={(value) => updateWeight('station_scarcity', value)} />
        <WeightSlider label="Target shortfall" value={weights.target_shortfall} onChange={(value) => updateWeight('target_shortfall', value)} />
        <WeightSlider label="Vehicle compatibility gap" value={weights.vehicle_compatibility} onChange={(value) => updateWeight('vehicle_compatibility', value)} />
        <p className="weights-note">If compatibility records are unavailable, that factor is omitted and the remaining active weights are renormalized.</p>
        <button className="analyze-button" type="submit" disabled={!state || !district || loadingDistricts || analyzing || (weights.station_scarcity + weights.target_shortfall === 0 && (!vehicleClass || weights.vehicle_compatibility === 0))}>
          {analyzing ? <><RefreshCw size={15} className="spin" /> Calculating...</> : <><Calculator size={15} /> Analyze gap</>}
        </button>
      </form>

      <section className="gap-results" aria-live="polite">
        {!assessment && !analyzing && <div className="gap-empty-state"><div><Calculator size={23} /></div><h3>Choose a geography to begin</h3><p>Analysis uses upstream district station counts, optional sampled vehicle compatibility, and the assumptions shown in the form.</p></div>}
        {analyzing && <div className="gap-empty-state"><RefreshCw size={22} className="spin" /><h3>Calculating assessment</h3><p>Retrieving a capped station sample for the selected district.</p></div>}
        {assessment && result && <>
          <div className="gap-score-card">
            <div className="gap-result-heading"><div><span className="gap-kicker">DISTRICT PROXY SCORE</span><h3>{assessment.district}, {assessment.state}</h3><p>Snapshot dated {result.meta.snapshot_date}</p></div><span className={`priority-pill priority-${assessment.priority.toLowerCase()}`}>{assessment.priority} priority</span></div>
            <div className="score-summary">
              <div className={`score-dial score-${assessment.priority.toLowerCase()}`} style={scoreStyle}><div><strong>{assessment.score.toFixed(1)}</strong><span>/ 100</span></div></div>
              <div className="score-summary-copy"><strong>{assessment.explanation[0]}</strong><p>{assessment.explanation[1]}</p><div className="score-legend"><span>Monitor &lt;40</span><span>Medium 40-69</span><span>High 70+</span></div></div>
            </div>
          </div>

          <div className="gap-evidence-grid">
            <article><span>District directory station rows</span><strong>{assessment.district_station_count.toLocaleString('en-IN')}</strong><small>/v1/cities aggregate; score uses this count</small></article>
            <article><span>District position</span><strong>{assessment.district_rank_by_station_count} <em>/ {assessment.districts_in_state}</em></strong><small>Sorted by station count, ascending</small></article>
            <article><span>Valid-coordinate records loaded</span><strong>{assessment.valid_coordinate_records_loaded}</strong><small>Of {assessment.records_available_in_filtered_district_query.toLocaleString('en-IN')} matching the district query</small></article>
            {vehicleClass && <article><span>{vehicleClass} compatible in sample</span><strong>{assessment.compatible_records_loaded} <em>/ {assessment.class_records_loaded} known</em></strong><small>{assessment.compatibility_sample_coverage_pct.toFixed(1)}% of filtered station query represented by rows with known compatibility</small></article>}
          </div>

          <div className="gap-factor-card">
            <header><div><h3>Score breakdown</h3><p>100 x weighted mean of factor scores; active weights are normalized to 100%.</p></div><span>WEIGHTED</span></header>
            {assessment.factors.map((factor) => <div className="factor-row" key={factor.key}>
              <div className="factor-label"><strong>{factor.label}</strong><span>{factor.explanation}</span></div>
              <div className="factor-meter"><i style={{ width: `${factor.value * 100}%` }} /></div>
              <div className="factor-numbers"><strong>{Math.round(factor.value * 100)}%</strong><small>{Math.round(factor.applied_weight * 100)}% wt.</small></div>
            </div>)}
            {assessment.explanation.slice(2).map((item) => <p className="gap-reason" key={item}><ArrowUpRight size={13} />{item}</p>)}
          </div>

          <div className="gap-methodology-card">
            <h3>Data scope and limitations</h3>
            <p>{result.meta.coverage_note}</p>
            <ul>{result.meta.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
            <small>Source: {result.meta.publisher}. {result.meta.attribution}</small>
          </div>
        </>}
      </section>
    </div>
    )}
  </div>
}

function WeightSlider({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label className="weight-slider"><span>{label}<b>{Math.round(value * 100)}%</b></span><input type="range" min="0" max="1" step="0.05" value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>
}
