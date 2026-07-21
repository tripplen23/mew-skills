---
name: behavior-contract
description: "Builds the behavioral contract for migration, authorized reconstruction, or feature adoption. Captures existing behavior, specifies requested behavior, labels each property, and records the oracle that will verify it. Use after repository mapping and before planning."
license: MIT
metadata:
  author: tripplen23
  version: "0.2.0"
  mew-phase: OBSERVE+CONTRACT
---

# Behavior Contract

## Purpose

Turn the repo inventory and desired evolution into an explicit, human-approved behavioral contract. The contract separates existing behavior, new behavior, intentional changes, and historical accidents. It records which oracle can judge each property; it does not assume every property has an executable old implementation.

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
6. **Streaming / event interfaces**: For SSE, WebSocket, or any incremental output, capture the *sequence and interleaving* of events against the running system, not just the final content. Order and grouping (e.g. text vs tool-call events) are observable behavior. Observe the live stream end to end — a green unit suite does not prove the consumer renders stream order faithfully.

Use `scripts/capture_behavior.py` to automate capture for common patterns. For custom systems, write a capture script specific to the project.

For a **feature adoption or reconstruction**, separate three evidence classes:

1. current target behavior, which may provide executable baseline, characterization, or regression oracles;
2. requested target behavior, labeled `introduce`; use `contract-spec` by default, or `authorized-reference` only when an executable reference and authorization are recorded;
3. other references, which remain design evidence and do not redefine target behavior.

Pin reference revisions, record their licenses, and prefer official API and SDK
documentation over reverse-engineered community behavior. If the requested
provider or SDK has no supported official path, record a blocker instead of
claiming compatibility from a nominally similar endpoint.

**Characterization tests / golden master** (Feathers, *Working Effectively with Legacy Code*, 2004, Ch. 13): Run the source over a corpus of inputs; serialize outputs to a canonical, deterministic form (sorted keys, fixed `PYTHONHASHSEED`, `allow_nan=False` in JSON). Store the corpus + outputs as the golden master. Characterization tests are *intentionally bug-preserving* — do not "fix" observed behavior while characterizing.

**Metamorphic testing** (Chen et al., ACM Computing Surveys 51(1), 2018): When the source has no ground-truth oracle (numerical/simulation/ML code), identify metamorphic relations (MRs) — necessary properties relating multiple inputs and their outputs. Examples: `f(x) == f(-x)` for even functions; `decode(encode(x)) == x` for round-trips; `sort(x ++ y) == sort(y ++ x)`. Encode MRs as executable checks; they survive the migration because they are input-relative, not output-literal.

### Step 3: Build the property list

For each existing or requested behavior, create a contract property entry with a structured `oracle`; keep captured observations in `evidence`:

```yaml
- id: P001
  surface: api
  path: GET /api/v1/users/{id}
  property: "Returns 200 with user object when user exists"
  preservation: preserve
  oracle:
    kind: executable-baseline
    command: "curl --fail http://baseline/api/v1/users/42"
  evidence:
    input: { id: 42 }
    output: { status: 200, body: { id: 42, name: "Alice" } }
    capture_method: live_request

- id: P002
  surface: api
  path: POST /api/v1/chat:stream
  property: "Emits text chunks in generation order"
  preservation: introduce
  oracle:
    kind: contract-spec
    assertion: "received chunk sequence equals generated chunk sequence"
```

Allowed oracle kinds are `executable-baseline`, `authorized-reference`, `characterization`, `regression`, `contract-spec`, and `unresolved`. `authorized-reference` requires explicit authorization evidence; `unresolved` is valid only while the property remains `unknown`.

### Step 4: Label each property

Assign one of five labels:

- **preserve**: Existing observable behavior must remain equivalent. Use an executable baseline when available; otherwise pin a characterization or regression oracle.
- **introduce**: Brand-new target behavior. Use `contract-spec` unless an explicitly authorized executable reference provides the comparison oracle.
- **intentionally-change**: Existing behavior is deliberately altered. Requires human approval, a reason, and old/new expectations.
- **deprecate**: Existing behavior is being removed. Requires human approval.
- **unknown**: Cannot determine whether behavior is intentional. Becomes a discovery task — run the system, search issues, ask maintainers.

Unknowns are NOT permission to guess. They must be resolved before the contract is approved.

### Step 5: Identify intentional changes

List all properties labeled `intentionally-change` with:
- What changes
- Why it changes (e.g., "replacing Python-specific debug header with standard X-Request-ID")
- What the new behavior will be
- Risk level (low/medium/high)

### Step 6: Human approval gate

Present the contract to the user. The user must approve:
1. The set of `preserve` properties and their oracles
2. The set of `introduce` properties and their contract-test assertions
3. Each `intentionally-change` and `deprecate` decision
4. Resolution of all `unknown` properties

When this skill is invoked by `mew-migration`, write a schema-valid draft without `approved_by` / `approved_at`, return control for planning, and let the orchestrator run one combined contract-and-plan approval gate. After approval, populate both fields before implementation. When used standalone, request approval here before planning.

### Step 7: Write artifacts

- `behavioral-contract.yaml` — the full contract with all properties and labels
- Append capture evidence to `evidence.jsonl`

## Gotchas

- **Describe behavior, not implementation.** Internal structure may change; observable properties require explicit labels and oracles.
- **Order and side effects are behavior.** Include stream/event order, database writes, files, logs, and emitted events when users can observe them.
- **References are design evidence by default.** Use `authorized-reference` only with recorded authorization and an executable comparison.
- **Make equivalence explicit.** Record normalization, tolerances, locale, timezone, clock, randomness, and serialization rules before comparing outputs.
- **Use measurable budgets.** Add performance properties only when users depend on them, and approve limits before implementation.

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
    oracle:
      kind: executable-baseline
      command: "curl --fail http://baseline/api/v1/users/42"
    evidence: { ... }

  - id: P002
    surface: api
    path: GET /api/v1/users/{id}
    property: "Returns 404 with {error: 'not_found'} when user does not exist"
    preservation: preserve
    oracle:
      kind: regression
      assertion: "missing user returns status 404 and error=not_found"
    evidence: { ... }

intentional_changes:
  - id: C001
    property_ref: P010
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
```
