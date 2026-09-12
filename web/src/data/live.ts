/**
 * Live paper bot feed for the Flight Recorder.
 *
 * scripts/export_paper_log.py writes paper_log/live.json on the paper-log branch after
 * every 15-minute cycle. A local copy (web/public/live.json) wins for previews; the
 * deployed site reads the branch. Returns null when neither exists, so the page falls
 * back to labelled demo data instead of pretending.
 */
import { useEffect, useState } from 'react'
import type { EquityPoint } from './demo'

export type LiveDecision = {
  id: number
  ts: string
  symbol: string
  side: string
  action: string
  confidence: number
  kind: string
  reason: string
  p_cal: number | null
  p_adj: number | null
  p_be: number | null
  anomaly: number | null
  checks: string[]
}

/** The newest check of one coin: when, its volatility regime, how many setups it found */
export type ScanRow = { symbol: string; ts: string; regime: string; setups: number }

export type LiveData = {
  generated_at: string
  status: { status: string; note: string; updated_at: string | null }
  /** Older exports lack bot, scan and counts.setups */
  bot?: { model: string; gate: string; fills: string; health: string }
  running_since: string | null
  symbols: number
  metrics: { equityGuarded: number; equityShadow: number; dayPnl: number; openPositions: number }
  counts: { cycles: number; setups?: number; proposals: number; takes: number; vetoes: number; orders: number }
  scan?: ScanRow[]
  equity: EquityPoint[]
  decisions: LiveDecision[]
  buckets: { bucket: string; gap: number; n: number }[]
  reliability: { stated: number; actual: number; n: number }[]
}

/** Set on the hosted site to its own /api/live, which reads the private paper-log branch */
const LIVE_URL = import.meta.env.VITE_LIVE_URL as string | undefined
/** Works only while the repo is public; harmless to try last */
const RAW = 'https://raw.githubusercontent.com/khalydmaina/tare/paper-log/paper_log/live.json'

/** A cycle runs every 15 minutes; past this the bot is treated as stalled */
const STALE_MINUTES = 40

export function minutesSince(iso: string | null | undefined): number | null {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isFinite(t) ? Math.max(0, Math.round((Date.now() - t) / 60_000)) : null
}

export function agoLabel(iso: string | null | undefined): string {
  const m = minutesSince(iso)
  if (m === null) return 'unknown'
  if (m < 1) return 'just now'
  if (m < 60) return `${m} min ago`
  const h = Math.round(m / 60)
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} days ago`
}

export function isFresh(live: LiveData): boolean {
  const m = minutesSince(live.status.updated_at)
  return m !== null && m <= STALE_MINUTES
}

export function useLive(): LiveData | null {
  const [data, setData] = useState<LiveData | null>(null)

  useEffect(() => {
    let cancelled = false
    const sources = LIVE_URL
      ? [LIVE_URL, `${import.meta.env.BASE_URL}live.json`]
      : [`${import.meta.env.BASE_URL}live.json`, RAW]
    const load = async () => {
      for (const url of sources) {
        try {
          const res = await fetch(url, { cache: 'no-store' })
          if (!res.ok) continue
          const json = (await res.json()) as LiveData
          if (json?.status && Array.isArray(json.decisions)) {
            if (!cancelled) setData(json)
            return
          }
        } catch {
          // try the next source
        }
      }
    }
    void load()
    const timer = window.setInterval(() => void load(), 60_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  return data
}
