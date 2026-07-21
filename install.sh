#!/usr/bin/env bash
# mew-skills — installer shim.
#
# Fetches (or updates) a cached clone of mew-skills and runs the existing
# scripts/install-agent-skills.py against the current directory as target.
#
# One-line install (run inside the target repo):
#   curl -fsSL https://raw.githubusercontent.com/tripplen23/mew-skills/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/tripplen23/mew-skills/main/install.sh | bash -s -- --host claude
#
# Local clone:
#   bash install.sh [flags forwarded to install-agent-skills.py]
#
# ponytail: host auto-detection is a naive directory-presence heuristic
# (first match wins); upgrade path is to let install-agent-skills.py itself
# probe/report ambiguity if false positives show up in practice.

set -euo pipefail

REPO="tripplen23/mew-skills"
CACHE_DIR="${MEW_SKILLS_CACHE:-$HOME/.cache/mew-skills}"

if ! command -v git >/dev/null 2>&1; then
  echo "mew-skills: git is required." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "mew-skills: python3 is required." >&2
  exit 1
fi

# Running from a local clone: use it directly, skip the cache fetch.
here="$(cd "$(dirname "${BASH_SOURCE[0]:-}")" 2>/dev/null && pwd)" || here=""
if [ -n "$here" ] && [ -f "$here/scripts/install-agent-skills.py" ]; then
  pack="$here"
else
  if [ -d "$CACHE_DIR/.git" ]; then
    git -C "$CACHE_DIR" pull --ff-only --quiet
  else
    git clone --depth 1 --quiet "https://github.com/$REPO.git" "$CACHE_DIR"
  fi
  pack="$CACHE_DIR"
fi

target="$(pwd)"

# Auto-detect host from the target repo, unless caller already passed --host.
host_flag=()
case " $* " in
  *" --host "*|*" --skills-dir "*) ;;
  *)
    if [ -d "$target/.claude" ]; then host_flag=(--host claude)
    elif [ -d "$target/.codex" ]; then host_flag=(--host codex)
    elif [ -d "$target/.kiro" ]; then host_flag=(--host kiro --copy)
    elif [ -d "$target/.opencode" ]; then host_flag=(--host opencode)
    fi
    ;;
esac

exec python3 "$pack/scripts/install-agent-skills.py" "${host_flag[@]}" "$@" "$target"
