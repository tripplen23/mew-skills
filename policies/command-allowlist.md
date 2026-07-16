# Command Allowlist Policy

## Rule

Implementation agents may only run safe, non-destructive shell commands. Destructive and coordination commands are forbidden for leaf workers.

## Allowed commands

```bash
# Compilation and type checking
cargo build, cargo check, cargo test, cargo clippy
go build, go test, go vet
python -m pytest, python -m mypy
npm test, npx tsc

# File operations (within editable_paths)
cat, ls, head, tail, wc, diff
mkdir, cp, mv (within worktree)

# Git (read-only)
git status, git diff, git log, git show, git branch

# Git (write, non-destructive)
git add, git commit, git checkout -b
```

## Forbidden commands (for leaf workers)

```bash
git reset --hard
git stash
git stash pop
git push --force
git rebase
rm -rf (outside worktree)
```

## Rationale

Bun's first large-scale parallel run failed because agents used `git stash`, `stash pop`, and `git reset --hard` in a shared workspace and destroyed each other's changes. Parallel coding is a distributed-systems problem: shared state, conflicting writers, and expensive global operations need explicit rules.

## Coordinator-only commands

A coordinator agent (not a leaf worker) may run:
- `git merge` (ordered integration)
- `git rebase` (with approval)
- `cargo check` across the full workspace (global compilation)

## Enforcement

The worker_policy in the migration plan specifies editable_paths and protected_paths. Commands outside editable_paths or touching protected_paths are blocked.
