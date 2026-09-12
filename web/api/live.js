/**
 * The live bot feed for the website.
 *
 * The bot writes paper_log/live.json to the paper-log branch of a private repo every cycle.
 * The read token stays on the server, so the site can be public while the code is not.
 */
const REPO = process.env.GH_REPO || 'khalydmaina/tare'

export default async function handler(req, res) {
  const token = process.env.GH_TOKEN
  if (!token) return res.status(503).json({ error: 'GH_TOKEN is not set on this deployment' })
  try {
    const r = await fetch(
      `https://api.github.com/repos/${REPO}/contents/paper_log/live.json?ref=paper-log`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github.raw',
          'User-Agent': 'tare-site',
          'X-GitHub-Api-Version': '2022-11-28',
        },
      },
    )
    if (!r.ok) return res.status(r.status).json({ error: `github ${r.status}` })
    res.setHeader('Content-Type', 'application/json')
    res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=300')
    return res.status(200).send(await r.text())
  } catch (err) {
    return res.status(502).json({ error: String(err).slice(0, 200) })
  }
}
