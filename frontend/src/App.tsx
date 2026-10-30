import { lazy, Suspense, useEffect, useState } from 'react'
import {
  BookOpen, ChartNoAxesColumnIncreasing, CircleDot, FileText, Focus,
  Map, Menu, Route, X, Zap,
} from 'lucide-react'
import NationalMap from './components/NationalMap'
import { pingHealth } from './services/chargerApi'
const DecisionDashboard = lazy(() => import('./components/DecisionDashboard'))
const GapAssessment = lazy(() => import('./components/GapAssessment'))
const ChargerPlanner = lazy(() => import('./components/ChargerPlanner'))
const BudgetOptimizer = lazy(() => import('./components/BudgetOptimizer'))
const TripPlanner = lazy(() => import('./components/TripPlanner'))
const MethodologyData = lazy(() => import('./components/MethodologyData'))
const ReportsScalability = lazy(() => import('./components/ReportsScalability'))

const sections = [
  { name: 'National Map', icon: Map, subtitle: 'EV infrastructure intelligence platform' },
  { name: 'Dashboard', icon: ChartNoAxesColumnIncreasing, subtitle: 'A nationwide overview of charging infrastructure' },
  { name: 'Gap Assessment', icon: Focus, subtitle: 'Identify underserved areas and infrastructure gaps' },
  { name: 'Charger Planner', icon: Zap, subtitle: 'Explore charging site planning across India' },
  { name: 'Budget Optimizer', icon: CircleDot, subtitle: 'Plan investment for future charging networks' },
  { name: 'Trip Planner', icon: Route, subtitle: 'Plan journeys around EV charging availability' },
  { name: 'Methodology & Data', icon: BookOpen, subtitle: 'Learn about the data behind this platform' },
  { name: 'Reports & Scalability', icon: FileText, subtitle: 'Review reports and network scalability' },
]

function App() {
  const [active, setActive] = useState('National Map')
  const [menuOpen, setMenuOpen] = useState(false)
  const current = sections.find((section) => section.name === active)!

  useEffect(() => {
    const handler = () => setActive('Budget Optimizer')
    window.addEventListener('switch-to-budget-optimizer', handler)
    return () => window.removeEventListener('switch-to-budget-optimizer', handler)
  }, [])

  // Keep the Render free-tier backend awake while this page is open.
  useEffect(() => {
    const ping = () => { void pingHealth() }
    ping()
    const interval = window.setInterval(ping, 5 * 60 * 1000)
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') ping()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [])

  return (
    <main className="viewport">
      <div className="app-shell">
        <button className="mobile-menu" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} onClick={() => setMenuOpen(!menuOpen)}>
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
        {menuOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
        <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
          <div className="brand">
            <div className="brand-mark"><Zap size={23} strokeWidth={1.9} /></div>
            <div className="brand-copy"><strong>EV INFRA</strong><span>MAP INDIA</span></div>
          </div>
          <div className="sidebar-rule" />
          <nav aria-label="Main navigation">
            {sections.map(({ name, icon: ItemIcon }) => (
              <button key={name} className={`nav-item ${active === name ? 'active' : ''}`} aria-current={active === name ? 'page' : undefined}
                onClick={() => { setActive(name); setMenuOpen(false) }}>
                <ItemIcon size={17} strokeWidth={1.8} /><span>{name}</span>
              </button>
            ))}
          </nav>
        </aside>

        <section className="workspace" tabIndex={0} role="region" aria-label="Main page content">
          <header className="page-header">
            <div><h1>{active}</h1><p>{current.subtitle}</p></div>
            <span className="demo-badge"><i />{active === 'National Map' ? 'BEE DATA' : active === 'Dashboard' || active === 'Gap Assessment' ? 'ANALYTICS' : 'DEMO'}</span>
          </header>
          <Suspense fallback={<div className="page-load-state" role="status"><span className="planning-spinner" /> Loading {active}…</div>}>
            {active === 'National Map' ? <NationalMap /> : active === 'Dashboard' ? <DecisionDashboard /> : active === 'Gap Assessment' ? <GapAssessment /> : active === 'Charger Planner' ? <ChargerPlanner /> : active === 'Budget Optimizer' ? <BudgetOptimizer /> : active === 'Trip Planner' ? <TripPlanner /> : active === 'Methodology & Data' ? <MethodologyData /> : <ReportsScalability />}
          </Suspense>
        </section>
      </div>
    </main>
  )
}

export default App
