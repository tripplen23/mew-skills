#!/usr/bin/env bash
# Gate: timestamp-format-utc fixture.
# Runs the Python oracle pattern check; must exit 0 (all 4 cases behave).
set -u
cd "$(dirname "$0")"

if python3 timestamp_format_check.py >/dev/null 2>&1; then
  echo "PASS: timestamp format check exit 0"
  echo "GATE PASS"
  exit 0
fi
echo "FAIL: timestamp format check exited non-zero"
exit 1
