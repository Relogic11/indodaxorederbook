from http.server import BaseHTTPRequestHandler
import json
import os
import time
import psycopg2
from urllib.parse import urlparse, parse_qs


def _get_db_url():
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise RuntimeError('DATABASE_URL env not set')
    if 'channel_binding=' in url:
        parts = url.split('?')
        if len(parts) == 2:
            base, qs = parts
            qitems = [kv for kv in qs.split('&') if not kv.startswith('channel_binding=')]
            url = base + ('?' + '&'.join(qitems) if qitems else '')
    return url


def _summarize(data_json):
    try:
        buys = data_json.get('buy') or []
        sells = data_json.get('sell') or []
        best_bid = max((float(b[0]) for b in buys if len(b) >= 1), default=None)
        best_ask = min((float(s[0]) for s in sells if len(s) >= 1), default=None)
        spread = (best_ask - best_bid) if (best_ask is not None and best_bid is not None) else None
        return best_bid, best_ask, spread
    except Exception:
        return None, None, None


class handler(BaseHTTPRequestHandler):
    def _send(self, code:int, data, content_type: str = "application/json"):
        body = data if isinstance(data, (bytes, bytearray)) else (json.dumps(data)).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            pair = (qs.get('pair', [None])[0] or '').strip()
            if not pair:
                return self._send(400, {"error": "missing pair"})

            now_ms = int(time.time() * 1000)
            seven_days = 7*24*60*60*1000
            to_ms = int(qs.get('to', [now_ms])[0])
            from_ms = int(qs.get('from', [max(0, to_ms - seven_days)])[0])
            limit = int(qs.get('limit', [1000])[0])
            if limit > 5000:
                limit = 5000

            db_url = _get_db_url()
            conn = psycopg2.connect(db_url)
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT ts_ms, data_json
                            FROM snapshots_raw
                            WHERE pair = %s AND ts_ms BETWEEN %s AND %s
                            ORDER BY ts_ms DESC
                            LIMIT %s
                            """,
                            (pair, from_ms, to_ms, limit)
                        )
                        rows = cur.fetchall()
                out_rows = []
                for ts_ms, data_json in rows:
                    if isinstance(data_json, str):
                        try:
                            data_json = json.loads(data_json)
                        except Exception:
                            data_json = {}
                    best_bid, best_ask, spread = _summarize(data_json)
                    out_rows.append({
                        'ts_ms': int(ts_ms),
                        'best_bid': best_bid,
                        'best_ask': best_ask,
                        'spread': spread,
                    })
                return self._send(200, {
                    'pair': pair,
                    'from': from_ms,
                    'to': to_ms,
                    'count': len(out_rows),
                    'rows': out_rows,
                })
            finally:
                conn.close()
        except Exception as e:
            return self._send(500, {"error": str(e)})
