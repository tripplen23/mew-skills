#!/usr/bin/env python3
"""Differential HTTP comparison runner for Mew migration.

Starts baseline and candidate HTTP servers on random ports, replays captured
requests against both, and emits a schema-shaped parity report.

Usage:
  python3 scripts/differential_http.py \
      --run-id 20260730-120000-abc1234 \
      --baseline "python3 app.py" \
      --baseline-dir tests/fixtures/golden-task-2/baseline \
      --candidate "cargo run -p axum-task-manager" \
      --candidate-dir mew-core/crates/axum-task-manager \
      --replay replay.jsonl \
      --output parity-report.json

replay.jsonl format — one request per line:
  {"property_id":"P001","method":"GET","path":"/health","expected_status":200,"expected_body":{"status":"ok"}}
  {"property_id":"P002","method":"POST","path":"/tasks","body":{"title":"Buy milk"},"expected_status":201,"expected_body_shape":{"id":"int","title":"str","done":false}}

Exit code: 0 on full pass, 1 on any mismatch, 2 on usage/config errors.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

SHAPE_TYPES = {
    "int": int,
    "str": str,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
}


def free_port() -> int:
    """Return an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(port: int, ready_path: str, timeout: float) -> bool:
    """Poll until the server at localhost:port responds to the readiness path."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
            conn.request("GET", ready_path)
            resp = conn.getresponse()
            resp.read()
            conn.close()
            if resp.status < 500:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def start_server(cmd: str, cwd: Path, port: int, name: str, ready_path: str, timeout: float) -> subprocess.Popen:
    """Start a server process with PORT in its environment."""
    env = os.environ.copy()
    env["PORT"] = str(port)
    proc = subprocess.Popen(
        cmd,
        shell=True,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    if not wait_for_server(port, ready_path, timeout):
        stop_server(proc, name)
        raise RuntimeError(f"{name} server did not respond on port {port} path {ready_path!r} within timeout")
    print(f"✓ {name} server ready on port {port} (pid {proc.pid})")
    return proc


def stop_server(proc: subprocess.Popen, name: str) -> None:
    """Stop a server process and its children where supported."""
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    print(f"✗ {name} server stopped")


def http_request(port: int, method: str, path: str, body: dict | None) -> dict[str, Any]:
    """Send an HTTP request and return a normalized output object."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    body_bytes = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    conn.request(method, path, body=body_bytes, headers=headers)
    resp = conn.getresponse()
    raw_body = resp.read().decode()
    conn.close()
    try:
        parsed_body: Any = json.loads(raw_body) if raw_body else None
    except json.JSONDecodeError:
        parsed_body = raw_body
    return {"status": resp.status, "body": parsed_body}


def body_matches(actual: Any, expected: Any) -> bool:
    """Check exact or shape-only body matches.

    String values `"int"`, `"str"`, `"float"`, `"bool"`, `"list"`, and `"dict"`
    mean shape-only assertions for dynamic fields.
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
            if isinstance(val, str) and val in SHAPE_TYPES:
                if not isinstance(actual[key], SHAPE_TYPES[val]):
                    return False
            elif not body_matches(actual[key], val):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        return all(body_matches(item, expected_item) for item, expected_item in zip(actual, expected))
    return actual == expected


def contract_result(output: dict[str, Any], entry: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate one server response against replay expectations."""
    issues: list[str] = []
    expected_status = entry.get("expected_status")
    expected_body = entry.get("expected_body")
    expected_shape = entry.get("expected_body_shape")

    if expected_status is not None and output.get("status") != expected_status:
        issues.append(f"status {output.get('status')} != expected {expected_status}")
    if expected_body is not None and not body_matches(output.get("body"), expected_body):
        issues.append("body does not match expected_body")
    if expected_shape is not None and not body_matches(output.get("body"), expected_shape):
        issues.append("body does not match expected_body_shape")
    return not issues, issues


def replay_requests(port: int, replay_file: Path) -> list[dict[str, Any]]:
    """Replay requests from replay.jsonl against a server, returning outputs."""
    results: list[dict[str, Any]] = []
    with replay_file.open() as handle:
        for lineno, raw in enumerate(handle, 1):
            raw = raw.strip()
            if not raw:
                continue
            entry = json.loads(raw)
            method = entry["method"]
            path = entry["path"]
            body = entry.get("body")
            property_id = entry.get("property_id") or f"P{lineno:03d}"
            try:
                output = http_request(port, method, path, body)
                passed, issues = contract_result(output, entry)
                results.append({
                    "property_id": property_id,
                    "method": method,
                    "path": path,
                    "output": output,
                    "contract_passed": passed,
                    "contract_issues": issues,
                    "entry": entry,
                })
            except Exception as exc:
                results.append({
                    "property_id": property_id,
                    "method": method,
                    "path": path,
                    "error": str(exc),
                    "contract_passed": False,
                    "contract_issues": [str(exc)],
                    "entry": entry,
                })
    return results


