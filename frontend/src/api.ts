import type { PullStatus, TradesResponse } from './types'

const backendUrl = (import.meta.env.VITE_MAIN_BACKEND_URL ?? 'http://localhost:8000').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${backendUrl}${path}`, init)
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
  return response.json() as Promise<T>
}

export const fetchTrades = () => request<TradesResponse>('/trades?limit=200')
export const fetchPullStatus = () => request<PullStatus>('/pull/status')
export const startPull = () => request<PullStatus>('/pull', { method: 'POST' })

export function webSocketUrl(afterSeq: number): string {
  const url = new URL(backendUrl)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = `${url.pathname.replace(/\/$/, '')}/ws`
  url.search = new URLSearchParams({ after_seq: String(afterSeq) }).toString()
  return url.toString()
}
