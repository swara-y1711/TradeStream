import type { ConnectionState } from '../types'
const labels: Record<ConnectionState, string> = { live: 'Live', reconnecting: 'Reconnecting', offline: 'Offline' }
export function ConnectionBadge({ state }: { state: ConnectionState }) { return <span className={`connection-badge ${state}`}>{labels[state]}</span> }
