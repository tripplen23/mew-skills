"""Fixture candidate server for http_diff_test.py.

Deliberately different from baseline_server.py in ways the harness must
catch: (1) the POST returns 201 with a body (spec-literal implementation,
ignoring the live-baseline's actual 204 — a regression Lesson 2 warns
about); (2) 404 detail wording differs. The harness must report these as
mismatches."""

import json

from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Lock

ITEMS = [
    {"id": 2, "name": "Bravo", "ts": "2026-08-01T10:00:00.123456"},
    {"id": 1, "name": "Alpha", "ts": "2026-08-01T10:00:00.123455"},
]
LOCK = Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/items":
            with LOCK:
                items = sorted(ITEMS, key=lambda i: i["name"])
            self._json(200, items)
        elif self.path.startswith("/items/"):
            raw = self.path.split("/")[-1]
            try:
                iid = int(raw)
            except ValueError:
                self._json(404, {"error": f"item {raw} missing"})
                return
            with LOCK:
                found = next((i for i in ITEMS if i["id"] == iid), None)
            if found:
                self._json(200, found)
            else:
                self._json(404, {"error": f"item {iid} missing"})  # wrong shape
        else:
            self._json(404, {"detail": "not found"})

    def do_POST(self):
        if self.path == "/items":
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            with LOCK:
                new = {
                    "id": len(ITEMS) + 1,
                    "name": payload.get("name", ""),
                    "ts": "2026-08-01T10:00:01.000000",
                }
                ITEMS.append(new)
            self._json(201, new)  # regression: baseline returns 204
        else:
            self._json(404, {"detail": "not found"})


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9002
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
