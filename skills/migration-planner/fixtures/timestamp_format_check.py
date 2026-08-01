#!/usr/bin/env python3
"""Fixture: assert chrono format string matches Python datetime.isoformat().

Lesson 3 (stack:rust): Python `datetime.utcnow().isoformat()` emits ISO-8601
UTC with exactly 6-digit microseconds and NO timezone suffix. A Rust
`Utc::now().to_rfc3339()` appends Z and varies precision -> differential
mismatch.

Scope: this fixture pins and verifies the PYTHON oracle pattern only — it
does not compile or execute Rust (no cargo dependency in the skill pack).
The Rust side is verified in the migration run itself: the differential
harness replays live HTTP responses and compares the candidate's emitted
timestamps against this pattern. Use this fixture to confirm the Python
oracle contract before writing the chrono format string.

The naive UTC timestamp is built with
`datetime.now(timezone.utc).replace(tzinfo=None)` (not the deprecated
`datetime.utcnow()`) and `isoformat(timespec="microseconds")` so the
fractional-seconds part is always present — with the default
`timespec="auto"`, a timestamp whose microseconds are 0 would omit the
`.dddddd` suffix and fail TS_RE flakily.

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


def naive_utc_now() -> datetime:
    """Naive UTC now, matching datetime.utcnow() shape without the deprecation."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def main() -> int:
    naive = naive_utc_now().isoformat(timespec="microseconds")
    aware = datetime.now(timezone.utc).isoformat(timespec="microseconds")

    checks = [
        (
            "naive UTC isoformat(microseconds) matches pinned pattern",
            bool(TS_RE.fullmatch(naive)),
        ),
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
