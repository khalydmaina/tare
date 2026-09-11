import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, Scales, ShieldCheck, Lightning } from '@phosphor-icons/react'
import { Link } from 'react-router-dom'
import { Nav } from '../components/Nav'
import { ScaleDial } from '../components/ScaleDial'
import { EquityChart } from '../components/EquityChart'
import { EQUITY, METRICS } from '../data/demo'
import { GATES, pct, sourceLabel, useResults } from '../data/results'

const fade = (delay = 0) => ({
  initial: { opacity: 0, y: 18 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, amount: 0.25 },
  transition: { duration: 0.55, delay, ease: [0.16, 1, 0.3, 1] as const },
})

export function Landing() {
  const reduce = useReducedMotion()
  const results = useResults()
  const firstA4 = results.rows.find((r) => r.attack === 'A4')
  const a4 = GATES.map((g) =>
    results.rows.find(
      (r) => r.attack === 'A4' && r.gate_config === g && r.scenario_id === firstA4?.scenario_id,
    ),
  )

  return (
    <div className="relative min-h-[100dvh] bg-canvas text-ink">
      <div className="tare-grain" aria-hidden />
      <Nav />

      {/* HERO */}
      <section className="relative overflow-hidden border-b border-line">
        <div className="pointer-events-none absolute inset-0">
          <img
            src="/brand/hero-atmosphere.jpg"
            alt=""
            className="h-full w-full object-cover opacity-[0.28]"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-canvas via-canvas/90 to-canvas/40" />
          <div className="absolute inset-0 bg-gradient-to-t from-canvas via-transparent to-canvas/50" />
        </div>
        <div className="relative mx-auto grid max-w-[1280px] items-center gap-10 px-4 pb-16 pt-10 md:grid-cols-12 md:px-6 md:pb-20 md:pt-14">
          <div className="md:col-span-6 lg:col-span-6">
            <motion.p
              className="mb-4 text-sm text-mute"
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              Bitget AI × Crypto · Agentic Trading
            </motion.p>
            <motion.h1
              className="tare-wordmark max-w-[14ch] text-[clamp(2.6rem,6vw,4.4rem)] leading-[1.02] text-balance text-white"
              initial={reduce ? false : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            >
              Zero the confidence. Weigh the record.
            </motion.h1>
            <motion.p
              className="mt-5 max-w-[36ch] text-base leading-relaxed text-mute md:text-lg"
              initial={reduce ? false : { opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08, duration: 0.55 }}
            >
              An AI trader with brakes that tighten where the model has proven it cannot be trusted.
            </motion.p>
            <motion.div
              className="mt-8 flex flex-wrap items-center gap-3"
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.15 }}
            >
              <Link
                to="/app"
                className="inline-flex items-center gap-2 rounded-[4px] bg-white px-5 py-3 text-sm font-semibold text-canvas transition hover:bg-ink active:scale-[0.98]"
              >
                Open Flight Recorder
                <ArrowRight size={16} weight="bold" />
              </Link>
              <a
                href="#attacks"
                className="inline-flex items-center gap-2 rounded-[4px] border border-line-strong px-5 py-3 text-sm text-ink transition hover:border-ink/50"
              >
                See Attack Lab
              </a>
            </motion.div>
          </div>

          <div className="flex justify-center md:col-span-6 lg:col-span-6">
            <motion.div
              className="rounded-[4px] border border-line bg-panel/80 p-6 shadow-[0_0_0_1px_rgba(255,255,255,0.02)]"
              initial={reduce ? false : { opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.12, duration: 0.55 }}
            >
              <ScaleDial
                stated={METRICS.stated}
                calibrated={METRICS.calibrated}
                label="Illustrative: when it says 90%, history says 41%. Gross vs net after tare."
              />
            </motion.div>
          </div>
        </div>
      </section>

      {/* METAPHOR STRIP */}
      <section className="border-b border-line bg-panel">
        <div className="mx-auto grid max-w-[1280px] grid-cols-1 divide-y divide-line md:grid-cols-3 md:divide-x md:divide-y-0">
          {[
            { k: 'Gross', v: 'Stated confidence', d: 'What the LLM claims' },
            { k: 'Tare', v: 'Inspector correction', d: 'Calibration + anomaly + limits' },
            { k: 'Net', v: 'Calibrated probability', d: 'What you actually size on' },
          ].map((row) => (
            <div key={row.k} className="px-6 py-8">
              <div className="tare-wordmark text-3xl text-white">{row.k}</div>
              <div className="mt-2 text-sm font-medium text-ink">{row.v}</div>
              <div className="mt-1 text-sm text-mute">{row.d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* HOW */}
      <section id="how" className="border-b border-line">
        <div className="mx-auto max-w-[1280px] px-4 py-16 md:px-6 md:py-24">
          <motion.h2 className="max-w-[18ch] text-3xl font-semibold tracking-tight text-white md:text-4xl" {...fade()}>
            A second LLM shares blind spots. Evidence does not.
          </motion.h2>
          <motion.p className="mt-4 max-w-[52ch] text-mute" {...fade(0.05)}>
            Setups come from market structure. An LLM proposes take or skip. A non-LLM Inspector
            sizes or vetoes using the record, an independent feed, and sealed risk limits.
          </motion.p>

          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {[
              {
                icon: Scales,
                title: 'Trader proposes',
                body: 'SMC finds the setup. The model states confidence as P(TP before SL).',
              },
              {
                icon: ShieldCheck,
                title: 'Inspector weighs',
                body: 'Calibration matrix, cross-venue data, anomaly sensors. No peer model.',
              },
              {
                icon: Lightning,
                title: 'Shadow remembers',
                body: 'Every take is also booked unguarded. Green vs red is always computable.',
              },
            ].map((card, i) => (
              <motion.div
                key={card.title}
                className="rounded-[4px] border border-line bg-panel p-6"
                {...fade(0.06 * i)}
              >
                <card.icon size={28} className="text-white" weight="regular" />
                <h3 className="mt-4 text-lg font-semibold text-white">{card.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-mute">{card.body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* PROOF */}
      <section id="proof" className="border-b border-line bg-panel">
        <div className="mx-auto max-w-[1280px] px-4 py-16 md:px-6 md:py-24">
          <motion.h2 className="text-3xl font-semibold tracking-tight text-white md:text-4xl" {...fade()}>
            Guarded green. Shadow red.
          </motion.h2>
          <motion.p className="mt-3 max-w-[48ch] text-mute" {...fade(0.05)}>
            Same fills. Same market. One book with brakes, one without. The gap is the product.
          </motion.p>
          <motion.div
            className="mt-10 rounded-[4px] border border-line bg-canvas p-3 md:p-5"
            {...fade(0.08)}
          >
            <p className="mb-2 text-[11px] uppercase tracking-wide text-mute">Illustrative demo curve · live paper results replace this</p>
            <EquityChart data={EQUITY} height={320} />
          </motion.div>
        </div>
      </section>

      {/* ATTACK LAB PREVIEW */}
      <section id="attacks" className="border-b border-line">
        <div className="mx-auto max-w-[1280px] px-4 py-16 md:px-6 md:py-24">
          <motion.h2 className="text-3xl font-semibold tracking-tight text-white md:text-4xl" {...fade()}>
            A4 beats calibration. Ablation closes the hole.
          </motion.h2>
          <motion.p className="mt-3 max-w-[52ch] text-mute" {...fade(0.05)}>
            Confidence steering aims for a believable, well-calibrated bucket instead of 95%, so
            calibration alone approves the loss. G2 re-asks the Trader with the news stripped out:
            text can talk it out of a trade, never into one.
          </motion.p>

          <div className="mt-10 grid gap-3 md:grid-cols-4">
            {a4.map((row) =>
              row ? (
                <motion.div
                  key={row.gate_config}
                  className={`rounded-[4px] border p-5 ${
                    row.approved
                      ? 'border-danger/40 bg-danger-deep/40'
                      : 'border-guarded/40 bg-panel'
                  }`}
                  {...fade()}
                >
                  <div className="flex items-center justify-between">
                    <span className="tabular text-sm text-mute">{row.gate_config}</span>
                    <span
                      className={`tabular text-xs font-medium uppercase tracking-wide ${
                        row.approved ? 'text-danger' : 'text-guarded'
                      }`}
                    >
                      {row.approved ? 'Approved' : 'Veto'}
                    </span>
                  </div>
                  <div className="mt-4 tabular text-3xl text-white">{row.confidence}%</div>
                  <div className="mt-1 text-sm text-mute">{row.reason}</div>
                  {row.checks_fired.length > 0 ? (
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {row.checks_fired.map((c) => (
                        <span
                          key={c}
                          className="rounded-[4px] border border-line-strong px-2 py-0.5 tabular text-[11px] text-ink"
                        >
                          {c}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="mt-4 text-[11px] text-mute">No anomaly chips</div>
                  )}
                </motion.div>
              ) : null,
            )}
          </div>

          <p className="mt-6 text-[11px] uppercase tracking-wide text-mute">{sourceLabel(results)}</p>
          <motion.div className="mt-3 overflow-x-auto rounded-[4px] border border-line" {...fade(0.1)}>
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead className="bg-panel text-mute">
                <tr>
                  <th className="px-4 py-3 font-medium">Attack</th>
                  {GATES.map((g) => (
                    <th key={g} className="px-4 py-3 font-medium">
                      {g} HAR
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {results.har.map((r) => (
                  <tr key={r.attack} className="border-t border-line">
                    <td className="px-4 py-3 text-ink">{r.attack}</td>
                    {GATES.map((g) => (
                      <td key={g} className={`tabular px-4 py-3 ${g === 'G2' ? 'text-ink' : 'text-mute'}`}>
                        {pct(r[g])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </motion.div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-panel">
        <div className="mx-auto flex max-w-[1280px] flex-col items-start justify-between gap-6 px-4 py-16 md:flex-row md:items-center md:px-6 md:py-20">
          <div>
            <h2 className="tare-wordmark text-3xl text-white md:text-4xl">Weigh it live.</h2>
            <p className="mt-2 max-w-[40ch] text-mute">
              Flight Recorder: dial, veto feed, equity curves, Attack Lab.
            </p>
          </div>
          <Link
            to="/app"
            className="inline-flex items-center gap-2 rounded-[4px] bg-white px-5 py-3 text-sm font-semibold text-canvas transition hover:bg-ink active:scale-[0.98]"
          >
            Enter Flight Recorder
            <ArrowRight size={16} weight="bold" />
          </Link>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1280px] flex-col gap-2 px-4 py-8 text-sm text-mute md:flex-row md:items-center md:justify-between md:px-6">
          <span className="tare-wordmark text-base text-white">tare</span>
          <span>Color is a verdict. Green survived the gate. Red did not.</span>
        </div>
      </footer>
    </div>
  )
}
