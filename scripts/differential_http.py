#!/usr/bin/env python3
"""Differential HTTP comparison runner for Mew migration.

Starts baseline and candidate HTTP servers on random ports, replays captured
requests against both, and reports differences.

Usage:
  python3 scripts/differential_http.py \\
      --baseline "python3.11 app.py" \\
      --baseline-dir tests/fixtures/golden-task-2/baseline \\
      --candidate "cargo run -p axum-task-manager" \\
      --candidate-dir mew-core/crates/axum-task-manager \\
      --replay replay.jsonl \\
      --output parity-report.json

replay.jsonl format — one request per line:
  {"method":"GET","path":"/health","body":null,"expected_status":200,"expected_body":{"status":"ok"}}
  {"method":"POST","path":"/tasks","body":{"title":"Buy milk"},"expected_status":201,"expected_body_shape":{"id":"int","title":"str","done":false}}

Exit code: 0 on full pass, 1 on any mismatch.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def free_port() -> int:
    """Return an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(port: int, timeout: float = 10.0) -> bool:
    """Poll until the server at localhost:port responds to GET /health."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
            conn.request("GET", "/health")
            resp = conn.getresponse()
            resp.read()
            conn.close()
            if resp.status < 500:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def start_server(cmd: str, cwd: Path, port: int, name: str) -> subprocess.Popen:
    """Start a server process with PORT in its environment."""
    env = os.environ.copy()
    env["PORT"] = str(port)
    proc = subprocess.Popen(
        cmd,
        shell=True,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,
    )
    ready = wait_for_server(port)
    if not ready:
        proc.terminate()
        raise RuntimeError(f"{name} server did not respond on port {port} within timeout")
    print(f"✓ {name} server ready on port {port} (pid {proc.pid})")
    return proc


def stop_server(proc: subprocess.Popen, name: str):
    """Kill the server process group and wait."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=5)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait(timeout=2)
        except Exception:
            pass
    print(f"✗ {name} server stopped")


def http_request(host: str, port: int, method: str, path: str, body: dict | None) -> tuple[int, Any]:
    """Send an HTTP request and return (status_code, json_body)."""
    conn = http.client.HTTPConnection(host, port, timeout=5.0)
    body_bytes = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}
    conn.request(method, path, body=body_bytes, headers=headers)
    resp = conn.getresponse()
    resp_body = resp.read().decode()
    conn.close()
    try:
        return resp.status, json.loads(resp_body) if resp_body else None
    except json.JSONDecodeError:
        return resp.status, resp_body


def body_matches(actual: Any, expected: Any) -> bool:
    """Check if actual body matches expected, supporting shape-only matching.

    When expected uses string-typed values like "int" or "str", that field
    is shape-checked (type assertion) rather than value-checked.
    """
    if actual is None and expected is None:
        return True
    if actual is None or expected is None:
        return False
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for key, val in expected.items():
            if key not in actual:
                return False
            if isinstance(val, str) and val in ("int", "str", "float", "bool", "list", "dict"):
                type_map = {"int": int, "str": str, "float": float, "bool": bool, "list": list, "dict": dict}
                if not isinstance(actual[key], type_map[val]):
                    return False
            elif not body_matches(actual[key], val):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        return all(body_matches(a, e) for a, e in zip(actual, expected))
    return actual == expected


