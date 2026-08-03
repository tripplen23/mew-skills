#!/usr/bin/env bash
# Fixture runner (mew#106). Discovers fixtures/*/fixture.json and executes
# each gate_command; exits 1 if any fixture fails or metadata is invalid.
#
# Usage: bash scripts/run_fixtures.sh [fixture-id ...]
set -u
cd "$(dirname "$0")/.." || { echo "FAIL: cannot enter repository root" >&2; exit 1; }
FAIL=0

# Validate metadata before executing any gate.
validate_meta() {
  local dir="$1" meta gate oracle fails_before passes_after
  meta="$dir/fixture.json"
  [ -f "$meta" ] || { echo "  FAIL: $dir (missing fixture.json)"; return 1; }
  gate=$(python3 - "$meta" <<'PY' 2>/dev/null || true
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get("gate_command", ""))
PY
)
  [ -n "$gate" ] || { echo "  FAIL: $dir (unreadable/invalid fixture.json or empty gate_command)"; return 1; }
  oracle=$(python3 - "$meta" <<'PY' 2>/dev/null || true
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get("oracle_tier", ""))
PY
)
  [ "$oracle" = "hard" ] || { echo "  FAIL: $dir (oracle_tier must be 'hard', got '$oracle')"; return 1; }
  fails_before=$(python3 - "$meta" <<'PY' 2>/dev/null || true
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get("fails_before", ""))
PY
)
  passes_after=$(python3 - "$meta" <<'PY' 2>/dev/null || true
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get("passes_after", ""))
PY
)
  [ -n "$fails_before" ] && [ -n "$passes_after" ] || {
    echo "  FAIL: $dir (provenance fields fails_before/passes_after required)"; return 1; }
  [ -x "$dir/gate.sh" ] || { echo "  FAIL: $dir (gate.sh missing or not executable)"; return 1; }
  return 0
}

run_one() {
  local id="$1" dir="fixtures/$1" log
  if ! validate_meta "$dir"; then
    FAIL=1
    return
  fi
  log=$(mktemp) || { echo "  FAIL: $id (cannot create temp log)"; FAIL=1; return; }
  local gate
  gate=$(python3 - "$dir/fixture.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1])).get("gate_command", ""))
PY
)
  if (cd "$dir" && bash -c "$gate") >"$log" 2>&1; then
    echo "  PASS: $id"
  else
    echo "  FAIL: $id (gate exited non-zero)"
    tail -5 "$log" | sed 's/^/    /'
    FAIL=1
  fi
  rm -f "$log"
}

if [ "$#" -gt 0 ]; then
  ids=("$@")
else
  ids=()
  for f in fixtures/*/fixture.json; do
    [ -e "$f" ] || continue
    dir=$(dirname "$f")
    ids+=("${dir#fixtures/}")
  done
fi

for id in "${ids[@]}"; do
  run_one "$id"
done

if [ "$FAIL" -eq 0 ]; then
  echo "All fixtures passed."
else
  echo "Some fixtures failed."
fi
exit $FAIL
