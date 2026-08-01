#!/usr/bin/env bash
# Gate: http-diff-normalize fixture.
# Starts baseline + candidate servers, replays the 4-case sequence with the
# promoted harness, asserts per-property verdicts (P001/P002 pass via
# normalizers, P003/P004 designed-fail), then asserts the both-down case
# exits non-zero (no false pass).
set -u
FIXTURE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$FIXTURE_DIR" || exit 1

PY=python3
HARNESS="$FIXTURE_DIR/../../skills/differential-migration/scripts/http_diff_test.py"
BASE_PORT=19001
CAND_PORT=19002
BASE_DIR=$(mktemp -d)
CAND_DIR=$(mktemp -d)
cleanup() {
  [ -n "${BASE_PID:-}" ] && kill "$BASE_PID" 2>/dev/null
  [ -n "${CAND_PID:-}" ] && kill "$CAND_PID" 2>/dev/null
  rm -rf "$BASE_DIR" "$CAND_DIR"
}
trap cleanup EXIT

cd "$BASE_DIR" && cp "$FIXTURE_DIR/baseline_server.py" . && "$PY" baseline_server.py "$BASE_PORT" >/dev/null 2>&1 &
BASE_PID=$!
cd "$CAND_DIR" && cp "$FIXTURE_DIR/candidate_server.py" . && "$PY" candidate_server.py "$CAND_PORT" >/dev/null 2>&1 &
CAND_PID=$!
cd "$FIXTURE_DIR" || exit 1
sleep 1.5

# 1) replay the sequence; capture verdicts per property
OUT=$(python3 "$HARNESS" --sequence cases.json \
      --baseline "http://127.0.0.1:$BASE_PORT" \
      --candidate "http://127.0.0.1:$CAND_PORT" 2>&1) || true
echo "$OUT" | sed 's/^/  [harness] /'

# P001 (timestamps+json_order) and P002 (timestamps) must PASS via normalizers
for prop in P001 P002; do
  if ! echo "$OUT" | grep -qE "^PASS $prop "; then
    echo "FAIL: $prop expected PASS (normalizer should reconcile), output above"
    exit 1
  fi
done
echo "PASS: P001/P002 reconciled by normalizers"

# P003 (404 shape) and P004 (201-vs-204) must FAIL (designed regressions)
for prop in P003 P004; do
  if ! echo "$OUT" | grep -qE "^FAIL $prop "; then
    echo "FAIL: expected $prop to FAIL (designed regression), output above"
    exit 1
  fi
done
echo "PASS: P003/P004 reported as mismatches"

# 2) both servers down -> must exit non-zero (status 0 != pass)
if python3 "$HARNESS" --sequence cases.json \
     --baseline "http://127.0.0.1:19991" \
     --candidate "http://127.0.0.1:19992" >/dev/null 2>&1; then
  echo "FAIL: both-down case exited 0 (false pass)"
  exit 1
fi
echo "PASS: both-down exits non-zero"

echo "GATE PASS"
