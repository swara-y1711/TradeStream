import type { PullStatus } from '../types'
const titleCase = (value: string) => value.charAt(0).toUpperCase() + value.slice(1)
export function PullProgress({ status }: { status: PullStatus }) {
  const progress = status.total_pages && status.total_pages > 0 ? Math.min(100, (status.pages_done / status.total_pages) * 100) : status.status === 'completed' ? 100 : 0
  return <section className="progress-card" aria-label="Pull progress"><div className="progress-heading"><div><p className="section-label">Data pull</p><h2>{status.status === 'running' ? 'Pulling trades' : 'Pull status'}</h2></div><span className={`pull-state ${status.status}`}>{titleCase(status.status)}</span></div><div className="progress-track" aria-hidden="true"><span style={{ width: `${progress}%` }} /></div><p className="progress-copy">{status.status === 'running' ? 'Pulling... ' : ''}{status.trades_saved.toLocaleString('en-IN')} trades{status.total_pages !== null && ` · ${status.pages_done} / ${status.total_pages} pages`}</p>{status.status === 'failed' && status.error && <p className="error-copy">{status.error}</p>}</section>
}
