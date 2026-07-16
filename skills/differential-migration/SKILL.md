---
name: differential-migration
description: "Implements target-language code slice by slice and verifies behavioral parity through differential testing against the old implementation. Feeds equivalent inputs to both implementations, compares observable results, and produces a parity report with a mismatch investigation queue. Use after the migration plan is built, when the user says \"implement the migration\" or \"run differential tests\", or when verifying that a port preserves behavior."
license: MIT
metadata:
  author: tripplen23
  version: "0.1.0"
  mew-phase: IMPLEMENT+VERIFY
---

# Differential Migration

## Purpose

Implement the target-language code one unit at a time and prove behavioral parity through differential testing. The old implementation is the oracle; disagreement produces a precise investigation queue.

## Steps

### Step 1: Load the migration plan

Read `.mew/runs/<run-id>/migration-plan.yaml`. If no plan exists, run migration-planner first.

### Step 2: Implement pilot units

For each pilot unit (in order):

1. **Implement**: Write the target-language code for the unit. Follow the semantic map for risky patterns. Use the policies in `policies/` for SDK selection, command safety, network, and secrets.
2. **Self-check**: Run the target-language compiler/type checker. Fix errors.
3. **Unit test**: Run unit tests for the changed module.
4. **Contract test**: Run contract tests at public boundaries (the properties from the behavioral contract).
5. **Differential test**: Feed equivalent inputs to old and new implementations. Compare observable results using the normalization rules from the contract.
6. **Fresh-context review**: A reviewer agent sees only the contract, source, diff, and check commands — not the author's reasoning. It searches for counterexamples and names missing tests.

### Step 3: Differential testing

Run old and new implementations on the same input corpus:

```bash
# Example: comparing API responses
python scripts/diff_test.py \
  --old "python -m src.api" \
  --new "./target/bin/api" \
  --corpus fixtures/replay/ \
  --normalize json_keyorder,whitespace,timestamp_1s \
  --output parity-report.json
```

Compare:
- Exit codes
- Normalized output (stdout, stderr, response body)
- Error categories
- Side effects (database rows, files, events)
- Timing (within performance budget)

### Step 4: Handle mismatches

For each mismatch:

1. **Investigate**: Is it a real behavioral difference or a normalization issue?
2. **Classify**: 
   - `intentional_change` — covered by the contract's intentional_changes list
   - `normalization_gap` — the normalization rule needs adjustment
   - `regression` — the new implementation is wrong
   - `contract_gap` — the contract missed this behavior
3. **Fix**: 
   - `regression` → fix the new implementation
   - `contract_gap` → update the contract (requires human approval)
   - `normalization_gap` → fix the normalization rule
   - `intentional_change` → mark as expected
4. **Re-run**: After each fix, re-run the differential test for the affected unit.

### Step 5: Fan out (after pilot success)

Only after all pilot units pass with stable, reproducible evidence:

1. Implement remaining units in dependency order.
2. Use isolated worktrees per writer.
3. Require atomic commits with source IDs, contract rules, checks run, and reviewer results.
4. Run widening test circles: unit → contract → integration → cross-platform → full regression.

### Step 6: Produce parity report

```yaml
parity_report:
  run_id: <run-id>
  total_properties: 45
  passed: 43
  mismatches: 2
  verdict: conditional_pass

  results:
    - property_id: P001
      status: pass
      old_output: { status: 200, body: { id: 42, name: "Alice" } }
      new_output: { status: 200, body: { id: 42, name: "Alice" } }
      normalized_equal: true

    - property_id: P015
      status: mismatch
      classification: regression
      old_output: { status: 500, body: { error: "db_timeout" } }
      new_output: { status: 500, body: { error: "connection_failed" } }
      investigation: "Error message differs — new impl uses different DB driver error mapping"

  performance:
    - path: GET /api/v1/users/{id}
      old_p95_ms: 45
      new_p95_ms: 48
      regression_pct: 6.7
      gate: FAIL  # exceeds 5% budget
```

### Step 7: Handoff

After the parity report passes all gates:
1. Present the report to the user.
2. List any conditional passes and their conditions.
3. Record all escaped defects as new contract properties or semantic-map rules.
4. Produce a final evidence manifest with: contract version, source/target commits, changed units, commands and exit codes, differential mismatches, reviewer findings, approved exceptions.

## Gotchas

- **A green test suite is not proof of parity.** Bun's rewrite passed 99.8% of tests but had 19 production regressions. Differential testing catches what unit tests miss.
- **debug_assert! side effects disappear in release builds.** Test in both debug and release modes.
- **Byte-slice and bounds behavior differs across languages.** UTF-16 odd-length slicing crashed Bun. Test boundary values explicitly.
- **Separate test authorship from implementation.** One agent derives edge cases from the contract; another writes the port. Lock approved tests against modification.
- **Optimize for verified units per hour, not lines per minute.** High generation throughput with a growing integration queue is negative progress.
- **Each escaped defect becomes a permanent test and a new semantic-map rule.** A migration is complete when the new implementation is operable and the team has learned from it.

## Evidence

Every step must append to `evidence.jsonl`:

```json
{
  "timestamp": "2026-07-17T12:00:00Z",
  "phase": "differential_test",
  "unit_id": "U001",
  "action": "diff_test",
  "result": "pass",
  "details": { "old_exit": 0, "new_exit": 0, "normalized_equal": true }
}
```
