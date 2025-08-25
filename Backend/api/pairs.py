from http.server import BaseHTTPRequestHandler
import json
import requests

INDODAX_PAIRS_URL = "https://indodax.com/api/pairs"

class handler(BaseHTTPRequestHandler):
    def _send(self, code:int, data, content_type: str = "application/json"):
        body = data if isinstance(data, (bytes, bytearray)) else (json.dumps(data)).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "s-maxage=5, stale-while-revalidate=30")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            resp = requests.get(INDODAX_PAIRS_URL, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            self._send(200, data)
        except Exception as e:
            self._send(502, {"error": str(e)})
