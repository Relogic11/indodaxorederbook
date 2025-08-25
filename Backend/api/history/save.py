from http.server import BaseHTTPRequestHandler
import json
import os
import time
import psycopg2
from urllib.parse import urlparse


def _get_db_url():
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise RuntimeError('DATABASE_URL env not set')
    # Some drivers may not like channel_binding param; strip if present (safe)
    if 'channel_binding=' in url:
        # remove '&channel_binding=...'
        parts = url.split('?')
        if len(parts) == 2:
            base, qs = parts
            qitems = [kv for kv in qs.split('&') if not kv.startswith('channel_binding=')]
            url = base + ('?' + '&'.join(qitems) if qitems else '')
    return url

class handler(BaseHTTPRequestHandler):
    def _send(self, code:int, data, content_type: str = "application/json"):
        body = data if isinstance(data, (bytes, bytearray)) else (json.dumps(data)).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # Basic CORS (optional; same-origin wont need this)
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            raw = self.rfile.read(length) if length > 0 else b''
            payload = json.loads(raw.decode('utf-8') or '{}')

            pair = (payload.get('pair') or '').strip()
            ts_ms = int(payload.get('ts_ms') or 0)
            buy = payload.get('buy') or []
            sell = payload.get('sell') or []
            if not pair or ts_ms <= 0:
                return self._send(400, {"error": "invalid payload: require pair, ts_ms"})

            db_url = _get_db_url()
            conn = psycopg2.connect(db_url)
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO snapshots_raw (pair, ts_ms, data_json)
                            VALUES (%s, %s, %s::jsonb)
                            """,
                            (pair, ts_ms, json.dumps({'buy': buy, 'sell': sell}))
                        )
                        # retention 7 days for this pair
                        cutoff = int(time.time() * 1000) - 7*24*60*60*1000
                        cur.execute(
                            "DELETE FROM snapshots_raw WHERE pair = %s AND ts_ms < %s",
                            (pair, cutoff)
                        )
                # success
                return self._send(200, {"ok": True})
            finally:
                conn.close()
        except Exception as e:
            return self._send(500, {"error": str(e)})
