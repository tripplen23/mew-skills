#!/usr/bin/env python3
"""Read-only capability preflight for Mew skill runs (mew#15).

Checks declared requirements against the current host without installing,
modifying, or writing anything outside the requested output file. Modeled
on the tool-index concept from security skill packs, but deliberately:

- read-only: never installs, never edits PATH/profiles/MCP config;
- scope-selected: checks only requirements matching --stack (and
  universal ones), never a broad host inventory;
- evidence-recorded: every check records command, resolved path, and
  version output so a clean worker can reproduce the decision.

Exit codes: 0 = all required capabilities present (or report written and
optional checks only missing), 1 = required capability missing or
incompatible. The report is written even on failure so the run can
record the blocker as evidence.

Usage:
  check_capabilities.py --config capabilities.yaml --stack <stack> --output <report.json>
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"


def load_config(path: Path) -> dict:
    try:
        import yaml  # pyyaml
    except ImportError as exc:
        raise SystemExit("check_capabilities: pyyaml required (pip install pyyaml)") from exc
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or data.get("version") != 1:
        raise SystemExit(f"check_capabilities: {path} has no version: 1 manifest")
    checks = data.get("checks")
    if not isinstance(checks, list) or not checks:
        raise SystemExit(f"check_capabilities: {path} declares no checks")
    return data


def detect_version(command: str, args: list[str]) -> str | None:
    """Run the check command and return its first non-empty stream (trimmed).

    Uses the resolved absolute path for determinism and reads both stdout and
    stderr, since several tools print version information to stderr.
    """
    try:
        proc = subprocess.run(
            [command, *args], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    return out or None


def check_one(entry: dict, stack: str) -> dict:
    """Evaluate a single declared check against the host."""
    check_id = entry["id"]
    purpose = entry.get("purpose", "")
    command = entry["command"]
    args = entry.get("args") or ["--version"]
    required = bool(entry.get("required", True))
    declared_stacks = entry.get("stacks")
    applicable = declared_stacks is None or stack in declared_stacks
    if not applicable:
        return {
            "id": check_id, "purpose": purpose, "status": "not_applicable",
            "required": required, "stack": stack, "command": command, "args": args,
            "resolved_path": None, "version_output": None, "min_version": None,
            "detected_version": None,
        }
    resolved = shutil.which(command)
    if resolved is None:
        return {
            "id": check_id, "purpose": purpose, "status": "missing",
            "required": required, "stack": stack if declared_stacks else None,
            "command": command, "args": args, "resolved_path": None,
            "version_output": None, "min_version": None, "detected_version": None,
        }
    probe_cmd = resolved if resolved else command
    version_output = detect_version(probe_cmd, args)
    detected = extract_version(version_output) if version_output else None
    min_version = entry.get("min_version")
    status = "available"
    if min_version and detected:
        if not version_ge(detected, min_version):
            status = "incompatible"
    elif min_version and not detected:
        # Cannot verify the gate -> treat as incompatible (fail closed).
        status = "incompatible"
    return {
        "id": check_id, "purpose": purpose, "status": status,
        "required": required, "stack": stack if declared_stacks else None,
        "command": command, "args": args, "resolved_path": str(resolved),
        "version_output": version_output, "min_version": min_version,
        "detected_version": detected,
    }


def extract_version(text: str) -> str | None:
    """First dotted numeric run in the output, e.g. 'Python 3.11.4' -> 3.11.4."""
    import re
    m = re.search(r"\d+(?:\.\d+)+", text)
    return m.group(0) if m else None


def version_ge(a: str, b: str) -> bool:
    """Compare dotted numeric versions; missing trailing components = 0."""
    import re
    def nums(v: str) -> list[int]:
        return [int(x) for x in re.findall(r"\d+", v)]
    na, nb = nums(a), nums(b)
    length = max(len(na), len(nb))
    na += [0] * (length - len(na))
    nb += [0] * (length - len(nb))
    for x, y in zip(na, nb):
        if x != y:
            return x > y
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only Mew capability preflight")
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--stack", default="", help="target stack: python, rust, go, node, ...")
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    config = load_config(args.config)
    results = [check_one(c, args.stack) for c in config["checks"]]
    blocked = [r for r in results if r["status"] in ("missing", "incompatible") and r["required"]]
    report = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "fail" if blocked else "pass",
        "checks": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    for r in results:
        flag = "" if r["status"] == "available" or r["status"] == "not_applicable" else "  <-- BLOCKER" if r["required"] else ""
        print(f"  {r['status']:14} {r['id']} {flag}")
    print(f"capability status: {report['status']}")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
