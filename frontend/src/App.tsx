import { ConnectionBadge } from './components/ConnectionBadge'
import { PullProgress } from './components/PullProgress'
import { TradesTable } from './components/TradesTable'
import { useTrades } from './useTrades'

function App() {
  const { trades, total, pullStatus, connectionState, loading, error, newSeqs, triggerPull } = useTrades()

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">TradeStream</p>
          <h1>Trades Dashboard</h1>
          <p className="subtitle">Live market-trade visibility, without a refresh.</p>
        </div>
        <div className="header-actions">
          <ConnectionBadge state={connectionState} />
          <button onClick={() => void triggerPull()} disabled={pullStatus.status === 'running'}>Start new pull</button>
        </div>
      </header>
      {error && <p className="error-banner" role="alert">{error}</p>}
      <PullProgress status={pullStatus} />
      {loading ? <section className="loading-card">Loading saved trades…</section> : <TradesTable trades={trades} total={total} newSeqs={newSeqs} />}
    </main>
  )
}

export default App
