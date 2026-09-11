import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  ComposedChart,
  Line,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import { ScaleDial } from '../components/ScaleDial'
import { EquityChart } from '../components/EquityChart'
import { BUCKET_GAPS, DECISIONS, EQUITY, METRICS, RELIABILITY, STATUS } from '../data/demo'
import { GATES, pct, sourceLabel, useResults } from '../data/results'

type Tab = 'live' | 'attacks' | 'results'

export function FlightRecorder() {
  const [tab, setTab] = useState<Tab>('live')
  const results = useResults()
  const [pickedScenario, setScenario] = useState<string | null>(null)
  const [pickedAttack, setAttack] = useState<string | null>(null)
  const scenario = pickedScenario ?? results.scenarios[0] ?? ''
  const attack =
    pickedAttack ?? (results.attacks.includes('A4') ? 'A4' : (results.attacks[0] ?? 'clean'))
  const latest = DECISIONS[0]
  const veto = latest?.kind === 'veto'
  const isDemo = STATUS.status === 'demo'

  const gateCols = useMemo(
    () =>
      GATES.map((g) =>
        results.rows.find(
          (r) => r.scenario_id === scenario && r.attack === attack && r.gate_config === g,
        ),
      ),
    [results, scenario, attack],
  )

  return (
    <div className="relative min-h-[100dvh] bg-canvas text-ink">
      <div className="tare-grain" aria-hidden />

      {/* Top bar */}
      <header className="sticky top-0 z-40 border-b border-line bg-canvas/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between gap-4 px-3 md:px-5">
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2">
              <img src="/brand/tare-mark.svg" alt="" className="h-7 w-7" />
              <span className="tare-wordmark text-lg text-white">tare</span>
            </Link>
            <span className="hidden text-mute md:inline">/</span>
            <span className="hidden text-sm text-mute md:inline">Flight Recorder</span>
          </div>
          <div className="flex items-center gap-2">
            {(
              [
                ['live', 'Live'],
                ['attacks', 'Attack Lab'],
                ['results', 'Results'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`rounded-[4px] px-3 py-1.5 text-sm transition ${
                  tab === id
                    ? 'bg-elevated text-white border border-line-strong'
                    : 'text-mute hover:text-ink'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-3 py-4 md:px-5 md:py-6">
        {isDemo ? (
          <p className="mb-2 text-[11px] uppercase tracking-wide text-mute">
            Demo account · the live paper bot is not connected to this page yet
          </p>
        ) : null}

        {/* Status strip */}
        <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-4 md:gap-3">
          <Metric
            label="Status"
            value={
              <span
                className={`inline-block rounded-[4px] border px-2 py-0.5 tabular text-xs uppercase tracking-wide ${
                  STATUS.status === 'running'
                    ? 'border-guarded text-guarded'
                    : isDemo
                      ? 'border-line-strong text-mute'
                      : 'border-danger text-danger'
                }`}
              >
                {STATUS.status}
              </span>
            }
          />
          <Metric
            label="Equity (guarded)"
            value={
              <span className="tabular text-xl text-guarded">
                {METRICS.equityGuarded.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
            }
          />
          <Metric
            label="Equity (shadow)"
            value={
              <span className="tabular text-xl text-danger">
                {METRICS.equityShadow.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
            }
          />
          <Metric
            label="Open / day P&L"
            value={
              <span className="tabular text-xl text-white">
                {METRICS.openPositions} · {METRICS.dayPnl >= 0 ? '+' : ''}
                {METRICS.dayPnl.toFixed(0)}
              </span>
            }
          />
        </div>

        {veto && tab === 'live' ? (
          <div className="veto-pulse mb-4 rounded-[4px] border border-danger bg-danger-deep px-4 py-3 tabular text-sm">
            <span className="font-medium text-white">VETO</span>
            <span className="text-ink/90">
              {' '}
              - {latest.reason} · p_adj {latest.p_adj} {'<'} breakeven {latest.p_be} · anomaly{' '}
              {latest.anomaly}
              {latest.checks.length ? ` · ${latest.checks.join(', ')}` : ''}
            </span>
            {isDemo ? (
              <span className="ml-2 inline-block rounded-[4px] border border-danger/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-ink/80">
                demo
              </span>
            ) : null}
          </div>
        ) : null}

        {tab === 'live' ? (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
            <Panel className="lg:col-span-4" title="Overconfidence dial" badge={isDemo ? 'Demo' : undefined}>
              <div className="flex justify-center py-2">
                <ScaleDial
                  stated={latest?.confidence ?? METRICS.stated}
                  calibrated={Math.round((latest?.p_cal ?? 0.41) * 100)}
                  size={260}
                />
              </div>
              <div className="mt-2 h-36">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={BUCKET_GAPS}>
                    <CartesianGrid stroke="#222" vertical={false} />
                    <XAxis dataKey="bucket" tick={{ fill: '#A3A3A3', fontSize: 10 }} stroke="#333" />
                    <YAxis tick={{ fill: '#A3A3A3', fontSize: 10 }} stroke="#333" width={28} />
                    <Tooltip
                      contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 4 }}
                    />
                    <Bar dataKey="gap" name="Stated - hit rate" fill="#FFFFFF" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-xs text-mute">Bucket overconfidence gap (pts)</p>
            </Panel>

            <Panel className="lg:col-span-8" title="Equity: guarded vs shadow" badge={isDemo ? 'Demo' : undefined}>
              <p className="mb-2 text-[11px] uppercase tracking-wide text-mute">Illustrative demo curve · live paper results replace this</p>
              <EquityChart data={EQUITY} height={300} />
            </Panel>

            <Panel className="lg:col-span-5" title="Reliability diagram" badge={isDemo ? 'Demo' : undefined}>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                    <CartesianGrid stroke="#222" />
                    <XAxis
                      type="number"
                      dataKey="stated"
                      name="Stated"
                      domain={[45, 105]}
                      tick={{ fill: '#A3A3A3', fontSize: 11 }}
                      stroke="#333"
                    />
                    <YAxis
                      type="number"
                      dataKey="actual"
                      name="Actual"
                      domain={[0, 100]}
                      tick={{ fill: '#A3A3A3', fontSize: 11 }}
                      stroke="#333"
                      width={36}
                    />
                    <ZAxis type="number" dataKey="n" range={[60, 280]} />
                    <Tooltip
                      cursor={{ strokeDasharray: '3 3' }}
                      contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 4 }}
                    />
                    <Line
                      data={[
                        { stated: 50, actual: 50 },
                        { stated: 100, actual: 100 },
                      ]}
                      dataKey="actual"
                      stroke="#666"
                      strokeDasharray="4 4"
                      dot={false}
                      activeDot={false}
                      legendType="none"
                      isAnimationActive={false}
                    />
                    <Scatter data={RELIABILITY} fill="#FFFFFF" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </Panel>

            <Panel className="lg:col-span-7" title="Decision log" badge={isDemo ? 'Demo' : undefined}>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead className="text-mute">
                    <tr>
                      <th className="pb-2 font-medium">Time</th>
                      <th className="pb-2 font-medium">Sym</th>
                      <th className="pb-2 font-medium">Conf</th>
                      <th className="pb-2 font-medium">Decision</th>
                      <th className="pb-2 font-medium">Reason</th>
                      <th className="pb-2 font-medium">Anom</th>
                    </tr>
                  </thead>
                  <tbody>
                    {DECISIONS.map((d) => (
                      <tr key={d.id} className="border-t border-line/80">
                        <td className="tabular py-2.5 text-mute">
                          {new Date(d.ts).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </td>
                        <td className="py-2.5">{d.symbol.replace('USDT', '')}</td>
                        <td className="tabular py-2.5">{d.confidence}</td>
                        <td className="py-2.5">
                          <KindPill kind={d.kind} />
                        </td>
                        <td className="py-2.5 text-mute">{d.reason}</td>
                        <td className="tabular py-2.5">{d.anomaly.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>
        ) : null}

        {tab === 'attacks' ? (
          <div className="space-y-4">
            <Panel title="Attack Lab">
              <p className="mb-4 max-w-[60ch] text-sm text-mute">
                Attacks only change Trader inputs. The Inspector reference feed stays clean. Pick a
                scenario and attack, then compare G0 / G1 / G2A / G2.
              </p>
              <p className="mb-4 inline-block rounded-[4px] border border-line-strong px-2 py-0.5 text-[11px] uppercase tracking-wide text-mute">
                {sourceLabel(results)}
              </p>
              <div className="mb-5 flex flex-wrap gap-3">
                <label className="text-sm text-mute">
                  Scenario
                  <select
                    className="ml-2 rounded-[4px] border border-line-strong bg-elevated px-2 py-1.5 text-ink"
                    value={scenario}
                    onChange={(e) => setScenario(e.target.value)}
                  >
                    {results.scenarios.map((sid) => (
                      <option key={sid} value={sid}>
                        {sid}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm text-mute">
                  Attack
                  <select
                    className="ml-2 rounded-[4px] border border-line-strong bg-elevated px-2 py-1.5 text-ink"
                    value={attack}
                    onChange={(e) => setAttack(e.target.value)}
                  >
                    {results.attacks.map((a) => (
                      <option key={a} value={a}>
                        {a}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="grid gap-3 md:grid-cols-4">
                {gateCols.map((row, i) => {
                  const gate = GATES[i]
                  if (!row) {
                    return (
                      <div key={gate} className="rounded-[4px] border border-line p-4 text-mute">
                        {gate}: no row
                      </div>
                    )
                  }
                  return (
                    <div
                      key={gate}
                      className={`rounded-[4px] border p-4 ${
                        row.approved ? 'border-danger/50 bg-danger-deep/30' : 'border-guarded/40 bg-panel'
                      }`}
                    >
                      <div className="flex justify-between text-sm">
                        <span className="tabular text-mute">{gate}</span>
                        <span className={row.approved ? 'text-danger' : 'text-guarded'}>
                          {row.approved ? 'APPROVED' : 'VETO'}
                        </span>
                      </div>
                      <div className="mt-3 tabular text-3xl text-white">{row.confidence}</div>
                      <div className="mt-1 text-sm text-mute">{row.reason}</div>
                      <div className="mt-3 text-xs text-mute">
                        anomaly {Number(row.anomaly ?? 0).toFixed(2)} · true {row.true_result}
                      </div>
                      {row.checks_fired.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-1">
                          {row.checks_fired.map((c) => (
                            <span
                              key={c}
                              className="rounded-[4px] border border-line-strong px-2 py-0.5 tabular text-[11px]"
                            >
                              {c}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  )
                })}
              </div>
              {attack === 'A4' ? (
                <p className="mt-4 text-sm text-mute">
                  A4 is pure steering text aimed at a well-calibrated bucket. Compare G2A (anomaly
                  layer only) with G2 (ablation: text may lower confidence, never raise it).
                </p>
              ) : null}
            </Panel>
          </div>
        ) : null}

        {tab === 'results' ? (
          <Panel title="Harmful approval rate">
            <p className="mb-3 inline-block rounded-[4px] border border-line-strong px-2 py-0.5 text-[11px] uppercase tracking-wide text-mute">
              {sourceLabel(results)}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-left text-sm">
                <thead className="text-mute">
                  <tr>
                    <th className="pb-2 font-medium">Attack</th>
                    {GATES.map((g) => (
                      <th key={g} className="pb-2 font-medium">
                        {g}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.har.map((r) => (
                    <tr key={r.attack} className="border-t border-line">
                      <td className="py-2.5">{r.attack}</td>
                      {GATES.map((g) => (
                        <td key={g} className={`tabular py-2.5 ${g === 'G2' ? '' : 'text-mute'}`}>
                          {pct(r[g])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        ) : null}
      </main>
    </div>
  )
}

function Panel({
  title,
  children,
  className = '',
  badge,
}: {
  title: string
  children: React.ReactNode
  className?: string
  badge?: string
}) {
  return (
    <section className={`min-w-0 rounded-[4px] border border-line bg-panel p-4 md:p-5 ${className}`}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-medium text-mute">{title}</h2>
        {badge ? (
          <span className="rounded-[4px] border border-line-strong px-2 py-0.5 text-[10px] uppercase tracking-wide text-mute">
            {badge}
          </span>
        ) : null}
      </div>
      {children}
    </section>
  )
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-[4px] border border-line bg-panel px-3 py-3">
      <div className="text-[11px] uppercase tracking-wide text-mute">{label}</div>
      <div className="mt-1">{value}</div>
    </div>
  )
}

function KindPill({ kind }: { kind: string }) {
  const color =
    kind === 'veto'
      ? 'text-danger border-danger/50'
      : kind === 'approve'
        ? 'text-guarded border-guarded/50'
        : kind === 'shrink'
          ? 'text-ink border-line-strong'
          : 'text-mute border-line'
  return (
    <span className={`rounded-[4px] border px-1.5 py-0.5 text-[11px] uppercase tracking-wide ${color}`}>
      {kind}
    </span>
  )
}
