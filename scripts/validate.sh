#!/usr/bin/env bash
# Validate all mew-skills artifacts.
# Usage: bash scripts/validate.sh
# Requires: agentskills (uvx --from skills-ref agentskills), python3, jq, jsonschema, pyyaml (python packages; e.g. pip install jsonschema pyyaml)
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
FAIL=0

echo "=== Skill validation (agentskills validate) ==="
for skill_dir in skills/*/; do
  skill_name=$(basename "$skill_dir")
  if uvx --from skills-ref agentskills validate "$skill_dir" 2>&1; then
    echo "  PASS: $skill_name"
  else
    echo "  FAIL: $skill_name"
    FAIL=1
  fi
done

echo ""
echo "=== JSON Schema metaschema validation ==="
for schema in schemas/*.schema.json; do
  if python3 -c "import json; from jsonschema import Draft202012Validator; Draft202012Validator.check_schema(json.load(open('$schema')))" 2>/dev/null; then
    echo "  PASS: $schema is a valid Draft 2020-12 schema"
  else
    echo "  FAIL: $schema is not a valid Draft 2020-12 schema"
    FAIL=1
  fi
done

echo ""
echo "=== Holdout manifest validation ==="
if python3 -c '
import json, re
d = json.load(open("evals/holdouts.json"))
assert d.get("version") == 1
assert d.get("holdouts")
for h in d["holdouts"]:
    assert all(h.get(k) for k in ("id", "repository", "revision", "license", "stack", "status", "task", "required_checks"))
    assert h["status"] in ("planned", "baselined", "active")
    assert re.fullmatch(r"[0-9a-f]{40}", h["revision"])
' 2>/dev/null; then
  echo "  PASS: evals/holdouts.json has pinned, complete holdouts"
else
  echo "  FAIL: evals/holdouts.json is invalid or has unpinned/incomplete holdouts"
  FAIL=1
fi

echo ""
echo "=== Python script syntax ==="
if python3 -m py_compile scripts/*.py 2>/dev/null; then
  echo "  PASS: scripts/*.py compile"
else
  echo "  FAIL: a Python script has a syntax error"
  FAIL=1
fi

echo ""
echo "=== Capability preflight (mew#15) ==="
if [ -f capabilities.yaml ]; then
  cap_log=$(mktemp) || { echo "  FAIL: cannot create temp log"; FAIL=1; }
  cap_report=$(mktemp) || { echo "  FAIL: cannot create temp report"; FAIL=1; }
  if python3 scripts/check_capabilities.py --config capabilities.yaml --output "$cap_report" >"$cap_log" 2>&1; then
    echo "  PASS: capability preflight (universal)"
    tail -2 "$cap_log" | sed 's/^/    /'
  else
    echo "  FAIL: capability preflight"
    tail -6 "$cap_log" | sed 's/^/    /'
    FAIL=1
  fi
  rm -f "$cap_log"
else
  echo "  SKIP: capabilities.yaml not present"
fi

echo ""
echo "=== Capability report schema (if present) ==="
if [ -n "${cap_report:-}" ] && [ -f "$cap_report" ] && command -v jsonschema >/dev/null 2>&1; then
  if jsonschema -i "$cap_report" schemas/capability-report.schema.json >/dev/null 2>&1; then
    echo "  PASS: capability report matches capability-report schema"
  else
    echo "  FAIL: capability report does not match schema"
    FAIL=1
  fi
  rm -f "$cap_report"
else
  echo "  SKIP: no report produced or jsonschema not in PATH"
fi

echo ""
echo "=== Capability preflight tests (mew#15) ==="
cap_test_log=$(mktemp) || { echo "  FAIL: cannot create temp log"; FAIL=1; }
if [ -d tests ] && python3 -m unittest tests.test_capability_preflight >"$cap_test_log" 2>&1; then
  echo "  PASS: tests/test_capability_preflight.py"
else
  echo "  FAIL: capability preflight tests"
  tail -6 "$cap_test_log" | sed 's/^/    /'
  FAIL=1
fi
rm -f "$cap_test_log"

echo ""
echo "=== Regression fixtures (mew#106) ==="
fixture_log=$(mktemp) || { echo "  FAIL: cannot create temp log"; FAIL=1; }
if bash scripts/run_fixtures.sh >"$fixture_log" 2>&1; then
  echo "  PASS: all regression fixtures"
else
  echo "  FAIL: one or more regression fixtures"
  tail -6 "$fixture_log" | sed 's/^/    /'
  FAIL=1
fi
rm -f "$fixture_log"

echo ""
echo "=== Cross-artifact analyzer self-check ==="
if python3 scripts/analyze_run.py --selfcheck >/dev/null 2>&1; then
  echo "  PASS: analyze_run.py self-check"
else
  echo "  FAIL: analyze_run.py self-check"
  FAIL=1
fi

echo ""
echo "=== Metrics artifact schema (if present) ==="
# Per-task measurement harness (mew#104) writes metrics.json into run dirs;
# validate it against the metrics schema when present.
if command -v jsonschema >/dev/null 2>&1; then
  found=0
  for f in $(find . -name "metrics.json" -not -path "./node_modules/*" 2>/dev/null); do
    found=1
    if jsonschema -i "$f" schemas/metrics.schema.json >/dev/null 2>&1; then
      echo "  PASS: $f matches metrics schema"
    else
      echo "  FAIL: $f does not match metrics schema"
      FAIL=1
    fi
  done
  if [ "$found" -eq 0 ]; then
    echo "  PASS: no metrics.json present (measure_metrics.py not run yet)"
  fi
else
  echo "  SKIP: jsonschema not in PATH (install with pip install jsonschema)"
fi

echo ""
echo "=== Frontmatter security check (no < or > in YAML) ==="
for skill_md in skills/*/SKILL.md; do
  # Extract frontmatter (between first and second ---)
  frontmatter=$(sed -n '/^---$/,/^---$/p' "$skill_md" | head -n -1 | tail -n +2)
  if echo "$frontmatter" | grep -qE '<|>'; then
    echo "  FAIL: $skill_md has < or > in frontmatter (injection risk)"
    FAIL=1
  else
    echo "  PASS: $skill_md frontmatter clean"
  fi
done

echo ""
echo "=== Skill body size cap (SKILL.md <= 500 lines) ==="
# Anti-bloat gate: gotchas accumulate over runs, so a hard line cap forces
# pruning and progressive disclosure (details belong in references/, not body).
for skill_md in skills/*/SKILL.md; do
  lines=$(wc -l < "$skill_md")
  if [ "$lines" -le 500 ]; then
    echo "  PASS: $skill_md ($lines lines)"
  else
    echo "  FAIL: $skill_md is $lines lines (> 500); prune or move detail to references/"
    FAIL=1
  fi
done

echo ""
echo "=== Name == directory check ==="
for skill_dir in skills/*/; do
  skill_name=$(basename "$skill_dir")
  declared_name=$(sed -n '/^---$/,/^---$/p' "$skill_dir/SKILL.md" | grep '^name:' | sed 's/name: *//' | tr -d '"')
  if [ "$skill_name" = "$declared_name" ]; then
    echo "  PASS: $skill_name (dir matches frontmatter)"
  else
    echo "  FAIL: dir=$skill_name but frontmatter name=$declared_name"
    FAIL=1
  fi
done

echo ""
if [ $FAIL -eq 0 ]; then
  echo "All checks passed."
  exit 0
else
  echo "Some checks failed."
  exit 1
fi
