#!/usr/bin/env python3
"""HTTP differential harness for API migrations.

diff_test.py compares stdin/stdout of CLI commands. This harness does the
same for HTTP APIs: replay an identical request sequence against the
executable-baseline oracle and the candidate, then compare status + body
after the contract's normalization rules.

Usage:
    python http_diff_test.py \
      --sequence cases.json \
      --baseline http://127.0.0.1:5000 \
      --candidate http://127.0.0.1:8080 \
      [--normalize timestamps] \
      [--output parity-report.json]

Sequence file format (cases.json):
{
  "properties": [
    {
      "id": "P001",
      "method": "GET",
      "path": "/api/people",
      "body": null,
      "status_only": false,
      "normalize": ["timestamps", "json_order"]
    }
  ]
}

Built-in normalizers:
  timestamps  - replace ISO-8601 UTC microsecond timestamps with <TS>
  json_order  - parse both bodies as JSON and compare as dicts
  status_only - compare status code only (e.g. framework-generated docs)

Exit code 0 = all properties matched, 1 = any mismatch. Prints a per-
property verdict table. Proven in two independent migration runs
(Flask+Connexion -> FastAPI and Flask+Connexion -> Rust axum) where the
pack's stdin/stdout diff_test.py could not verify HTTP endpoints.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}")


def normalize_timestamps(obj):
    if isinstance(obj, dict):
        return {k: normalize_timestamps(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_timestamps(v) for v in obj]
    if isinstance(obj, str) and TS_RE.fullmatch(obj):
        return "<TS>"
    return obj


def call(base: str, method: str, path: str, body) -> tuple[int, bytes]:
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def parse_body(raw: bytes):
    text = raw.decode(errors="replace")
    if not text.strip():
        return text
    try:
        return json.loads(text)
    except Exception:
        return text


def compare(case: dict, bs: int, bb, cs: int, cb) -> tuple[bool, str]:
    if bs != cs:
        return False, f"status {bs} != {cs}"
    if case.get("status_only"):
        return True, "status OK (body not contractual)"
    nb, nc = bb, cb
    if "timestamps" in case.get("normalize", []):
        nb, nc = normalize_timestamps(nb), normalize_timestamps(nc)
    if "json_order" in case.get("normalize", []):
        try:
            nb, nc = json.loads(json.dumps(nb, sort_keys=True)), json.loads(json.dumps(nc, sort_keys=True))
        except Exception:
            pass
    if nb == nc:
        return True, "body OK"
    return (
        False,
        f"body mismatch: base={json.dumps(nb, sort_keys=True)[:160]} "
        f"cand={json.dumps(nc, sort_keys=True)[:160]}",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="HTTP differential harness for API migrations")
    ap.add_argument("--sequence", required=True, help="cases.json sequence file")
    ap.add_argument("--baseline", required=True, help="baseline base URL")
    ap.add_argument("--candidate", required=True, help="candidate base URL")
    ap.add_argument("--output", help="optional parity-report.json output")
    args = ap.parse_args()

    with open(args.sequence) as f:
        seq = json.load(f)

    results = []
    fails = 0
    for case in seq["properties"]:
        pid, method, path, body = (
            case["id"],
            case["method"],
            case["path"],
            case.get("body"),
        )
        bs, raw_b = call(args.baseline, method, path, body)
        cs, raw_c = call(args.candidate, method, path, body)
        bb, cb = parse_body(raw_b), parse_body(raw_c)
        ok, note = compare(case, bs, bb, cs, cb)
        if not ok:
            fails += 1
        results.append(
            {"property_id": pid, "status": "pass" if ok else "mismatch", "note": note}
        )
        print(f"{'PASS' if ok else 'FAIL'} {pid} {method} {path}: {note}")

    total = len(seq["properties"])
    print(f"\n{total - fails}/{total} properties matched")
    if args.output:
        with open(args.output, "w") as f:
            json.dump(
                {
                    "total_properties": total,
                    "passed": total - fails,
                    "mismatches": fails,
                    "verdict": "pass" if fails == 0 else "fail",
                    "results": results,
                },
                f,
                indent=2,
            )
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
