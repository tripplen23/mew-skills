#!/usr/bin/env python3
"""Validate a Mew run directory against the pack schemas.

Usage: python3 scripts/validate_run.py <run-dir>

Checks every produced artifact against its JSON Schema and validates
evidence.jsonl line by line. Exit code is non-zero if any artifact drifts from
its schema. This is the run-time gate the skills instruct ("validate against
schemas/..."); validate.sh only checks the schema files themselves.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

try:
    import yaml  # optional; only needed for .yaml artifacts
except ImportError:  # ponytail: YAML artifacts skipped (not failed) without pyyaml.
    yaml = None

PACK = Path(__file__).resolve().parents[1]

# artifact filename -> schema filename
ARTIFACTS = {
    "migration-request.json": "migration-request.schema.json",
    "manifest.json": "run-manifest.schema.json",
    "repro.json": "repro.schema.json",
    "provenance.json": "provenance.schema.json",
    "behavioral-contract.yaml": "behavioral-contract.schema.json",
    "migration-plan.yaml": "migration-plan.schema.json",
    "parity-report.json": "parity-report.schema.json",
}


def load(path: Path):
    text = path.read_text()
    if path.suffix == ".yaml":
        if yaml is None:
            raise RuntimeError("pyyaml not installed; cannot validate YAML artifact")
        return yaml.safe_load(text)
    return json.loads(text)


def validator(schema_name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((PACK / "schemas" / schema_name).read_text()))


def validate_run(run_dir: Path) -> int:
    if not run_dir.is_dir():
        print(f"not a directory: {run_dir}")
        return 2

    failures = 0
    checked = 0
    for artifact, schema_name in ARTIFACTS.items():
        path = run_dir / artifact
        if not path.exists():
            continue
        checked += 1
        try:
            data = load(path)
        except (RuntimeError, ValueError) as exc:
            print(f"FAIL {artifact}: cannot load ({exc})")
            failures += 1
            continue
        errors = sorted(validator(schema_name).iter_errors(data), key=lambda e: list(e.path))
        if errors:
            failures += 1
            print(f"FAIL {artifact}: {len(errors)} schema error(s)")
            for err in errors[:5]:
                print(f"     {list(err.path) or '<root>'}: {err.message}")
        else:
            print(f"PASS {artifact}")

    evidence = run_dir / "evidence.jsonl"
    if evidence.exists():
        checked += 1
        ev = validator("evidence.schema.json")
        bad = 0
        total = 0
        for lineno, raw in enumerate(evidence.read_text().splitlines(), 1):
            raw = raw.strip()
            if not raw:
                continue
            total += 1
            try:
                record = json.loads(raw)
            except ValueError as exc:
                bad += 1
                print(f"FAIL evidence.jsonl:{lineno}: not JSON ({exc})")
                continue
            errs = list(ev.iter_errors(record))
            if errs:
                bad += 1
                print(f"FAIL evidence.jsonl:{lineno}: {list(errs[0].path) or '<root>'}: {errs[0].message}")
        if bad:
            failures += 1
            print(f"FAIL evidence.jsonl: {bad}/{total} entries invalid")
        else:
            print(f"PASS evidence.jsonl ({total} entries)")

    if checked == 0:
        print("no known artifacts found to validate")
        return 2
    if failures:
        print(f"\n{failures} artifact(s) failed schema validation.")
        return 1
    print("\nAll present artifacts are schema-valid.")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    return validate_run(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
