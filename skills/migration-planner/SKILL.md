---
name: migration-planner
description: "Builds a migration plan from a behavioral contract. Creates a semantic map for risky source-to-target patterns, selects pilot slices, defines migration units aligned with the dependency graph, and sets stop conditions and performance budgets. Use after the behavioral contract is approved, when the user says \"plan the migration\" or \"build the migration plan\", or before implementing any target-language code."
license: MIT
metadata:
  author: tripplen23
  version: "0.1.0"
  mew-phase: MIGRATION_PLAN
---

# Migration Planner

## Purpose

Convert the approved behavioral contract into a concrete, executable migration plan. The plan defines what gets migrated, in what order, with what risk mitigation, and when to stop.

## Steps

### Step 1: Load the contract

Read `.mew/runs/<run-id>/behavioral-contract.yaml`. If no approved contract exists, run behavior-contract first and obtain human approval.

### Step 2: Build the semantic map

Create `semantic-map.yaml` that maps recurring source-language patterns to target-language equivalents. Cover the high-risk translation categories:

1. **Ownership and lifetimes**: How source manages memory → target equivalent
2. **Nullable values**: How source handles null/None/nil → target equivalent
3. **Exceptions and errors**: Source exception hierarchy → target error handling
4. **Integer overflow**: Source behavior → target behavior
5. **Time calculations**: Timezone handling, epoch, duration
6. **String encodings**: UTF-8, UTF-16, byte slices
7. **Concurrency primitives**: Threads, async, channels, locks
8. **Allocator ownership**: Custom allocators, memory pools
9. **FFI boundaries**: Foreign function interfaces
10. **Debug/release behavior**: Assertions, optimization-dependent behavior
11. **Platform-specific code**: OS conditionals

For each mapping, include:
- Source pattern (with example)
- Target pattern (with example)
- Risk level (low/medium/high)
- Known gotchas

### Step 3: Select pilot slices

Scale the pilot count to the request mode. A bounded `feature_adoption`
normally needs one vertical slice. A `framework_migration` starts with one
public boundary. A broad `language_port` may use up to three units covering
different failure modes:

1. **Simple representative unit**: A leaf module with no dependencies. Tests mechanical translation.
2. **Dependency-heavy unit**: A module with database or I/O effects. Tests side-effect preservation.
3. **Semantic hotspot**: A module with tricky logic (concurrency, edge cases, error handling). Tests the semantic map.

Every pilot must include a representative edge case or failure path. Do not
inject a synthetic defect into production source merely to make the pilot
"difficult"; use a fixture or mutation test when proving that verification can
catch a subtle difference.

### Step 4: Define migration units

Break the full migration into units aligned with the dependency graph. Use the **Strangler Fig** pattern (Fowler, 2004): new functionality is built on top of, yet separate to the legacy code base, and behavior is moved piece by piece. "Wholesale replacements go down in flames most of the time."

For Python-to-Rust migrations, use **Branch By Abstraction** (Fowler): introduce a PyO3/maturin seam — keep the Python entrypoint, implement the slice in Rust, expose it via PyO3 as `_module._slice`, and route the Python code to call it. Run the full characterization + differential suite after each slice. The transitional Python-to-Rust dispatch code is expected and will be deleted at the end.

```yaml
units:
  - id: U001
    name: "currency formatter"
    source_paths: [src/format/currency.py]
    target_paths: [src/format/currency.rs]
    depends_on: []
    contract_properties: [P001, P002]
    risk: low
    pilot: true

  - id: U002
    name: "idempotency repository"
    source_paths: [src/db/idempotency.py]
    target_paths: [src/db/idempotency.rs]
    depends_on: [U001]
    contract_properties: [P010, P011, P012]
    risk: medium
    pilot: true
```

### Step 5: Set stop conditions

Define hard stop conditions that halt fan-out:

```yaml
stop_conditions:
  - "Pilot mismatch rate exceeds 20%"
  - "Workers repeatedly modify global tests"
  - "Compiler queue grows faster than it closes for 3 consecutive rounds"
  - "Target performance misses budget by >2x"
  - "Rollback artifact cannot be built"
```

### Step 6: Set performance budgets

From the behavioral contract's performance_budgets section, define concrete gates:

```yaml
performance_gates:
  - path: GET /api/v1/users/{id}
    p95_regression_max_pct: 5
    p99_regression_max_pct: 10
    peak_memory_regression_max_pct: 15
```

### Step 7: Define worker policy

```yaml
worker_policy:
  isolation: ephemeral_worktree
  one_writer_per_unit: true
  forbidden_commands:
    - "git reset --hard"
    - "git stash"
    - "git push --force"
  editable_paths: ["src/", "tests/migration/"]
  protected_paths:
    - "tests/contracts/"
    - ".mew/runs/*/behavioral-contract.yaml"
```

### Step 8: Write artifact

Produce `migration-plan.yaml` combining all of the above.

## Gotchas

- **Do not force three pilots onto a small feature adoption.** One minimal
  vertical slice with complete contract coverage is stronger evidence than
  three artificial units that inflate context and implementation scope.
- **Don't choose only easy files for the pilot.** A pilot that passes only clean examples has not been tested. Include a semantic hotspot.
- **File-level division may be wrong.** When behavior spans modules, use module-level or feature-level units instead.
- **Lock contract tests against modification by implementation workers.** An agent should not "solve" a failing test by weakening the requirement.
- **Version the semantic map.** A newly discovered mismatch should update the rule and trigger targeted re-verification of affected units.
- **Stop conditions protect against sunk-cost escalation.** Do not remove them mid-run to "unblock" progress.

## Output format

See `schemas/migration-plan.schema.json` for the full schema.
