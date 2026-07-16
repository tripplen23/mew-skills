#!/usr/bin/env python3
"""Capture observable behavior from a running service for behavioral contract extraction.

Usage:
    python capture_behavior.py --base-url http://localhost:8000 --endpoints endpoints.json --output evidence.jsonl

This is a template — adapt the capture logic to your specific system.
"""
import argparse, json, sys, time, requests
from datetime import datetime, timezone

def capture_endpoint(base_url, endpoint):
    """Send a request and capture the full response."""
    url = base_url + endpoint["path"]
    method = endpoint.get("method", "GET")
    headers = endpoint.get("headers", {})
    body = endpoint.get("body")

    # Redact secrets
    for key in list(headers.keys()):
        if any(s in key.lower() for s in ["auth", "key", "token", "secret"]):
            headers[key] = "<REDACTED>"

    start = time.monotonic()
    try:
        resp = requests.request(method, url, headers=headers, json=body, timeout=10)
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "observe",
            "action": "capture_request",
            "result": "pass",
            "details": {
                "method": method,
                "path": endpoint["path"],
                "status_code": resp.status_code,
                "response_headers": dict(resp.headers),
                "response_body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
                "elapsed_ms": round(elapsed_ms, 2),
            },
            "redacted": True,
        }
    except Exception as e:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "observe",
            "action": "capture_request",
            "result": "fail",
            "details": {"method": method, "path": endpoint["path"], "error": str(e)},
            "redacted": True,
        }

def main():
    parser = argparse.ArgumentParser(description="Capture observable behavior")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--endpoints", required=True, help="JSON file with endpoint definitions")
    parser.add_argument("--output", default="evidence.jsonl")
    args = parser.parse_args()

    with open(args.endpoints) as f:
        endpoints = json.load(f)

    with open(args.output, "w") as f:
        for ep in endpoints:
            entry = capture_endpoint(args.base_url, ep)
            f.write(json.dumps(entry) + "\n")
            print(f"  {ep.get('method','GET')} {ep['path']} → {entry['result']}")

    print(f"\nCaptured {len(endpoints)} endpoints → {args.output}")

if __name__ == "__main__":
    main()
