#!/usr/bin/env python3
"""Capture observable behavior from a running service for behavioral contract extraction.

Usage:
    python capture_behavior.py --base-url http://localhost:8000 \
        --endpoints endpoints.json --output evidence.jsonl

Exit codes: 0=all captures succeeded, 1=one or more failed, 2=error.
"""
import argparse, json, sys, time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("Error: 'requests' package required. Install with: pip install requests", file=sys.stderr)
    sys.exit(2)

SENSITIVE_HEADER_KEYS = {"authorization", "x-api-key", "api-key", "x-auth-token",
                         "cookie", "set-cookie", "x-secret", "secret"}

def redact_headers(headers):
    """Redact sensitive header values."""
    redacted = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADER_KEYS:
            redacted[key] = "<REDACTED>"
        else:
            redacted[key] = value
    return redacted

def capture_endpoint(base_url, endpoint):
    """Send a request and capture the full response."""
    url = base_url + endpoint["path"]
    method = endpoint.get("method", "GET")
    headers = endpoint.get("headers", {})
    body = endpoint.get("body")

    # Redact secrets in request headers
    headers = redact_headers(headers)

    start = time.monotonic()
    try:
        resp = requests.request(method, url, headers=headers, json=body, timeout=10)
        elapsed_ms = (time.monotonic() - start) * 1000
        content_type = resp.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            response_body = resp.json()
        else:
            response_body = resp.text[:10000]  # cap at 10K chars

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "observe",
            "action": "capture_request",
            "result": "pass",
            "details": {
                "method": method,
                "path": endpoint["path"],
                "status_code": resp.status_code,
                "response_headers": redact_headers(dict(resp.headers)),
                "response_body": response_body,
                "elapsed_ms": round(elapsed_ms, 2),
            },
            "redacted": True,
        }
    except requests.exceptions.Timeout:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "observe",
            "action": "capture_request",
            "result": "fail",
            "details": {"method": method, "path": endpoint["path"],
                       "error": "Request timed out after 10s"},
            "redacted": True,
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "observe",
            "action": "capture_request",
            "result": "fail",
            "details": {"method": method, "path": endpoint["path"],
                       "error": f"Connection failed: {e.__class__.__name__}"},
            "redacted": True,
        }
    except Exception as e:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "observe",
            "action": "capture_request",
            "result": "fail",
            "details": {"method": method, "path": endpoint["path"],
                       "error": f"{e.__class__.__name__}: {str(e)[:200]}"},
            "redacted": True,
        }

def main():
    parser = argparse.ArgumentParser(description="Capture observable behavior")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--endpoints", required=True,
                        help="JSON file with endpoint definitions")
    parser.add_argument("--output", default="evidence.jsonl")
    args = parser.parse_args()

    try:
        with open(args.endpoints) as f:
            endpoints = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error reading endpoints file: {e}", file=sys.stderr)
        sys.exit(2)

    failures = 0
    with open(args.output, "w") as f:
        for ep in endpoints:
            entry = capture_endpoint(args.base_url, ep)
            f.write(json.dumps(entry) + "\n")
            status_icon = "✓" if entry["result"] == "pass" else "✗"
            print(f"  {status_icon} {ep.get('method','GET')} {ep['path']} → {entry['result']}")
            if entry["result"] == "fail":
                failures += 1

    print(f"\nCaptured {len(endpoints)} endpoints → {args.output} ({failures} failures)")
    sys.exit(0 if failures == 0 else 1)

if __name__ == "__main__":
    main()
