#!/usr/bin/env python3
"""Fixture: assert chrono format string matches Python datetime.isoformat().

Lesson 3 (stack:rust): Python `datetime.utcnow().isoformat()` emits ISO-8601
UTC with exactly 6-digit microseconds and NO timezone suffix. A Rust
`Utc::now().to_rfc3339()` appends Z and varies precision -> differential
mismatch. This fixture pins the expected pattern and asserts the Python
side (the oracle), so a planner can compare the chrono format string
against it.

Usage:
    python timestamp_format_check.py

Exit 0 = pattern matches Python isoformat(); exit 1 = regression.
"""

import re
import sys
from datetime import datetime, timezone

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}$")

# The chrono format string this fixture pins for Python->Rust ports.
# %.6f = exactly 6 digits; no %:z / %Z suffix.
CHRONO_FORMAT = "%Y-%m-%dT%H:%M:%S%.6f"


def main() -> int:
    naive = datetime.utcnow().isoformat()
    aware = datetime.now(timezone.utc).isoformat()

    checks = [
        ("naive utcnow().isoformat() matches pinned pattern", bool(TS_RE.fullmatch(naive))),
        ("no timezone suffix on naive output", not naive.endswith(("Z", "+00:00"))),
        ("aware output carries +00:00 (baseline contrast)", aware.endswith("+00:00")),
        ("pinned chrono format is the documented one", CHRONO_FORMAT == "%Y-%m-%dT%H:%M:%S%.6f"),
    ]
    fails = 0
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'} {name}")
        if not ok:
            fails += 1
    if fails:
        print(f"\nnaive={naive!r} aware={aware!r}")
        return 1
    print("\npattern pinned: " + TS_RE.pattern)
    return 0


if __name__ == "__main__":
    sys.exit(main())
