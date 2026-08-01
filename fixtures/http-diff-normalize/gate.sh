#!/usr/bin/env bash
# Gate: http-diff-normalize fixture.
# Starts baseline + candidate servers, replays the 4-case sequence with the
# promoted harness, asserts exactly 2 pass + 2 designed-fail, then asserts
# the both-down case exits non-zero (no false pass).
set -u
cd "$(dirname "$0")"

PY=python3
HARNESS="../../skills/differential-migration/scripts/http_diff_test.py"
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

cd "$BASE_DIR" && cp "$OLDPWD/baseline_server.py" . && "$PY" baseline_server.py "$BASE_PORT" >/dev/null 2>&1 &
BASE_PID=$!
cd "$CAND_DIR" && cp "$OLDPWD/candidate_server.py" . && "$PY" candidate_server.py "$CAND_PORT" >/dev/null 2>&1 &
CAND_PID=$!
cd "$OLDPWD"
sleep 1.5

# 1) replay the sequence -> expect 2 pass + 2 fail (designed regressions)
OUT=$(python3 "$HARNESS" --sequence cases.json \
      --baseline "http://127.0.0.1:$BASE_PORT" \
      --candidate "http://127.0.0.1:$CAND_PORT" 2>&1)
if ! echo "$OUT" | grep -q "2/4 properties matched"; then
  echo "FAIL: expected 2/4 (2 pass + 2 designed-fail), got:"; echo "$OUT" | tail -8
  exit 1
fi
echo "PASS: sequence 2/4 as designed"

# 2) both servers down -> must exit non-zero (status 0 != pass)
if python3 "$HARNESS" --sequence cases.json \
     --baseline "http://127.0.0.1:19991" \
     --candidate "http://127.0.0.1:19992" >/dev/null 2>&1; then
  echo "FAIL: both-down case exited 0 (false pass)"
  exit 1
fi
echo "PASS: both-down exits non-zero"

echo "GATE PASS"