def replay_requests(port: int, replay_file: Path) -> list[dict]:
    """Replay requests from replay.jsonl against a server, return results."""
    results = []
    with open(replay_file) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            method = entry["method"]
            path = entry["path"]
            body = entry.get("body")
            expected_status = entry.get("expected_status")
            expected_body = entry.get("expected_body")
            expected_shape = entry.get("expected_body_shape")

            try:
                status, resp_body = http_request("127.0.0.1", port, method, path, body)
            except Exception as exc:
                results.append({
                    "lineno": lineno,
                    "method": method,
                    "path": path,
                    "error": str(exc),
                })
                continue

            ok = True
            issues = []
            if expected_status is not None and status != expected_status:
                ok = False
                issues.append(f"status {status} != {expected_status}")
            if expected_body is not None and not body_matches(resp_body, expected_body):
                ok = False
                issues.append("body mismatch")
            if expected_shape is not None and not body_matches(resp_body, expected_shape):
                ok = False
                issues.append("body shape mismatch")

            results.append({
                "lineno": lineno,
                "method": method,
                "path": path,
                "status": status,
                "body": resp_body,
                "expected_status": expected_status,
                "expected_body": expected_body,
                "passed": ok,
                "issues": issues,
            })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Differential HTTP comparison for Mew")
    parser.add_argument("--baseline", required=True, help="Command to start baseline server")
    parser.add_argument("--baseline-dir", required=True, help="Working directory for baseline")
    parser.add_argument("--candidate", required=True, help="Command to start candidate server")
    parser.add_argument("--candidate-dir", required=True, help="Working directory for candidate")
    parser.add_argument("--replay", required=True, help="Path to replay.jsonl with captured requests")
    parser.add_argument("--output", default="parity-report.json", help="Path for output parity report")
    parser.add_argument("--timeout", type=float, default=15.0, help="Server startup timeout (seconds)")
    args = parser.parse_args()

    replay_path = Path(args.replay)
    if not replay_path.exists():
        print(f"replay file not found: {args.replay}")
        return 2

    baseline_dir = Path(args.baseline_dir)
    candidate_dir = Path(args.candidate_dir)

    baseline_port = free_port()
    candidate_port = free_port()

    print(f"Baseline port: {baseline_port}, Candidate port: {candidate_port}")

    try:
        baseline_proc = start_server(args.baseline, baseline_dir, baseline_port, "Baseline")
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1

    try:
        candidate_proc = start_server(args.candidate, candidate_dir, candidate_port, "Candidate")
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        stop_server(baseline_proc, "Baseline")
        return 1

    try:
        print(f"\nReplaying {replay_path}...")
        baseline_results = replay_requests(baseline_port, replay_path)
        candidate_results = replay_requests(candidate_port, replay_path)

        passed = 0
        failed = 0
        results = []
        for br, cr in zip(baseline_results, candidate_results):
            entry = {
                "method": br["method"],
                "path": br["path"],
                "baseline_status": br.get("status"),
                "baseline_body": br.get("body"),
                "candidate_status": cr.get("status"),
                "candidate_body": cr.get("body"),
            }
            ok = True
            issues = []
            if br.get("error"):
                ok = False
                issues.append(f"baseline error: {br['error']}")
            if cr.get("error"):
                ok = False
                issues.append(f"candidate error: {cr['error']}")
            if not br.get("error") and not cr.get("error"):
                if br.get("status") != cr.get("status"):
                    ok = False
                    issues.append(f"status: {br['status']} vs {cr['status']}")
                if not body_matches(cr.get("body"), br.get("body")):
                    ok = False
                    issues.append("body mismatch")
            entry["passed"] = ok
            entry["issues"] = issues
            if ok:
                passed += 1
            else:
                failed += 1
            results.append(entry)

        report = {
            "run_id": "differential-http",
            "baseline_command": args.baseline,
            "candidate_command": args.candidate,
            "total_requests": len(results),
            "passed": passed,
            "failed": failed,
            "results": results,
        }

        output_path = Path(args.output)
        output_path.write_text(json.dumps(report, indent=2))
        print(f"\nReport written to {output_path}")
        print(f"Passed: {passed}/{len(results)}, Failed: {failed}/{len(results)}")

        return 1 if failed > 0 else 0

    finally:
        stop_server(candidate_proc, "Candidate")
        stop_server(baseline_proc, "Baseline")


if __name__ == "__main__":
    raise SystemExit(main())
