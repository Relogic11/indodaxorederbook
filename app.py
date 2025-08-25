from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
from requests.exceptions import RequestException, Timeout
from urllib.parse import urljoin

INDODAX_BASE = "https://indodax.com"

app = Flask(__name__, static_folder="static", static_url_path="/static")
# Allow cross-origin for API routes (useful when opening index.html via file://)
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.after_request
def add_no_cache_headers(response):
    # Prevent caching during development to always fetch the latest HTML/JS/API
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def http_get_json(path: str):
    url = urljoin(INDODAX_BASE + "/", path.lstrip("/"))
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Timeout:
        return {"error": True, "message": "Upstream request to Indodax timed out"}, 504
    except RequestException as e:
        status = e.response.status_code if getattr(e, "response", None) is not None else 502
        return {"error": True, "message": f"Upstream error: {str(e)}"}, status
    except ValueError:
        return {"error": True, "message": "Invalid JSON from upstream"}, 502


@app.route("/")
def root():
    # Serve the root-level index.html (created for this project)
    return send_from_directory(".", "index.html")


@app.route("/api/pairs")
def pairs():
    result = http_get_json("/api/pairs")
    # If http_get_json returned (dict, status) tuple on error, pass through
    if isinstance(result, tuple):
        data, status = result
        return jsonify(data), status
    # Flask must not return a raw list; wrap with jsonify
    return jsonify(result)


@app.route("/api/orderbook")
def orderbook():
    pair = request.args.get("pair", default="btcidr")
    # Defensive: allow alnum and underscore (e.g., 'btc_idr')
    if not pair.replace('_', '').isalnum():
        return jsonify({"error": True, "message": "Invalid pair"}), 400

    result = http_get_json(f"/api/depth/{pair}")

    # If http_get_json returned (dict, status) tuple on error, pass through
    if isinstance(result, tuple):
        data, status = result
        return jsonify(data), status

    # Normalize response structure
    buy = result.get("buy", [])
    sell = result.get("sell", [])

    # Ensure numeric sorting (buy: desc, sell: asc)
    try:
        buy_sorted = sorted(buy, key=lambda x: float(x[0]), reverse=True)
        sell_sorted = sorted(sell, key=lambda x: float(x[0]))
    except Exception:
        buy_sorted, sell_sorted = buy, sell

    return jsonify({
        "pair": pair,
        "buy": buy_sorted,
        "sell": sell_sorted
    })


@app.route("/api/server_time")
def server_time():
    return http_get_json("/api/server_time")


if __name__ == "__main__":
    # Run development server
    app.run(host="127.0.0.1", port=5000, debug=True)
