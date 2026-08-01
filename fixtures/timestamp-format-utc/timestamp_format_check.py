#!/usr/bin/env python3
"""Fixture: assert the timestamp normalizer contract (mew#106).

Regression fixture for the UTC-only timestamp normalizer promoted with the
HTTP differential harness (Lesson: only UTC suffixes collapse; a real
timezone offset stays visible so it still fails comparison).

This fixture imports the *actual* normalizer from the skill pack
(`differential-migration/scripts/http_diff_test.py`) and asserts the cases
advertised in `fixture.json`:

  full-string  `2026-08-01T10:00:00.123456`        -> <TS>
  embedded     `"ts 2026-08-01T10:00:00Z here"`    -> "ts <TS> here"
  Z suffix     `2026-08-01T10:00:00Z`              -> <TS>
  +00:00       `2026-08-01T10:00:00+00:00`         -> <TS>
  seconds-only `2026-08-01T10:00:00`               -> <TS>
  +05:30       `2026-08-01T10:00:00+05:30`         -> <TS>+05:30 (offset kept visible)

Exit 0 = all cases behave; exit 1 = regression.
"""

import re
import sys
from pathlib import Path

# Load the harness module by path so the fixture tests the real normalizer.
HARNESS = (
    Path(__file__).resolve().parents[2]
    / "skills" / "differential-migration" / "scripts" / "http_diff_test.py"
)
if not HARNESS.exists():
    print(f"FAIL harness not found: {HARNESS}")
    sys.exit(1)

import importlib.util

spec = importlib.util.spec_from_file_location("http_diff_test", HARNESS)
if spec is None or spec.loader is None:
    print(f"FAIL cannot load harness: {HARNESS}")
    sys.exit(1)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
normalize_timestamps = mod.normalize_timestamps

TS = "<TS>"

CASES = [
    # (label, input, expected)
    ("full-string microseconds", "2026-08-01T10:00:00.123456", TS),
    ("embedded in larger string", "item created at 2026-08-01T10:00:00Z", "item created at <TS>"),
    ("Z suffix", "2026-08-01T10:00:00Z", TS),
    ("+00:00 suffix", "2026-08-01T10:00:00+00:00", TS),
    ("-00:00 suffix", "2026-08-01T10:00:00-00:00", TS),
    ("seconds-only (no fraction, no suffix)", "2026-08-01T10:00:00", TS),
    ("1-digit fraction", "2026-08-01T10:00:00.1", TS),
    ("6-digit fraction", "2026-08-01T10:00:00.123456", TS),
    ("non-UTC offset stays visible", "2026-08-01T10:00:00+05:30", f"{TS}+05:30"),
    ("negative non-UTC offset stays visible", "2026-08-01T10:00:00-08:00", f"{TS}-08:00"),
    ("dict value", {"ts": "2026-08-01T10:00:00.123456"}, {"ts": TS}),
    ("list element", ["2026-08-01T10:00:00Z"], [TS]),
]


def main() -> int:
    fails = 0
    for label, inp, expected in CASES:
        got = normalize_timestamps(inp)
        ok = got == expected
        print(f"{'PASS' if ok else 'FAIL'} {label}: {got!r}")
        if not ok:
            fails += 1
    if fails:
        print(f"\n{fails} case(s) failed")
        return 1
    print("\nnormalizer contract pinned: UTC-only collapse, non-UTC visible")
    return 0


if __name__ == "__main__":
    sys.exit(main())
