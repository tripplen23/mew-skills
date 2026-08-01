"""Fixture baseline server for http_diff_test.py.

A deliberately simple spec-first service: GET /items returns a list sorted
by name; GET /items/{id} returns 200 or 404; POST /items returns 204
(actual behavior — the fixture spec would declare 201, mirroring the
people-api case that motivated Lesson 2: probe live behavior, the running
server is the oracle, not the spec)."""

import json
from datetime import datetime, timezone
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
                self._json(
                    404,
                    {
                        "type": "about:blank",
                        "title": "Not Found",
                        "detail": f"Item with id {raw} not found",
                        "status": 404,
                    },
                )
                return
            with LOCK:
                found = next((i for i in ITEMS if i["id"] == iid), None)
            if found:
                self._json(200, found)
            else:
                self._json(
                    404,
                    {
                        "type": "about:blank",
                        "title": "Not Found",
                        "detail": f"Item with id {iid} not found",
                        "status": 404,
                    },
                )
        else:
            self._json(404, {"detail": "not found"})

    def do_POST(self):
        if self.path == "/items":
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            with LOCK:
                ITEMS.append(
                    {
                        "id": len(ITEMS) + 1,
                        "name": payload.get("name", ""),
                        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f"),
                    }
                )
            # Actual behavior: 204 empty, NOT the 201 the spec would declare.
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._json(404, {"detail": "not found"})


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9001
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
