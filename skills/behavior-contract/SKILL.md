---
name: behavior-contract
description: "Extracts behavioral DNA from a running system and produces a behavioral contract that defines what a migration must preserve. Labels each property as preserve, intentionally-change, deprecate, or unknown. Runs the system against representative inputs to capture observable behavior. Use after repo-cartographer has completed, when the user says \"extract behavior\" or \"build the contract\", or before planning a migration that must not break existing functionality."
license: MIT
metadata:
  author: tripplen23
  version: "0.1.0"
  mew-phase: OBSERVE+CONTRACT
---

# Behavior Contract

## Purpose

Turn the repo inventory into an explicit, human-approved behavioral contract. The contract separates intentional behavior from historical accidents. It is the oracle that differential testing checks against.

## Steps

### Step 1: Load repo inventory

Read `.mew/runs/<run-id>/repo-inventory.yaml` produced by repo-cartographer. If no run exists, run repo-cartographer first.

### Step 2: Capture observable behavior

For each surface in the inventory, capture actual behavior by running the system:

1. **API endpoints**: Send representative requests (happy path, edge cases, error cases). Record exact response status, headers, body, and timing.
2. **CLI commands**: Run each command with representative arguments. Record stdout, stderr, exit code.
3. **Database effects**: Run operations against a test database. Record resulting rows, emitted events, side effects.
4. **File I/O**: Record what files are read, written, and in what format.
5. **Error paths**: Trigger each error condition. Record exact error message and behavior.

Use `scripts/capture_behavior.py` to automate capture for common patterns. For custom systems, write a capture script specific to the project.

### Step 3: Build the property list

For each observed behavior, create a contract property entry:

```yaml
- id: P001
  surface: api
  path: GET /api/v1/users/{id}
  property: "Returns 200 with user object when user exists"
  preservation: preserve
  evidence:
    input: { id: 42 }
    output: { status: 200, body: { id: 42, name: "Alice" } }
    capture_method: live_request
```

### Step 4: Label each property

Assign one of four labels:

- **preserve**: The new implementation must produce equivalent observable behavior. This is the default.
- **intentionally-change**: The migration deliberately alters this behavior. Requires human approval and a reason.
- **deprecate**: The behavior is being removed. Requires human approval.
- **unknown**: Cannot determine if behavior is intentional. Becomes a discovery task — run the system, search issues, ask maintainers.

Unknowns are NOT permission to guess. They must be resolved before the contract is approved.

### Step 5: Identify intentional changes

List all properties labeled `intentionally-change` with:
- What changes
- Why it changes (e.g., "replacing Python-specific debug header with standard X-Request-ID")
- What the new behavior will be
- Risk level (low/medium/high)

### Step 6: Human approval gate

Present the contract to the user. The user must approve:
1. The set of `preserve` properties
2. Each `intentionally-change` and `deprecate` decision
3. Resolution of all `unknown` properties

Do NOT proceed to migration planning until the contract is approved. Save the approval as an evidence entry.

### Step 7: Write artifacts

- `behavioral-contract.yaml` — the full contract with all properties and labels
- Append capture evidence to `evidence.jsonl`

## Gotchas

- **Capture behavior, not code structure.** The contract describes what the system does, not how it does it. Internal refactoring is allowed; observable behavior changes require approval.
- **Normalization rules must be explicit.** If you compare outputs, define exactly what counts as equivalent (e.g., "JSON key order may differ, whitespace may differ, timestamps must match within 1 second").
- **Side effects are behavior.** Database writes, file creation, event emission, log output — all are part of the behavioral contract.
- **Performance can be behavior.** If users depend on response time, include a latency budget in the contract. Set budgets before migration so regressions cannot be rationalized away.
- **debug_assert vs assert.** A side effect inside debug_assert! disappears in release builds. The contract must specify whether assertion behavior is preserved or intentionally changed.

## Output format

See `schemas/behavioral-contract.schema.json` for the full schema.

```yaml
contract_id: <run-id>
source_commit: <sha>
approved_by: <user>
approved_at: <ISO timestamp>

properties:
  - id: P001
    surface: api
    path: GET /api/v1/users/{id}
    property: "Returns 200 with user object when user exists"
    preservation: preserve
    evidence: { ... }

  - id: P002
    surface: api
    path: GET /api/v1/users/{id}
    property: "Returns 404 with {error: 'not_found'} when user does not exist"
    preservation: preserve
    evidence: { ... }

intentional_changes:
  - id: C001
    property: P010
    what: "Replace X-Debug header with X-Request-ID"
    why: "Python-specific, not needed in Go"
    risk: low
    approved: true

normalization_rules:
  - "JSON key order may differ"
  - "Whitespace in JSON output may differ"
  - "Timestamps must match within 1 second"

performance_budgets:
  - path: GET /api/v1/users/{id}
    p95_ms: 50
    p99_ms: 100
