export default async function handler(req, res) {
  const pairRaw = (req.query.pair ?? '').toString();
  if (!pairRaw) return res.status(400).json({ error: true, message: 'missing pair' });
  const pair = pairRaw; // pass through (supports 'btcidr' or 'btc_idr')
  try {
    const upstream = await fetch(`https://indodax.com/api/depth/${encodeURIComponent(pair)}`, {
      headers: { 'accept': 'application/json' }
    });
    if (!upstream.ok) {
      return res.status(upstream.status).json({ error: true, message: `Upstream ${upstream.status}` });
    }
    const data = await upstream.json();
    res.setHeader('Cache-Control', 's-maxage=5, stale-while-revalidate=30');
    res.setHeader('Access-Control-Allow-Origin', '*');
    return res.status(200).json(data);
  } catch (e) {
    return res.status(502).json({ error: true, message: e?.message || String(e) });
  }
}
