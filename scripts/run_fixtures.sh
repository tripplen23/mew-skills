#!/usr/bin/env bash
# Fixture runner (mew#106). Discovers fixtures/*/fixture.json and executes
# each gate_command; exits 1 if any fixture fails.
#
# Usage: bash scripts/run_fixtures.sh [fixture-id ...]
set -u
cd "$(dirname "$0")/.."
FAIL=0

if [ "$#" -gt 0 ]; then
  SELECT="$*"
else
  SELECT="$(ls fixtures/*/fixture.json 2>/dev/null | xargs -n1 dirname | xargs -n1 basename)"
fi

for id in $SELECT; do
  dir="fixtures/$id"
  if [ ! -f "$dir/fixture.json" ]; then
    echo "  FAIL: $id (no fixture.json)"
    FAIL=1
    continue
  fi
  gate=$(python3 -c "import json,sys; print(json.load(open('$dir/fixture.json')).get('gate_command','bash gate.sh'))" 2>/dev/null)
  if (cd "$dir" && bash -c "$gate" >/tmp/fixture-$id.log 2>&1); then
    echo "  PASS: $id"
  else
    echo "  FAIL: $id (gate exited non-zero)"
    tail -5 /tmp/fixture-$id.log | sed 's/^/    /'
    FAIL=1
  fi
done

if [ "$FAIL" -eq 0 ]; then
  echo "All fixtures passed."
else
  echo "Some fixtures failed."
fi
exit $FAIL
