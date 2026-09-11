import { Link } from 'react-router-dom'
import { StippleField } from '../components/StippleField'
import { EQUITY, type AttackDemo } from '../data/demo'
import { sourceLabel, useResults } from '../data/results'
import './landing.css'

const SHOWN_GATES = [
  { id: 'G0', name: 'Unguarded' },
  { id: 'G1', name: 'Calibration' },
  { id: 'G2', name: 'Full gate' },
] as const

const REASONS: Record<string, string> = {
  unguarded: 'Fixed 1% risk on every take. No questions asked.',
  unguarded_fixed_risk: 'Fixed 1% risk on every take. No questions asked.',
  approve: 'The record shows an edge at this confidence, so the trade is sized.',
  calibrated_edge: 'The record shows an edge at this confidence, so the trade is sized.',
  shrink: 'The record shows a thin edge, so the trade is sized down.',
  no_calibrated_edge: 'The record at this confidence does not beat breakeven. Size is zero.',
  input_anomaly: 'Tampering checks fired. Size is zero.',
  sentiment_driven_take: 'Asked again without the news, the Trader skips. Size is zero.',
  edge_too_thin: 'The edge is too thin to size. Size is zero.',
  max_leverage: 'No leverage headroom left. Size is zero.',
}

/** Return and worst peak-to-trough drop of one book, from the same demo curve the recorder shows */
function bookStats(key: 'guarded' | 'shadow') {
  const values = EQUITY.map((p) => p[key])
  let peak = values[0]
  let drawdown = 0
  for (const v of values) {
    peak = Math.max(peak, v)
    drawdown = Math.max(drawdown, (peak - v) / peak)
  }
  return { ret: values[values.length - 1] / values[0] - 1, drawdown }
}

const signedPct = (x: number) => `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(1)}%`

/** One A4 scenario for the preview: prefer one where calibration alone approves and the full gate vetoes */
function pickA4Scenario(rows: AttackDemo[]) {
  const byScenario = new Map<string, AttackDemo[]>()
  for (const row of rows) {
    if (row.attack !== 'A4') continue
    byScenario.set(row.scenario_id, [...(byScenario.get(row.scenario_id) ?? []), row])
  }
  const groups = [...byScenario.values()]
  const at = (group: AttackDemo[], gate: string) => group.find((r) => r.gate_config === gate)
  const showcase = groups.find((g) => at(g, 'G1')?.approved === true && at(g, 'G2')?.approved === false)
  return { rows: showcase ?? groups[0] ?? [], showsHole: showcase !== undefined }
}

