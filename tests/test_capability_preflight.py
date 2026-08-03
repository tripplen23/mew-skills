#!/usr/bin/env python3
"""Tests for the capability preflight checker (mew#15).

Fixtures live in fixtures/capability-preflight/:
  - config-minimal.yaml   : universal requirements only
  - config-full.yaml      : universal + stack-specific + optional
  - report-good.json      : expected report for config-minimal on this host
  - report-bad-schema.json: deliberately invalid report (schema must reject)

Every test runs the real script in a subprocess (no mocks) so the
RED-GREEN loop exercises the actual CLI.
"""

import json
import os
import subprocess
import sys
import unittest

def load_report(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_capabilities.py"
FIXTURES = ROOT / "fixtures" / "capability-preflight"
SCHEMA = ROOT / "schemas" / "capability-report.schema.json"

# validate.sh convention: /tmp/valenv supplies pyyaml+jsonschema. Prefer its
# interpreter over sys.executable so the subprocess under test can import yaml.
_VALENV = Path("/tmp/valenv/bin/python3")
INTERP = str(_VALENV) if _VALENV.exists() else sys.executable


def run_check(*args: str, env=None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    e["PATH"] = "/tmp/valenv/bin:" + e.get("PATH", "")
    if env:
        e.update(env)
    return subprocess.run(
        [INTERP, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=str(ROOT), env=e,
    )


class CapabilityPreflightTest(unittest.TestCase):

    def test_missing_executable_fails_nonzero_and_reports_missing(self):
        p = run_check(
            "--config", str(FIXTURES / "config-missing-tool.yaml"),
            "--stack", "python",
            "--output", "/tmp/cap-missing.json",
        )
        self.assertNotEqual(p.returncode, 0, p.stderr)
        report = load_report("/tmp/cap-missing.json")
        missing = [c for c in report["checks"] if c["status"] == "missing"]
        self.assertTrue(missing, "expected at least one missing capability")

    def test_available_capability_reports_command_and_version(self):
        p = run_check(
            "--config", str(FIXTURES / "config-minimal.yaml"),
            "--output", "/tmp/cap-minimal.json",
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        report = load_report("/tmp/cap-minimal.json")
        self.assertEqual(report["status"], "pass")
        for c in report["checks"]:
            self.assertIn(c["status"], ("available", "missing", "incompatible", "not_applicable"))
            if c["status"] == "available":
                self.assertTrue(c["command"], f"available check {c['id']} lacks command")
                self.assertTrue(c["resolved_path"], f"available check {c['id']} lacks resolved_path")

    def test_not_applicable_capability_does_not_block(self):
        p = run_check(
            "--config", str(FIXTURES / "config-full.yaml"),
            "--stack", "go",
            "--output", "/tmp/cap-full-go.json",
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        report = load_report("/tmp/cap-full-go.json")
        for c in report["checks"]:
            if c["id"] == "toolchain-node":
                self.assertEqual(c["status"], "not_applicable")

    def test_version_incompatible_reports_incompatible(self):
        p = run_check(
            "--config", str(FIXTURES / "config-version-gate.yaml"),
            "--stack", "python",
            "--output", "/tmp/cap-version.json",
        )
        # Required capability below min_version is a blocker: non-zero exit.
        self.assertNotEqual(p.returncode, 0, p.stderr)
        report = load_report("/tmp/cap-version.json")
        gate = [c for c in report["checks"] if c["id"] == "toolchain-python"][0]
        self.assertEqual(gate["status"], "incompatible")
        self.assertEqual(report["status"], "fail")

    def test_report_matches_schema(self):
        p = run_check(
            "--config", str(FIXTURES / "config-minimal.yaml"),
            "--output", "/tmp/cap-schema.json",
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        import jsonschema
        with open(SCHEMA) as f:
            schema = json.load(f)
        jsonschema.validate(load_report("/tmp/cap-schema.json"), schema)

    def test_schema_rejects_invalid_report(self):
        import jsonschema
        with open(SCHEMA) as f:
            schema = json.load(f)
        with open(FIXTURES / "report-bad-schema.json") as f:
            bad = json.load(f)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)

    def test_unselected_stack_checks_are_not_applicable(self):
        p = run_check(
            "--config", str(FIXTURES / "config-full.yaml"),
            "--stack", "rust",
            "--output", "/tmp/cap-full-rust.json",
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        report = load_report("/tmp/cap-full-rust.json")
        by_id = {c["id"]: c for c in report["checks"]}
        self.assertIn("toolchain-cargo", by_id)
        # Node check stays visible for traceability but is not applicable.
        self.assertEqual(by_id["toolchain-node"]["status"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
