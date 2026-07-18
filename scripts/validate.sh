#!/usr/bin/env bash
# Validate all mew-skills artifacts.
# Usage: bash scripts/validate.sh
# Requires: agentskills (uvx --from skills-ref agentskills), python3, jq
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
echo "=== JSON Schema validation ==="
for schema in schemas/*.schema.json; do
  if python3 -c "import json; json.load(open('$schema'))" 2>/dev/null; then
    echo "  PASS: $schema is valid JSON"
  else
    echo "  FAIL: $schema is not valid JSON"
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
