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
