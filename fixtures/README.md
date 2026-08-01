# Regression fixtures — earned from real failures

Every **hard-oracle skill change** must ship a regression fixture: a test
that **fails before the fix** and **passes after**. This directory is the
registry + runner contract (mew#106).

## Fixture format

Each fixture is a directory under `fixtures/<id>/` containing:

| file | required | purpose |
|---|---|---|
| `fixture.json` | yes | metadata (schema below) |
| `gate.sh` | yes | pass/fail gate: exit 0 = pass, non-zero = fail |
| `README.md` | no | human context: what failed, which run, what fix |

### fixture.json schema

```json
{
  "id": "http-diff-normalize",
  "skill": "differential-migration",
  "oracle_tier": "hard",
  "linked_lesson": "L-http-diff",
  "run_id": "20260801-145954-217cab5",
  "fails_before": "commit <sha of pre-fix state>",
  "passes_after": "commit <sha of fix>",
  "description": "HTTP differential harness normalizes timestamps only for UTC offsets",
  "gate_command": "bash gate.sh"
}
```

- `fails_before` / `passes_after` are **provenance**: the fixture must have
  actually failed on the pre-fix tree and passed on the fixed tree in a
  real run — not be written after the fact.
- `oracle_tier` must be `hard` (soft-oracle lessons never get fixtures).

## Runner

```
bash scripts/run_fixtures.sh [fixture-id ...]
```

- Discovers every `fixtures/*/fixture.json`.
- Executes each `gate_command` with cwd = fixture dir.
- Prints `PASS <id>` / `FAIL <id>`; exits 1 if any fixture fails.
- Wired into `scripts/validate.sh` so a broken fixture blocks the pack.

## Pruning rules

1. **Stale**: fixture whose linked lesson was superseded/merged — remove
   the fixture in the same commit that merges the lesson (no orphans).
2. **Absorbed**: fixture duplicating another fixture's failure class —
   keep the one with the stricter gate, delete the other.
3. **Rot**: a fixture that has not run in 20 consecutive `validate.sh`
   passes is flagged; if its gate no longer fails on the pre-fix
   behavior it was earned from, it is pruned (it stopped being a
   regression guard).
4. Every prune must be a reviewable commit with the reason in the message.

## Current fixtures

| id | skill | linked lesson | gate |
|---|---|---|---|
| `http-diff-normalize` | differential-migration | L-http-diff | `http-diff` smoke: 2 pass + 2 designed-fail |
| `timestamp-format-utc` | migration-planner | L-timestamp-utc | `timestamp_format_check.py` (4 checks) |