def response_equivalent(baseline: dict[str, Any], candidate: dict[str, Any], entry: dict[str, Any]) -> bool:
    """Compare candidate to baseline under the replay entry's approved tolerance."""
    old_output = baseline.get("output") or {}
    new_output = candidate.get("output") or {}
    if old_output.get("status") != new_output.get("status"):
        return False

    # If the contract only approves shape (dynamic IDs, timestamps), compare both
    # responses against that shape instead of exact values.
    expected_shape = entry.get("expected_body_shape")
    if expected_shape is not None:
        return body_matches(old_output.get("body"), expected_shape) and body_matches(new_output.get("body"), expected_shape)

    expected_body = entry.get("expected_body")
    if expected_body is not None:
        return body_matches(old_output.get("body"), expected_body) and body_matches(new_output.get("body"), expected_body)

    return body_matches(new_output.get("body"), old_output.get("body"))


def classify_result(baseline: dict[str, Any], candidate: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """Return (status, classification, investigation) for one replayed property."""
    if baseline.get("error"):
        return "mismatch", "reproducibility_break", f"Baseline request failed: {baseline['error']}"
    if candidate.get("error"):
        return "mismatch", "regression", f"Candidate request failed: {candidate['error']}"
    if not baseline.get("contract_passed", False):
        return "mismatch", "reproducibility_break", "Baseline no longer satisfies the replay contract: " + "; ".join(baseline.get("contract_issues", []))
    if not candidate.get("contract_passed", False):
        return "mismatch", "regression", "Candidate does not satisfy the replay contract: " + "; ".join(candidate.get("contract_issues", []))
    if not response_equivalent(baseline, candidate, baseline.get("entry", {})):
        return "mismatch", "regression", "Candidate HTTP response differs from executable baseline"
    return "pass", None, None


def build_parity_report(run_id: str, baseline_results: list[dict[str, Any]], candidate_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a parity-report.schema.json-shaped object."""
    results: list[dict[str, Any]] = []
    for baseline, candidate in zip(baseline_results, candidate_results):
        status, classification, investigation = classify_result(baseline, candidate)
        normalized_equal = status == "pass"
        item: dict[str, Any] = {
            "property_id": baseline["property_id"],
            "status": status,
            "old_output": baseline.get("output", {}),
            "new_output": candidate.get("output", {}),
            "normalized_equal": normalized_equal,
        }
        if status == "mismatch":
            item["classification"] = classification
            item["investigation"] = investigation
        results.append(item)

    mismatches = sum(1 for item in results if item["status"] == "mismatch")
    passed = len(results) - mismatches
    return {
        "run_id": run_id,
        "total_properties": len(results),
        "passed": passed,
        "mismatches": mismatches,
        "verdict": "pass" if mismatches == 0 else "fail",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Differential HTTP comparison for Mew")
    parser.add_argument("--baseline", required=True, help="Command to start baseline server")
    parser.add_argument("--baseline-dir", required=True, help="Working directory for baseline")
    parser.add_argument("--candidate", required=True, help="Command to start candidate server")
    parser.add_argument("--candidate-dir", required=True, help="Working directory for candidate")
    parser.add_argument("--replay", required=True, help="Path to replay.jsonl with captured requests")
    parser.add_argument("--output", default="parity-report.json", help="Path for output parity report")
    parser.add_argument("--run-id", default="differential-http", help="Run ID for the parity report")
    parser.add_argument("--ready-path", default="/health", help="Readiness path polled before replay")
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
        baseline_proc = start_server(args.baseline, baseline_dir, baseline_port, "Baseline", args.ready_path, args.timeout)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1

    try:
        candidate_proc = start_server(args.candidate, candidate_dir, candidate_port, "Candidate", args.ready_path, args.timeout)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        stop_server(baseline_proc, "Baseline")
        return 1

    try:
        print(f"\nReplaying {replay_path}...")
        baseline_results = replay_requests(baseline_port, replay_path)
        candidate_results = replay_requests(candidate_port, replay_path)
        report = build_parity_report(args.run_id, baseline_results, candidate_results)

        output_path = Path(args.output)
        output_path.write_text(json.dumps(report, indent=2))
        print(f"\nReport written to {output_path}")
        print(f"Passed: {report['passed']}/{report['total_properties']}, Mismatches: {report['mismatches']}/{report['total_properties']}")
        return 1 if report["mismatches"] > 0 else 0
    finally:
        stop_server(candidate_proc, "Candidate")
        stop_server(baseline_proc, "Baseline")


if __name__ == "__main__":
    raise SystemExit(main())
