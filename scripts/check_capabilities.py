#!/usr/bin/env python3
"""Read-only capability preflight for Mew skill runs.

Checks declared requirements against the current host without installing,
modifying, or writing anything outside the requested output file. Modeled
on the tool-index concept from security skill packs, but deliberately:

- read-only: never installs, never edits PATH/profiles/MCP config;
- scope-selected: checks only requirements matching --stack (and
  universal ones), never a broad host inventory;
- evidence-recorded: every check records command, resolved path, and
  version output so a clean worker can reproduce the decision.

Exit codes: 0 = all required capabilities present (or report written and
optional checks only missing), 1 = invalid manifest or a required capability
is missing/incompatible. A schema-shaped report is written on every evaluated
failure so the run can record an honest blocker.

Usage:
  check_capabilities.py --config capabilities.yaml --stack <stack> --output <report.json>
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"
VALID_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
VALID_VERSION = re.compile(r"^\d+(?:\.\d+)*$")


class ConfigError(ValueError):
    """Capability manifest is malformed."""


def load_config(path: Path) -> dict:
    try:
        import yaml  # pyyaml
    except ImportError as exc:
        raise ConfigError("pyyaml required (pip install pyyaml)") from exc
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read capability manifest: {exc}") from exc
    validate_config(data)
    return data


def validate_config(data: object) -> None:
    """Validate manifest types before any command is executed."""
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ConfigError("manifest must be an object with version: 1")
    checks = data.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ConfigError("manifest must declare a non-empty checks list")
    seen: set[str] = set()
    for index, check in enumerate(checks):
        label = f"checks[{index}]"
        if not isinstance(check, dict):
            raise ConfigError(f"{label} must be an object")
        for field in ("id", "purpose", "command"):
            if not isinstance(check.get(field), str) or not check[field].strip():
                raise ConfigError(f"{label}.{field} must be a non-empty string")
        if not VALID_ID.fullmatch(check["id"]):
            raise ConfigError(f"{label}.id must match {VALID_ID.pattern}")
        if check["id"] in seen:
            raise ConfigError(f"duplicate check id: {check['id']}")
        seen.add(check["id"])
        if "required" in check and not isinstance(check["required"], bool):
            raise ConfigError(f"{label}.required must be boolean")
        for field in ("args", "stacks"):
            if field in check and (
                not isinstance(check[field], list)
                or not all(isinstance(v, str) and v for v in check[field])
            ):
                raise ConfigError(f"{label}.{field} must be a list of non-empty strings")
        if "min_version" in check and (
            not isinstance(check["min_version"], str)
            or not VALID_VERSION.fullmatch(check["min_version"])
        ):
            raise ConfigError(f"{label}.min_version must be a dotted numeric version")


def probe_version(command: str, args: list[str]) -> tuple[str | None, bool]:
    """Run a version probe and return its evidence plus success flag."""
    try:
        proc = subprocess.run(
            [command, *args], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, False
    out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    return out or None, proc.returncode == 0


def check_one(entry: dict, stack: str) -> dict:
    """Evaluate a single validated check against the host."""
    check_id = entry["id"]
    purpose = entry["purpose"]
    command = entry["command"]
    args = entry.get("args") or ["--version"]
    required = entry.get("required", True)
    declared_stacks = entry.get("stacks")
    applicable = declared_stacks is None or stack in declared_stacks
    base = {
        "id": check_id,
        "purpose": purpose,
        "required": required,
        "stack": stack if declared_stacks else None,
        "command": command,
        "args": args,
        "resolved_path": None,
        "version_output": None,
        "min_version": entry.get("min_version"),
        "detected_version": None,
    }
    if not applicable:
        return {**base, "status": "not_applicable"}
    resolved = shutil.which(command)
    if resolved is None:
        return {**base, "status": "missing"}
    version_output, probe_ok = probe_version(resolved, args)
    detected = extract_version(version_output) if version_output else None
    min_version = entry.get("min_version")
    status = "available"
    if not probe_ok:
        status = "incompatible"
    elif min_version and (not detected or not version_ge(detected, min_version)):
        status = "incompatible"
    return {
        **base,
        "status": status,
        "resolved_path": str(resolved),
        "version_output": version_output,
        "detected_version": detected,
    }


def extract_version(text: str) -> str | None:
    """Extract an unqualified dotted numeric version; reject prereleases."""
    match = re.search(r"(?<![\d.])(\d+(?:\.\d+)+)(?![\w.-])", text)
    return match.group(1) if match else None


def version_ge(a: str, b: str) -> bool:
    """Compare dotted numeric versions; missing trailing components = 0."""
    na = [int(x) for x in a.split(".")]
    nb = [int(x) for x in b.split(".")]
    length = max(len(na), len(nb))
    na += [0] * (length - len(na))
    nb += [0] * (length - len(nb))
    return na >= nb


def manifest_failure(message: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "checks": [{
            "id": "manifest",
            "purpose": message,
            "status": "incompatible",
            "command": "manifest",
            "args": [],
            "resolved_path": None,
            "version_output": None,
            "required": True,
            "stack": None,
            "min_version": None,
            "detected_version": None,
        }],
    }


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only Mew capability preflight")
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--stack", default="", help="target stack: python, rust, go, node, ...")
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        report = manifest_failure(str(exc))
        write_report(args.output, report)
        print(f"  incompatible   manifest  <-- BLOCKER\ncapability status: fail")
        return 1

    results = [check_one(c, args.stack) for c in config["checks"]]
    blocked = [
        r for r in results
        if r["status"] in ("missing", "incompatible") and r["required"]
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "fail" if blocked else "pass",
        "checks": results,
    }
    write_report(args.output, report)

    for result in results:
        blocker = (
            "  <-- BLOCKER"
            if result["required"] and result["status"] in ("missing", "incompatible")
            else ""
        )
        print(f"  {result['status']:14} {result['id']}{blocker}")
    print(f"capability status: {report['status']}")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
