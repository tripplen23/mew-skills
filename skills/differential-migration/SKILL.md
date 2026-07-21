---
name: differential-migration
description: "Implements approved migration units and verifies properties against executable baseline or authorized reference oracles. Use only after an approved plan selects a mixed or differential route, or when the user explicitly requests differential testing; do not trigger for a generic implementation request."
license: MIT
metadata:
  author: tripplen23
  version: "0.2.0"
  mew-phase: IMPLEMENT+VERIFY
---

# Differential Migration

## Purpose

Implement approved units and verify each contract property with the oracle declared in the behavioral contract.

A property is differential-eligible when `oracle.kind` is `executable-baseline` or `authorized-reference`, regardless of its preservation label. This includes an `introduce` property during authorized reconstruction when an executable reference and its authorization are recorded. Run the same inputs against the oracle and candidate at the contracted boundary.

Properties with `contract-spec`, `characterization`, or `regression` oracles are not differential-eligible. Verify them with the corresponding contract, characterization, or regression test. Define the **in-scope verification set** as every approved contract property except an `unknown` property explicitly deferred by run-bound `property_deferred` decision evidence. A deferred unknown remains in the contract for traceability but has no plan-unit ownership, executable check, parity result, or contribution to parity totals. Any other `unresolved` oracle blocks implementation.

## Steps

### Step 1: Confirm the entry gate

Read the approved behavioral contract and `.mew/runs/<run-id>/migration-plan.yaml`.

Proceed only when:

- the plan is approved;
- its derived route is `mixed` or `differential`, or the user explicitly requested differential testing; and
- every property in the in-scope verification set maps to a concrete oracle and check; and
- every excluded unknown has passing run-bound `property_deferred` evidence naming its property ID and `decision: defer`.

For a `mixed` route, apply differential testing only to properties with executable oracles. Keep the non-executable properties in the same verification and parity report. Keep deferred unknowns out of both.

### Step 2: Implement pilot units

For each pilot unit, in dependency order:

1. Implement the smallest approved slice.
2. Run the target formatter, compiler or type checker, and focused unit tests.
3. Verify each property by `oracle.kind`:
   - `executable-baseline` or `authorized-reference`: run a differential comparison;
   - `contract-spec`: run the approved contract test;
   - `characterization`: replay the approved characterization test;
   - `regression`: run the approved regression test.
4. Review the source, contract, diff, and commands for missing cases.
5. Append commands, exit codes, and outcomes to `evidence.jsonl`.

Do not invent an executable oracle or silently substitute a reference that lacks recorded authorization.

### Step 3: Run differential comparisons

Feed the same corpus to the executable oracle and candidate. The runner's `--old` flag is the oracle command and `--new` is the candidate command:

```bash
python skills/differential-migration/scripts/diff_test.py \
  --old "<oracle-command>" \
  --new "<candidate-command>" \
  --corpus fixtures/replay/ \
  --normalize json_keyorder,whitespace \
  --output parity-report.json
```

Use only normalization and tolerances approved in the contract. Compare:

- exit codes and normalized outputs;
- error categories;
- observable side effects such as rows, files, and events;
- performance against approved budgets.

Pin inputs, dependencies, locale, timezone, clock, randomness, and external services where they affect results. Confirm the oracle is reproducible before trusting a mismatch.

### Step 4: Classify and resolve mismatches

Use this vocabulary in the report and schema:

- `regression` — contracted behavior differs; fix the candidate.
- `tolerance_miss` — an approved tolerance is exceeded; fix the candidate or obtain approval to amend the contract.
- `nondeterminism` — uncontrolled state makes the result unstable; control it and rerun.
- `intentional_change` — the difference matches an approved change; update the expected result and evidence.
- `deprecation` — the difference matches an approved deprecation; verify the compatibility or removal plan.
- `performance_regression` — an approved budget is exceeded; optimize or obtain approval to amend the budget.
- `provenance_break` — licensing or source provenance is invalid; block the change until resolved.
- `reproducibility_break` — the oracle or candidate cannot be reproduced in the pinned environment; repair the environment before comparison.
- `normalization_gap` — an approved normalization is missing or incorrect; fix it and rerun.
- `contract_gap` — expected behavior is unspecified; stop and obtain contract approval.

After resolution, rerun the affected property and retain the original mismatch evidence.

### Step 5: Fan out after pilot success

Expand only after pilot properties pass with reproducible evidence:

1. Implement remaining units in dependency order.
2. Keep one writer per unit and isolate concurrent work.
3. Run focused checks after each unit.
4. Run contract, integration, cross-platform where required, and full regression checks before handoff.
5. Run the target repository's formatter, linter, build, and test commands; record every exit code.

### Step 6: Produce the parity report

The report is a root object conforming to `schemas/parity-report.schema.json`. Include exactly one result for every property in the in-scope verification set, including properties verified by non-executable oracles; omit `old_output` and `new_output` when no executable comparison occurred. Do not emit results for deferred unknowns.

```yaml
run_id: <run-id>
total_properties: 45
passed: 43
mismatches: 2
verdict: conditional_pass
results:
  - property_id: P001
    status: pass
    old_output: {status: 200, body: {id: 42, name: Alice}}
    new_output: {status: 200, body: {id: 42, name: Alice}}
    normalized_equal: true
  - property_id: P015
    status: mismatch
    classification: regression
    old_output: {status: 500, body: {error: db_timeout}}
    new_output: {status: 500, body: {error: connection_failed}}
    normalized_equal: false
    investigation: "Candidate error mapping differs from the executable oracle"
performance:
  - path: GET /api/v1/users/{id}
    old_p95_ms: 45
    new_p95_ms: 48
    regression_pct: 6.7
    gate: fail
```

Check that `total_properties == len(results) == passed + mismatches` and that `results` contains exactly one entry per property in the in-scope verification set. Deferred unknowns contribute to none of these values.

### Step 7: Handoff

Present the parity report, unresolved conditions, and final evidence manifest. The manifest must identify the contract version, oracle and candidate revisions, changed units, commands and exit codes, mismatch resolutions, reviewer findings, and approved exceptions.

Every escaped defect becomes a regression test or contract property. Never weaken a check merely to obtain a pass.

## Evidence

Append one observed fact per line to `evidence.jsonl`:

```json
{
  "timestamp": "2026-07-17T12:00:00Z",
  "phase": "verify",
  "unit_id": "U001",
  "action": "diff_test",
  "result": "pass",
  "details": {"old_exit": 0, "new_exit": 0, "normalized_equal": true}
}
```
