/**
 * The paper trading log and the results write-up, for judges and anyone checking the numbers.
 *
 *   /api/log                    the paper log summary
 *   /api/log?file=trades.csv
 *   /api/log?file=RESULTS.md    the measured results (docs/RESULTS.md on main)
 *
 * Read from the private repo with a server-side token, one fixed list of files, nothing else
 * reachable. Markdown goes out as text/plain: some browsers download text/markdown instead of
 * showing it.
 */
const REPO = process.env.GH_REPO || 'khalydmaina/tare'
const MD = 'text/plain; charset=utf-8'
const LOG = (name, type) => ({ path: `paper_log/${name}`, ref: 'paper-log', type })
const FILES = {
  'README.md': LOG('README.md', MD),
  'live.json': LOG('live.json', 'application/json'),
  'decisions.csv': LOG('decisions.csv', 'text/csv; charset=utf-8'),
  'trades.csv': LOG('trades.csv', 'text/csv; charset=utf-8'),
  'shadow_trades.csv': LOG('shadow_trades.csv', 'text/csv; charset=utf-8'),
  'equity.csv': LOG('equity.csv', 'text/csv; charset=utf-8'),
  'RESULTS.md': { path: 'docs/RESULTS.md', ref: 'main', type: MD },
}

export default async function handler(req, res) {
  const token = process.env.GH_TOKEN
  if (!token) return res.status(503).json({ error: 'GH_TOKEN is not set on this deployment' })
  const file = String(req.query.file || 'README.md')
  const entry = FILES[file]
  if (!entry) return res.status(404).json({ error: `unknown file`, available: Object.keys(FILES) })
  try {
    const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${entry.path}?ref=${entry.ref}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github.raw',
        'User-Agent': 'tare-site',
        'X-GitHub-Api-Version': '2022-11-28',
      },
    })
    if (!r.ok) return res.status(r.status).json({ error: `github ${r.status}` })
    res.setHeader('Content-Type', entry.type)
    res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=300')
    return res.status(200).send(await r.text())
  } catch (err) {
    return res.status(502).json({ error: String(err).slice(0, 200) })
  }
}
