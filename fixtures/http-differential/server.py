#!/usr/bin/env python3
"""Tiny HTTP server fixture for scripts/differential_http.py.

Reads PORT from the environment and serves deterministic JSON responses.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        elif self.path == "/item":
            self._json(200, {"id": 1, "name": "demo"})
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, _format, *_args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(os.environ["PORT"])), Handler).serve_forever()
