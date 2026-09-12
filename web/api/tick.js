/**
 * The 15-minute trigger.
 *
 * GitHub fires roughly one in twelve of its own scheduled runs on this account, and a setup
 * only exists on the newest closed candle, so a missed cycle is a missed trade. An outside
 * scheduler calls this every 15 minutes; it starts a bot run unless one already started
 * inside the current candle, so a double call costs nothing.
 */
const REPO = process.env.GH_REPO || 'khalydmaina/tare'
const WORKFLOW = 'live-bot.yml'
const SLOT_MS = 15 * 60 * 1000

export default async function handler(req, res) {
  const token = process.env.GH_TOKEN
  const secret = process.env.TICK_SECRET
  if (!token || !secret) return res.status(503).json({ error: 'GH_TOKEN and TICK_SECRET must be set' })
  const key = req.query.key || req.headers['x-tick-key']
  if (key !== secret) return res.status(403).json({ error: 'bad key' })

  const gh = (path, init = {}) =>
    fetch(`https://api.github.com/repos/${REPO}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'User-Agent': 'tare-tick',
        'X-GitHub-Api-Version': '2022-11-28',
        ...(init.headers || {}),
      },
    })

  try {
    const slotStart = Math.floor(Date.now() / SLOT_MS) * SLOT_MS
    const recent = await gh(`/actions/workflows/${WORKFLOW}/runs?per_page=1`)
    if (recent.ok) {
      const last = (await recent.json()).workflow_runs?.[0]
      if (last && Date.parse(last.created_at) >= slotStart) {
        return res.status(200).json({ dispatched: false, reason: 'this candle already has a run', run: last.id })
      }
    }
    const fired = await gh(`/actions/workflows/${WORKFLOW}/dispatches`, {
      method: 'POST',
      body: JSON.stringify({ ref: 'main' }),
      headers: { 'Content-Type': 'application/json' },
    })
    if (fired.status !== 204) {
      const body = (await fired.text()).slice(0, 200)
      return res.status(502).json({ dispatched: false, error: `github ${fired.status} ${body}` })
    }
    return res.status(200).json({ dispatched: true, at: new Date().toISOString() })
  } catch (err) {
    return res.status(502).json({ error: String(err).slice(0, 200) })
  }
}
