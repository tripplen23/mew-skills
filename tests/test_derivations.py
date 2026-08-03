#!/usr/bin/env python3
"""Tests for the run-artifact derivation record (derivations.jsonl).

Derivation links a produced artifact to its input artifacts with content
hashes, so a reviewer or clean worker can reconstruct the inputs->artifact
chain without the transcript. Each line is validated against
schemas/derivations.schema.json; analyze_run.py verifies the on-disk
hashes match.

Fixtures live in fixtures/derivations/:
  - run/           : minimal run dir with manifest + evidence + one artifact
  - bad-hash.jsonl : a derivation whose derived.sha256 does not match disk
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPEND = ROOT / "scripts" / "append_derivation.py"
ANALYZE = ROOT / "scripts" / "analyze_run.py"
SCHEMA = ROOT / "schemas" / "derivations.schema.json"
FIXTURES = ROOT / "fixtures" / "derivations"
RUN_DIR = FIXTURES / "20260801-181337-217cab5"

import jsonschema


def run_appender(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(APPEND), *args],
        capture_output=True, text=True, cwd=str(ROOT),
    )


def load_lines(path: Path) -> list[dict]:
    entries = []
    for raw in path.read_text().splitlines():
        if raw.strip():
            entries.append(json.loads(raw))
    return entries


class DerivationsTest(unittest.TestCase):

    def setUp(self):
        # Fresh copy of the fixture run dir per test so appends never leak
        # across tests (append-only history makes counts order-dependent).
        # The dir name must equal the run_id inside the artifacts (identity
        # check) and match the derivations run_id pattern.
        import shutil
        self.work_root = ROOT / "tests" / ".tmp-derivations"
        self.work = self.work_root / RUN_DIR.name
        if self.work_root.exists():
            shutil.rmtree(self.work_root)
        shutil.copytree(RUN_DIR, self.work)

    def test_append_writes_schema_valid_record_with_real_hash(self):
        p = run_appender(
            "--run-dir", str(self.work),
            "--derived", "behavioral-contract.yaml",
            "--inputs", "manifest.json,evidence.jsonl",
            "--phase", "contract",
            "--action", "derive_property",
            "--details", "property_id=P001,kind=preserve",
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        lines = load_lines(self.work / "derivations.jsonl")
        self.assertEqual(len(lines), 1)
        rec = lines[0]
        with open(SCHEMA) as f:
            schema = json.load(f)
        jsonschema.validate(rec, schema)
        # Hash must match the on-disk artifact, not a placeholder.
        import hashlib
        disk_hash = hashlib.sha256(
            (self.work / "behavioral-contract.yaml").read_bytes()
        ).hexdigest()
        self.assertEqual(rec["derived"]["sha256"], disk_hash)
        self.assertEqual(rec["derived"]["artifact"], "behavioral-contract.yaml")
        self.assertEqual(rec["phase"], "contract")
        self.assertEqual(rec["action"], "derive_property")
        self.assertEqual(rec["details"]["property_id"], "P001")

    def test_append_is_append_only(self):
        for _ in range(2):
            p = run_appender(
                "--run-dir", str(self.work),
                "--derived", "behavioral-contract.yaml",
                "--inputs", "manifest.json",
                "--phase", "contract",
                "--action", "derive_property",
            )
            self.assertEqual(p.returncode, 0, p.stderr)
        lines = load_lines(self.work / "derivations.jsonl")
        self.assertEqual(len(lines), 2)
        # Same content must appear twice (history preserved), and hashes equal.
        self.assertEqual(lines[0]["derived"]["sha256"], lines[1]["derived"]["sha256"])

    def test_append_rejects_missing_derived_artifact(self):
        p = run_appender(
            "--run-dir", str(self.work),
            "--derived", "no-such-artifact.yaml",
            "--inputs", "manifest.json",
            "--phase", "contract",
            "--action", "derive_property",
        )
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("no-such-artifact.yaml", p.stderr)
        self.assertFalse((self.work / "derivations.jsonl").exists())

    def test_analyze_run_rejects_hash_mismatch(self):
        # Copy fixture's derivations with a deliberately wrong hash into work.
        bad = (FIXTURES / "bad-hash.jsonl").read_text()
        bad = bad.replace("20260803-000000-abcdef0", "20260801-181337-217cab5")
        (self.work / "derivations.jsonl").write_text(bad)
        p = subprocess.run(
            [sys.executable, str(ANALYZE), str(self.work)],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("derivations", p.stdout + p.stderr)

    def test_analyze_run_passes_with_valid_derivations(self):
        p = run_appender(
            "--run-dir", str(self.work),
            "--derived", "behavioral-contract.yaml",
            "--inputs", "manifest.json,evidence.jsonl",
            "--phase", "contract",
            "--action", "derive_property",
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        q = subprocess.run(
            [sys.executable, str(ANALYZE), str(self.work)],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(q.returncode, 0, q.stdout + q.stderr)


if __name__ == "__main__":
    unittest.main()
