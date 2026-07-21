#!/usr/bin/env python3
"""Validate a Mew run directory against the pack schemas.

Usage:
  python3 scripts/validate_run.py <run-dir>
  python3 scripts/validate_run.py --final <run-dir>

Default mode validates every present schema-backed artifact. `--final` also
requires the complete handoff artifact set. Exit code is non-zero on missing or
invalid artifacts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

try:
    import yaml  # optional; only needed for .yaml artifacts
    from yaml import YAMLError
except ImportError:  # ponytail: YAML artifacts skipped (not failed) without pyyaml.
    yaml = None
    YAMLError = ValueError

PACK = Path(__file__).resolve().parents[1]


def artifact_path(run_dir: Path, filename: str) -> Path | None:
    root = run_dir.resolve()
    path = root / filename
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError(f"artifact must not be a symlink: {filename}")
    resolved = path.resolve()
    if resolved.parent != root or not resolved.is_file():
        raise ValueError(f"artifact escapes run directory or is not a file: {filename}")
    return resolved


# artifact filename -> schema filename
ARTIFACTS = {
    "migration-request.json": "migration-request.schema.json",
    "manifest.json": "run-manifest.schema.json",
    "run-state.json": "run-state.schema.json",
    "repro.json": "repro.schema.json",
    "provenance.json": "provenance.schema.json",
    "repo-inventory.yaml": "repo-inventory.schema.json",
    "behavioral-contract.yaml": "behavioral-contract.schema.json",
    "migration-plan.yaml": "migration-plan.schema.json",
    "parity-report.json": "parity-report.schema.json",
}
FINAL_REQUIRED = set(ARTIFACTS) | {"evidence.jsonl"}


def load(path: Path):
    text = path.read_text()
    if path.suffix == ".yaml":
        if yaml is None:
            raise RuntimeError("pyyaml not installed; cannot validate YAML artifact")
        return yaml.safe_load(text)
    return json.loads(text)


def validator(schema_name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((PACK / "schemas" / schema_name).read_text()))


def validate_run(run_dir: Path, *, final: bool = False) -> int:
    if not run_dir.is_dir():
        print(f"not a directory: {run_dir}")
        return 2

    failures = 0
    checked = 0
    paths: dict[str, Path | None] = {}
    for name in FINAL_REQUIRED:
        try:
            paths[name] = artifact_path(run_dir, name)
        except ValueError as exc:
            print(f"FAIL {name}: {exc}")
            paths[name] = None
            failures += 1
    if final:
        missing = sorted(name for name in FINAL_REQUIRED if paths[name] is None)
        for name in missing:
            print(f"FAIL {name}: required for final handoff")
        failures += len(missing)

    for artifact, schema_name in ARTIFACTS.items():
        path = paths[artifact]
        if path is None:
            continue
        checked += 1
        try:
            data = load(path)
        except (OSError, UnicodeError, RuntimeError, ValueError, YAMLError) as exc:
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

    evidence = paths["evidence.jsonl"]
    if evidence is not None:
        checked += 1
        ev = validator("evidence.schema.json")
        bad = 0
        total = 0
        try:
            evidence_lines = evidence.read_text().splitlines()
        except (OSError, UnicodeError) as exc:
            print(f"FAIL evidence.jsonl: cannot load ({exc})")
            return 1
        for lineno, raw in enumerate(evidence_lines, 1):
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
    if len(sys.argv) == 2:
        return validate_run(Path(sys.argv[1]).resolve())
    if len(sys.argv) == 3 and sys.argv[1] == "--final":
        return validate_run(Path(sys.argv[2]).resolve(), final=True)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
