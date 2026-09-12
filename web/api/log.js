/**
 * The paper trading log, for judges and anyone checking the numbers.
 *
 *   /api/log            the summary README
 *   /api/log?file=trades.csv
 *
 * Same private branch as the live feed, one fixed list of files, nothing else reachable.
 */
const REPO = process.env.GH_REPO || 'khalydmaina/tare'
const FILES = {
  'README.md': 'text/markdown; charset=utf-8',
  'live.json': 'application/json',
  'decisions.csv': 'text/csv; charset=utf-8',
  'trades.csv': 'text/csv; charset=utf-8',
  'shadow_trades.csv': 'text/csv; charset=utf-8',
  'equity.csv': 'text/csv; charset=utf-8',
}

export default async function handler(req, res) {
  const token = process.env.GH_TOKEN
  if (!token) return res.status(503).json({ error: 'GH_TOKEN is not set on this deployment' })
  const file = String(req.query.file || 'README.md')
  if (!FILES[file]) return res.status(404).json({ error: `unknown file`, available: Object.keys(FILES) })
  try {
    const r = await fetch(`https://api.github.com/repos/${REPO}/contents/paper_log/${file}?ref=paper-log`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github.raw',
        'User-Agent': 'tare-site',
        'X-GitHub-Api-Version': '2022-11-28',
      },
    })
    if (!r.ok) return res.status(r.status).json({ error: `github ${r.status}` })
    res.setHeader('Content-Type', FILES[file])
    res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=300')
    return res.status(200).send(await r.text())
  } catch (err) {
    return res.status(502).json({ error: String(err).slice(0, 200) })
  }
}
