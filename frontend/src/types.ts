export type Trade = {
  seq: number
  trade_id: string
  client: string
  symbol: string
  quantity: number
  price: number
  timestamp: string
  pulled_at: string
}

export type PullState = 'idle' | 'running' | 'completed' | 'failed'

export type PullStatus = {
  status: PullState
  pages_done: number
  total_pages: number | null
  trades_saved: number
  error: string | null
}

export type TradesResponse = { trades: Trade[]; total: number; latest_seq: number | null }
export type HelloMessage = { type: 'hello'; status: PullStatus; latest_seq: number | null }
export type TradesMessage = { type: 'trades'; trades: Trade[]; total: number; latest_seq: number }
export type ProgressMessage = PullStatus & { type: 'progress' }
export type PingMessage = { type: 'ping' }
export type WebSocketMessage = HelloMessage | TradesMessage | ProgressMessage | PingMessage
export type ConnectionState = 'live' | 'reconnecting' | 'offline'
