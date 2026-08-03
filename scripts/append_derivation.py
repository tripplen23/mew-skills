#!/usr/bin/env python3
"""Append one run-artifact derivation record to derivations.jsonl.

A derivation links a produced artifact to its input artifacts with SHA-256
content hashes, so a reviewer or clean worker can reconstruct the
inputs->artifact chain without the transcript (PRD §13).

The record is append-only: existing lines are never rewritten. The derived
artifact must exist inside the run directory at append time; its hash is
computed from the on-disk bytes, never taken from user input. Input
artifacts must also exist (symlinks rejected) so a later analyze_run pass
can verify the full chain.

Usage:
  append_derivation.py --run-dir <dir> --derived <artifact> \
      [--inputs a,b,c] --phase <phase> --action <action> \
      [--details key=value,key2=value2]
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"
PHASES = {
    "ingest", "reproduce", "observe", "grill", "contract", "plan",
    "implement", "verify", "handoff",
}


def _contained_file(run_dir: Path, name: str) -> Path:
    """Return a regular file inside run_dir; reject escapes and symlinks."""
    root = run_dir.resolve()
    path = root / name
    if not path.exists() or not path.is_file():
        raise ValueError(f"artifact does not exist in run dir: {name}")
    if path.is_symlink():
        raise ValueError(f"artifact must not be a symlink: {name}")
    resolved = path.resolve()
    if resolved.parent != root:
        raise ValueError(f"artifact escapes run directory: {name}")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Append a run-artifact derivation record")
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--derived", required=True, help="artifact produced by this action")
    ap.add_argument("--inputs", default="", help="comma-separated input artifact names")
    ap.add_argument("--phase", required=True, choices=sorted(PHASES))
    ap.add_argument("--action", required=True)
    ap.add_argument("--details", default="", help="comma-separated key=value pairs")
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    if not run_dir.is_dir():
        print(f"error: run dir does not exist: {run_dir}", file=sys.stderr)
        return 1

    # Reject traversal attempts before any file access.
    if Path(args.derived).name != args.derived or any(
        Path(name).name != name for name in args.inputs.split(",") if name
    ):
        print("error: artifact names must be plain filenames", file=sys.stderr)
        return 1

    try:
        derived_path = _contained_file(run_dir, args.derived)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    inputs = []
    for name in args.inputs.split(","):
        if not name:
            continue
        try:
            path = _contained_file(run_dir, name)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        inputs.append({"artifact": name, "sha256": _sha256(path)})

    details = {}
    for pair in args.details.split(","):
        if not pair:
            continue
        if "=" not in pair:
            print(f"error: details must be key=value, got: {pair}", file=sys.stderr)
            return 1
        key, value = pair.split("=", 1)
        details[key.strip()] = value.strip()

    record = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "derived": {"artifact": args.derived, "sha256": _sha256(derived_path)},
        "inputs": inputs,
        "phase": args.phase,
        "action": args.action,
        "details": details,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    derivations = run_dir / "derivations.jsonl"
    with open(derivations, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()
    print(f"appended derivation: {args.derived} ({record['derived']['sha256'][:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
