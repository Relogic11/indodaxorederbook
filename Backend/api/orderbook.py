from http.server import BaseHTTPRequestHandler
import json
import requests
from urllib.parse import urlparse, parse_qs

BASE_URL = "https://indodax.com/api/depth/"

class handler(BaseHTTPRequestHandler):
    def _send(self, code:int, data, content_type: str = "application/json"):
        body = data if isinstance(data, (bytes, bytearray)) else (json.dumps(data)).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "s-maxage=3, stale-while-revalidate=30")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            pair = (qs.get('pair', [None])[0] or '').strip()
            if not pair:
                return self._send(400, {"error": "missing pair"})

            url = BASE_URL + pair
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            data = r.json()

            # Ensure structure keys
            out = {
                'buy': data.get('buy') or [],
                'sell': data.get('sell') or [],
            }
            return self._send(200, out)
        except Exception as e:
            return self._send(502, {"error": str(e)})
