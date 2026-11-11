import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchPullStatus, fetchTrades, startPull, webSocketUrl } from './api'
import type { ConnectionState, PullStatus, Trade, TradesResponse, WebSocketMessage } from './types'

const emptyStatus: PullStatus = { status: 'idle', pages_done: 0, total_pages: null, trades_saved: 0, error: null }
const MAX_VISIBLE_TRADES = 200
const newestFirst = (trades: Iterable<Trade>) => [...trades].sort((a, b) => b.seq - a.seq).slice(0, MAX_VISIBLE_TRADES)

export function useTrades() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [total, setTotal] = useState(0)
  const [pullStatus, setPullStatus] = useState<PullStatus>(emptyStatus)
  const [connectionState, setConnectionState] = useState<ConnectionState>('offline')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newSeqs, setNewSeqs] = useState<Set<number>>(new Set())
  const tradesRef = useRef(new Map<number, Trade>())
  const highestSeqRef = useRef(0)
  const socketRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptRef = useRef(0)

  const mergeTrades = useCallback((incoming: Trade[], highlight: boolean) => {
    const added = new Set<number>()
    for (const trade of incoming) {
      if (!tradesRef.current.has(trade.seq)) added.add(trade.seq)
      tradesRef.current.set(trade.seq, trade)
      highestSeqRef.current = Math.max(highestSeqRef.current, trade.seq)
    }
    setTrades(newestFirst(tradesRef.current.values()))
    if (highlight && added.size > 0) {
      setNewSeqs(added)
      if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current)
      highlightTimerRef.current = setTimeout(() => setNewSeqs(new Set()), 1800)
    }
  }, [])

  useEffect(() => {
    let disposed = false
    const closeSocket = () => {
      const socket = socketRef.current
      socketRef.current = null
      if (socket) { socket.onclose = null; socket.onerror = null; socket.close() }
    }
    const connect = () => {
      if (disposed) return
      closeSocket()
      setConnectionState(reconnectAttemptRef.current === 0 ? 'offline' : 'reconnecting')
      const socket = new WebSocket(webSocketUrl(highestSeqRef.current))
      socketRef.current = socket
      socket.onopen = () => { reconnectAttemptRef.current = 0; setConnectionState('live') }
      socket.onmessage = (event: MessageEvent<string>) => {
        let message: WebSocketMessage
        try { message = JSON.parse(event.data) as WebSocketMessage } catch { return }
        if (message.type === 'ping') return
        if (message.type === 'hello') {
          setPullStatus(message.status)
          highestSeqRef.current = Math.max(highestSeqRef.current, message.latest_seq ?? 0)
        } else if (message.type === 'trades') {
          mergeTrades(message.trades, true)
          setTotal(message.total)
          highestSeqRef.current = Math.max(highestSeqRef.current, message.latest_seq)
        } else setPullStatus(message)
      }
      const scheduleReconnect = () => {
        if (disposed || reconnectTimerRef.current) return
        const delay = Math.min(1000 * 2 ** reconnectAttemptRef.current, 10000)
        reconnectAttemptRef.current += 1
        setConnectionState('reconnecting')
        reconnectTimerRef.current = setTimeout(() => { reconnectTimerRef.current = null; connect() }, delay)
      }
      socket.onerror = () => socket.close()
      socket.onclose = scheduleReconnect
    }
    const load = async () => {
      try {
        const initialTrades: TradesResponse = await fetchTrades()
        if (disposed) return
        mergeTrades(initialTrades.trades, false)
        setTotal(initialTrades.total)
        highestSeqRef.current = Math.max(highestSeqRef.current, initialTrades.latest_seq ?? 0)
        setLoading(false)
        connect()
      } catch (loadError) {
        if (disposed) return
        setError(loadError instanceof Error ? loadError.message : 'Unable to load trades')
        setLoading(false)
        reconnectTimerRef.current = setTimeout(connect, 1000)
      }
    }
    void load()
    void fetchPullStatus().then((status) => { if (!disposed) setPullStatus(status) }).catch(() => { if (!disposed) setError('Unable to load pull status') })
    return () => {
      disposed = true; closeSocket()
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current)
    }
  }, [mergeTrades])

  const triggerPull = useCallback(async () => {
    try { setPullStatus(await startPull()); setError(null) }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Unable to start pull') }
  }, [])
  return { trades, total, pullStatus, connectionState, loading, error, newSeqs, triggerPull }
}
