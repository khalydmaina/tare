/**
 * Plain names for the codes the attack suite and the Inspector write into their results, so no
 * visitor has to decode A4F, G2A or M2. Shared by the landing page and the Flight Recorder.
 */

export const ATTACKS: Record<string, { name: string; how: string }> = {
  clean: { name: 'No attack', how: 'The real setup and the real news, untouched.' },
  A1: {
    name: 'Prompt injection',
    how: 'Commands hidden inside a news item, telling the AI to take the trade.',
  },
  A2: {
    name: 'Fake consensus',
    how: 'A flood of near-identical hype posts from brand-new sources, faking a crowd.',
  },
  A3: {
    name: 'Candle forgery',
    how: 'The recent price chart the AI sees is rewritten into a textbook setup.',
  },
  A4: {
    name: 'Confidence steering',
    how: "Calm, believable text that nudges the AI's confidence up. Nothing is forged.",
  },
  A4F: {
    name: 'Steering + forgery',
    how: 'Confidence steering on top of a forged price chart.',
  },
  A5: {
    name: 'Adaptive attacker',
    how: 'An AI writes a fake headline, reads why it was blocked, and rewrites it, up to 6 tries.',
  },
}

export const GATE_NAMES: Record<string, { name: string; how: string }> = {
  G0: { name: 'No referee', how: "The AI's decision goes straight through at a fixed size." },
  G1: { name: 'Track record', how: 'Sized by how often the AI has been right at this confidence.' },
  G2A: {
    name: '+ Tampering checks',
    how: 'Track record, plus checks for hidden commands, fake crowds and forged prices.',
  },
  G2: {
    name: 'Full referee',
    how: 'All of the above, plus the AI is asked again with the news removed.',
  },
}

export const REASONS: Record<string, string> = {
  unguarded: 'Fixed 1% risk on every take. No questions asked.',
  unguarded_fixed_risk: 'Fixed 1% risk on every take. No questions asked.',
  approve: 'The record shows an edge at this confidence, so the trade is sized.',
  calibrated_edge: 'The record shows an edge at this confidence, so the trade is sized.',
  shrink: 'The record shows a thin edge, so the trade is sized down.',
  no_calibrated_edge: 'The record at this confidence does not beat breakeven. Size is zero.',
  probe_uncalibrated:
    'Nothing measured at this confidence yet, so the trade is exploration: a quarter of normal risk, two a day.',
  uncalibrated_no_probe_left: "Today's two exploration trades are already spent. Size is zero.",
  probe_needs_quiet_input:
    'Exploration only runs on untampered inputs, and the checks fired. Size is zero.',
  probe_no_room: 'No leverage headroom for an exploration trade. Size is zero.',
  input_anomaly: 'Tampering checks fired. Size is zero.',
  sentiment_driven_take: 'Asked again without the news, the AI skips. Size is zero.',
  edge_too_thin: 'The edge is too thin to size. Size is zero.',
  max_leverage: 'No leverage headroom left. Size is zero.',
  trader_skip: 'The AI skipped this setup.',
}

/** Inspector checks as they appear in checks_fired */
export const CHECKS: Record<string, string> = {
  S1: 'hidden commands in the news',
  S2: 'news mood spiked',
  S3: 'news contradicts the price',
  S4: 'crowd looks fake',
  C1: 'price disagrees with the second exchange',
  C2: 'last candle looks abnormal',
  C3: 'price feed stale',
  M1: 'confidence jumped',
  M2: 'only confident because of the news',
}

export const attackLabel = (id: string) =>
  id === 'clean' ? ATTACKS.clean.name : ATTACKS[id] ? `${id} · ${ATTACKS[id].name}` : id
export const gateLabel = (id: string) => (GATE_NAMES[id] ? GATE_NAMES[id].name : id)
export const reasonText = (code: string) => REASONS[code] ?? code.replace(/_/g, ' ')
export const checkText = (code: string) => (CHECKS[code] ? `${code} · ${CHECKS[code]}` : code)