export function Landing() {
  const results = useResults()
  const guarded = bookStats('guarded')
  const shadow = bookStats('shadow')
  const a4 = pickA4Scenario(results.rows)

  return (
    <div className="lp" id="top">
      <nav className="lp-nav" aria-label="Primary">
        <a className="lp-brand" href="#top">
          tare
        </a>
        <span className="lp-meta">Bitget AI · Genesis S2</span>
        <Link className="lp-ghost" to="/app">
          Enter
        </Link>
      </nav>

      <header className="lp-hero">
        <StippleField className="lp-field" density={700} maxR={2.2} />
        <div className="lp-halftone" aria-hidden="true" />
        <div className="lp-veil" aria-hidden="true" />
        <div className="lp-hero-copy">
          <h1 className="lp-title">tare</h1>
          <p className="lp-tag">Zero the confidence. Weigh the record.</p>
        </div>
        <a className="lp-scroll" href="#hook">
          Scroll to be briefed
        </a>
      </header>

      <main>
        <section className="lp-block" id="hook">
          <p className="lp-kicker">01 · Hook</p>
          <p className="lp-quote">
            This AI trader is <em>90%</em> sure. Historically, when it says 90%, it’s right{' '}
            <span className="lp-num">41%</span> of the time.
          </p>
          <p className="lp-note">
            <span className="lp-chip">Illustrative</span>
            The measured record replaces these numbers after the real model run.
          </p>
        </section>

        <section className="lp-block" id="argument">
          <p className="lp-kicker">02 · Shared blind spots</p>
          <h2>A second model will fail at the same moment.</h2>
          <p className="lp-lead">
            Another LLM reviewing the first shares the same blind spots. When the trader is fooled, the
            peer reviewer tends to fail with it. Tare never asks a model to grade a model. It asks the
            record.
          </p>
        </section>

        <section className="lp-block" id="how">
          <p className="lp-kicker">03 · How it works</p>
          <h2>Gross in. Net out.</h2>
          <p className="lp-quiet">
            Stated confidence is overweight. The Inspector subtracts what the model cannot prove.
          </p>
          <div className="lp-flow">
            <div className="lp-step">
              <div className="lp-step-n">01</div>
              <h3>Trader</h3>
              <p>Market structure finds a setup. An LLM says take or skip, and states P(TP before SL).</p>
            </div>
            <div className="lp-step">
              <div className="lp-step-n">02</div>
              <h3>Inspector</h3>
              <p>Non-LLM gate. Calibration, independent sensors, hard limits the model cannot edit.</p>
            </div>
            <div className="lp-step">
              <div className="lp-step-n">03</div>
              <h3>Shadow</h3>
              <p>Unguarded book. What would have happened if the brakes stayed silent.</p>
            </div>
            <div className="lp-step">
              <div className="lp-step-n">04</div>
              <h3>Recorder</h3>
              <p>Every proposal, veto, and counterfactual is logged. Evidence, not vibes.</p>
            </div>
          </div>
        </section>

        <section className="lp-block" id="books">
          <p className="lp-kicker">04 · Proof</p>
          <h2>Guarded green. Unguarded red.</h2>
          <p className="lp-quiet">
            Same setups, same fills. One book lets the Inspector size or veto every trade; the shadow
            book takes them all at full size.
          </p>
          <div className="lp-books">
            <div className="lp-book is-guarded">
              <div className="lp-book-label">Guarded · worst drop</div>
              <div className="lp-book-value">{signedPct(-guarded.drawdown)}</div>
              <p>Ends {signedPct(guarded.ret)}. The book that is allowed to exist.</p>
            </div>
            <div className="lp-book is-shadow">
              <div className="lp-book-label">Shadow (unguarded) · worst drop</div>
              <div className="lp-book-value">{signedPct(-shadow.drawdown)}</div>
              <p>Ends {signedPct(shadow.ret)}. The cost of believing the model’s stated confidence.</p>
            </div>
          </div>
          <p className="lp-note">
            <span className="lp-chip">Illustrative</span>
            The same demo curve as the recorder’s Live tab. The live paper record replaces it.
          </p>
        </section>

        <section className="lp-block" id="lab">
          <p className="lp-kicker">05 · Attack Lab</p>
          <h2>A4 is built to beat calibration-only.</h2>
          <p className="lp-quiet">
            Planted news steers the Trader to a believable confidence, one its record says it usually
            hits. Attacks change the Trader’s inputs only; the Inspector’s second price feed stays clean.{' '}
            {a4.showsHole
              ? 'In this scenario calibration alone lets it through, and the full gate stops it.'
              : 'Open the Attack Lab to see which gate stops it in each scenario.'}
          </p>
          <div className="lp-gates">
            {SHOWN_GATES.map(({ id, name }) => {
              const row = a4.rows.find((r) => r.gate_config === id)
              if (!row) {
                return (
                  <div key={id} className="lp-gate">
                    <div className="lp-gate-id">
                      {id} · {name}
                    </div>
                    <p>No result in this run.</p>
                  </div>
                )
              }
              return (
                <div key={id} className={`lp-gate ${row.approved ? 'is-fail' : 'is-pass'}`}>
                  <div className="lp-gate-id">
                    {id} · {name}
                  </div>
                  <div className="lp-verdict">{row.approved ? 'Approved' : 'Veto'}</div>
                  <p>{REASONS[row.reason] ?? row.reason}</p>
                  {row.checks_fired.length > 0 ? (
                    <div className="lp-checks">
                      {row.checks_fired.map((check) => (
                        <span key={check} className="lp-chip">
                          {check}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <div className="lp-gate-meta">Trade outcome · {row.true_result}</div>
                </div>
              )
            })}
          </div>
          <div className="lp-row">
            <span className="lp-chip">{sourceLabel(results)}</span>
            <Link className="lp-textlink" to="/app?tab=attacks">
              Open the Attack Lab →
            </Link>
          </div>
        </section>

        <section className="lp-block" id="about">
          <p className="lp-kicker">06 · What this is</p>
          <div className="lp-cards">
            <div className="lp-card">
              <div className="lp-card-id">GROSS</div>
              <h3>Stated confidence</h3>
              <p>The model’s P(TP before SL). A claim. Often overweight.</p>
            </div>
            <div className="lp-card">
              <div className="lp-card-id">TARE</div>
              <h3>Inspector correction</h3>
              <p>Historical hit rate, independent sensors, sealed limits.</p>
            </div>
            <div className="lp-card">
              <div className="lp-card-id">NET</div>
              <h3>Calibrated p</h3>
              <p>What is allowed to pass the gate. The number that may trade.</p>
            </div>
          </div>
        </section>
      </main>

      <section className="lp-portal" id="enter">
        <StippleField className="lp-field" density={900} maxR={1.8} />
        <div className="lp-portal-inner">
          <p className="lp-kicker">End of brief</p>
          <h2 className="lp-portal-title">Enter the recorder.</h2>
          <p className="lp-portal-sub">The product is the Flight Recorder. The page was the argument.</p>
          <Link className="lp-enter" to="/app">
            <span className="lp-dot" aria-hidden="true" />
            Enter
          </Link>
          <div className="lp-portal-links">
            <Link to="/app?tab=attacks">Attack Lab</Link>
            <span aria-hidden="true">·</span>
            <Link to="/app?tab=results">Results</Link>
          </div>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="lp-cols">
          <div>
            <h4>System</h4>
            <a href="#how">Trader</a>
            <a href="#how">Inspector</a>
            <a href="#how">Shadow book</a>
            <a href="#how">Flight Recorder</a>
          </div>
          <div>
            <h4>Evidence</h4>
            <a href="#books">Guarded vs shadow</a>
            <Link to="/app?tab=attacks">Attack Lab</Link>
            <Link to="/app?tab=results">Results</Link>
            <span>Attacks A1 to A5</span>
          </div>
          <div>
            <h4>Record</h4>
            <span>limits_hash sealed</span>
            <span>Paper trading only</span>
            <span>SQLite flight log</span>
          </div>
          <div>
            <h4>Enter</h4>
            <Link to="/app">Flight Recorder</Link>
            <a href="#top">Back to top</a>
          </div>
        </div>
        <div className="lp-legal">tare · brand kit 1.1 · not another LLM judge</div>
      </footer>
    </div>
  )
}
