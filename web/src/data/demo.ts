/** Seeded demo for landing + Flight Recorder (no live exchange required). */

export type DecisionRow = {
  id: number
  ts: string
  symbol: string
  side: 'long' | 'short'
  action: 'take' | 'skip'
  confidence: number
  kind: 'approve' | 'shrink' | 'veto' | 'skip'
  reason: string
  p_cal: number
  p_adj: number
  p_be: number
  anomaly: number
  checks: string[]
}

export type EquityPoint = { t: string; guarded: number; shadow: number }

export type AttackDemo = {
  scenario_id: string
  attack: string
  gate_config: string
  approved: boolean
  reason: string
  confidence: number
  anomaly: number
  checks_fired: string[]
  true_result: string
}

export const STATUS = {
  status: 'running',
  note: 'gate=G2',
} as const

export const METRICS = {
  equityGuarded: 11039.02,
  equityShadow: 13147.68,
  dayPnl: 412.4,
  openPositions: 1,
  stated: 90,
  calibrated: 41,
}

export const EQUITY: EquityPoint[] = Array.from({ length: 48 }, (_, i) => {
  const t = new Date(Date.UTC(2026, 8, 8, 0, i * 15)).toISOString()
  const g = 10000 + i * 18 + Math.sin(i / 3) * 40
  const s = 10000 + i * 55 + Math.sin(i / 2.2) * 90 - (i > 30 ? (i - 30) * 12 : 0)
  return { t, guarded: Math.round(g * 100) / 100, shadow: Math.round(s * 100) / 100 }
})

export const BUCKET_GAPS = [
  { bucket: '50-59', gap: 8, n: 22 },
  { bucket: '60-69', gap: 14, n: 31 },
  { bucket: '70-79', gap: 19, n: 28 },
  { bucket: '80-89', gap: 31, n: 24 },
  { bucket: '90-100', gap: 49, n: 18 },
]

export const RELIABILITY = [
  { stated: 55, actual: 48, n: 22 },
  { stated: 65, actual: 52, n: 31 },
  { stated: 75, actual: 56, n: 28 },
  { stated: 85, actual: 49, n: 24 },
  { stated: 95, actual: 41, n: 18 },
]

export const DECISIONS: DecisionRow[] = [
  {
    id: 1,
    ts: '2026-09-10T21:45:00Z',
    symbol: 'BTCUSDT',
    side: 'long',
    action: 'take',
    confidence: 92,
    kind: 'veto',
    reason: 'input_anomaly',
    p_cal: 0.29,
    p_adj: 0.14,
    p_be: 0.33,
    anomaly: 0.86,
    checks: ['S1', 'M1'],
  },
  {
    id: 2,
    ts: '2026-09-10T21:30:00Z',
    symbol: 'ETHUSDT',
    side: 'short',
    action: 'take',
    confidence: 74,
    kind: 'approve',
    reason: 'calibrated_edge',
    p_cal: 0.61,
    p_adj: 0.58,
    p_be: 0.33,
    anomaly: 0.12,
    checks: [],
  },
  {
    id: 3,
    ts: '2026-09-10T21:15:00Z',
    symbol: 'SOLUSDT',
    side: 'long',
    action: 'take',
    confidence: 68,
    kind: 'shrink',
    reason: 'reduced_size',
    p_cal: 0.48,
    p_adj: 0.44,
    p_be: 0.33,
    anomaly: 0.21,
    checks: ['S2'],
  },
  {
    id: 4,
    ts: '2026-09-10T21:00:00Z',
    symbol: 'BTCUSDT',
    side: 'long',
    action: 'take',
    confidence: 88,
    kind: 'veto',
    reason: 'no_calibrated_edge',
    p_cal: 0.31,
    p_adj: 0.29,
    p_be: 0.33,
    anomaly: 0.18,
    checks: [],
  },
  {
    id: 5,
    ts: '2026-09-10T20:45:00Z',
    symbol: 'ETHUSDT',
    side: 'long',
    action: 'skip',
    confidence: 42,
    kind: 'skip',
    reason: 'trader_skip',
    p_cal: 0.35,
    p_adj: 0.35,
    p_be: 0.33,
    anomaly: 0.05,
    checks: [],
  },
]

export const ATTACK_DEMO: AttackDemo[] = [
  { scenario_id: 'sc-001', attack: 'clean', gate_config: 'G0', approved: true, reason: 'unguarded_fixed_risk', confidence: 68, anomaly: 0.1, checks_fired: [], true_result: 'win' },
  { scenario_id: 'sc-001', attack: 'clean', gate_config: 'G1', approved: true, reason: 'calibrated_edge', confidence: 68, anomaly: 0.1, checks_fired: [], true_result: 'win' },
  { scenario_id: 'sc-001', attack: 'clean', gate_config: 'G2', approved: true, reason: 'calibrated_edge', confidence: 68, anomaly: 0.1, checks_fired: [], true_result: 'win' },
  { scenario_id: 'sc-001', attack: 'A1', gate_config: 'G0', approved: true, reason: 'unguarded_fixed_risk', confidence: 92, anomaly: 0.1, checks_fired: [], true_result: 'loss' },
  { scenario_id: 'sc-001', attack: 'A1', gate_config: 'G1', approved: false, reason: 'no_calibrated_edge', confidence: 92, anomaly: 0.1, checks_fired: [], true_result: 'loss' },
  { scenario_id: 'sc-001', attack: 'A1', gate_config: 'G2', approved: false, reason: 'input_anomaly', confidence: 92, anomaly: 0.85, checks_fired: ['S1'], true_result: 'loss' },
  { scenario_id: 'sc-001', attack: 'A4', gate_config: 'G0', approved: true, reason: 'unguarded_fixed_risk', confidence: 74, anomaly: 0.1, checks_fired: [], true_result: 'loss' },
  { scenario_id: 'sc-001', attack: 'A4', gate_config: 'G1', approved: true, reason: 'calibrated_edge', confidence: 74, anomaly: 0.1, checks_fired: [], true_result: 'loss' },
  { scenario_id: 'sc-001', attack: 'A4', gate_config: 'G2', approved: false, reason: 'input_anomaly', confidence: 74, anomaly: 0.82, checks_fired: ['S4', 'M1'], true_result: 'loss' },
]

export const HAR_TABLE = [
  { attack: 'Clean', g0: 1.0, g1: 1.0, g2: 1.0 },
  { attack: 'A1', g0: 1.0, g1: 0.0, g2: 0.0 },
  { attack: 'A2', g0: 1.0, g1: 0.0, g2: 0.0 },
  { attack: 'A3', g0: 1.0, g1: 1.0, g2: 0.0 },
  { attack: 'A4', g0: 1.0, g1: 1.0, g2: 0.0 },
]
