/**
 * Measured results loader.
 *
 * Reads attack_metrics.json + attack_lab_demo.json written by
 * `python scripts/run_attacks.py` into web/public/. Falls back to the
 * hand-written demo data only when those files are missing, and always tells
 * the UI which one it is showing so nothing seeded is passed off as measured.
 */
import { useEffect, useState } from 'react'
import { ATTACK_DEMO, HAR_TABLE, type AttackDemo } from './demo'

export const GATES = ['G0', 'G1', 'G2A', 'G2'] as const
export type Gate = (typeof GATES)[number]

export type HarRow = { attack: string } & Partial<Record<Gate, number | null>>
export type ResultsSource = 'measured' | 'sim' | 'demo'

export type Results = {
  source: ResultsSource
  trader: string
  rows: AttackDemo[]
  har: HarRow[]
  attacks: string[]
  scenarios: string[]
}

const FALLBACK: Results = {
  source: 'demo',
  trader: 'hand-written demo',
  rows: ATTACK_DEMO,
  har: HAR_TABLE.map((r) => ({ attack: r.attack, G0: r.g0, G1: r.g1, G2: r.g2 })),
  attacks: ['clean', 'A1', 'A4'],
  scenarios: ['sc-001'],
}

export function useResults(): Results {
  const [res, setRes] = useState<Results>(FALLBACK)
  useEffect(() => {
    const base = import.meta.env.BASE_URL
    Promise.all([
      fetch(`${base}attack_metrics.json`).then((r) => (r.ok ? r.json() : null)),
      fetch(`${base}attack_lab_demo.json`).then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([metrics, lab]) => {
        if (!metrics?.summary || !lab?.rows) return
        const trader: string = metrics.meta?.trader ?? 'unknown'
        const rows: AttackDemo[] = lab.rows
        setRes({
          source: trader === 'sim' ? 'sim' : 'measured',
          trader,
          rows,
          har: metrics.summary.map((s: Record<string, unknown>) => {
            const out: HarRow = { attack: String(s.attack) }
            for (const g of GATES) out[g] = (s[`${g}_HAR`] as number | null | undefined) ?? null
            return out
          }),
          attacks: Array.from(new Set(rows.map((r) => r.attack))),
          scenarios: Array.from(new Set(rows.map((r) => r.scenario_id))),
        })
      })
      .catch(() => undefined)
  }, [])
  return res
}

export function sourceLabel(r: Results): string {
  // The page says the numbers come from a real model on real setups, not which provider answered
  if (r.source === 'measured') return 'Measured · real AI on real setups'
  if (r.source === 'sim') return 'Simulated trader · not evidence'
  return 'Demo data · not measured'
}

export const pct = (x: number | null | undefined) =>
  x === null || x === undefined ? '-' : `${Math.round(x * 100)}%`
