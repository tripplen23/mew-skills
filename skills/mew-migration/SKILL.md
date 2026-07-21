---
name: mew-migration
description: "Orchestrates and resumes evidence-driven migrations, authorized reconstructions, clones, and feature adoptions. Use when the user asks to migrate, port, rewrite, transplant, reproduce, continue, recover, or inspect unfinished Mew work. Classifies oracle presence, selects contract-only, mixed, or differential verification, keeps a durable progress view across compaction and sessions, and stops for human approval before implementation."
license: MIT
compatibility: "OpenCode, Kiro, Hermes, and Agent Skills-compatible clients"
metadata:
  author: tripplen23
  version: "0.6.0"
  mew-phase: END_TO_END
---

# Mew Migration

Turn a migration, reconstruction, clone, or feature-adoption request into a bounded Mew run. This skill owns orchestration; the phase skills own specialized reasoning. Do not make the user restate the workflow, artifact paths, schemas, or phase order.

## When to use

Load this skill when the user asks to:

- migrate or port an implementation while preserving behavior;
- reconstruct or clone an authorized app, system, workflow, or individual feature from observable behavior;
- reproduce a UX or protocol in a target repository without treating the reference as the preservation oracle;
- replace a framework, language, SDK, service, or provider;
- adopt a capability from one or more reference implementations;
- resume, inspect, or recover an unfinished Mew run after compaction, handoff, or a new session;
- sync stale progress with approved artifacts and verification evidence;
- rewrite a subsystem with evidence-backed parity;
- run the complete Mew workflow rather than one isolated phase.

If the target has project-local adopted notes, resolve and apply them through `references/project-notes.md`. Ignore notes for other repositories and do not make local obligations universal.

For reconstructing a running system (web, TUI, mobile, desktop, device, etc), load `observation` as the observation driver. For a single already-established phase, use that phase skill directly.

## Minimum input

Only two fields are required:

1. **Target repository** — path to the repository that will change. If the host agent is running inside that repository, use the current git root.
2. **Desired evolution** — one sentence describing the intended capability or replacement.

Everything else is optional:

- reference repositories or URLs;
- paths included or excluded from scope;
- compatibility constraints;
- required providers, SDKs, languages, or platforms;
- explicit performance or resource budgets.

During intake, ask one concise clarification only when a required field cannot
be inferred. Do not ask the user for a run ID, artifact directory, phase
sequence, schemas, test commands discoverable from the repo, or a complete
acceptance-criteria list. The later grill phase is separate: after evidence is
collected, it asks only decision questions that the repository and references
cannot answer.

## Quick start

A sufficient request is:

```text
Use mew-migration to add <capability> to this target repository while preserving
its existing behavior. Treat <reference URL or repository> as design evidence,
prefer official SDKs, and keep the change minimal.
```

From this, infer the current git root as the target, create the run directory, inspect the target and references, draft the contract and plan, then stop for approval. Do not require a phase-by-phase prompt.

## Run defaults

Unless the user overrides them:

- Run root: `<target>/.mew/runs/<run-id>/`
- Run ID: UTC timestamp plus locked short SHA, `YYYYMMDD-HHMMSS-<7chars>`
- Baseline: immutable worktree at the locked target commit
- Candidate: separate writable worktree or branch
- Preservation default: all existing observable behavior
- Change default: only the requested evolution
- Builder mode: supervised
- Network: deny except approved documentation, source, and dependency endpoints
- SDK selection: official SDK first; record any exception
- Implementation gate: human approval of the contract and migration plan
- Durable progress: `run-state.json`, refreshed from canonical artifacts and evidence

Write a `migration-request.json` first and validate it against `schemas/migration-request.schema.json`. Record inferred values explicitly so the user can correct them. Decompose every top-level requested capability into a stable `W###` item in `run-state.json` and append one `work_items_initialized` evidence entry before mapping or implementation.

## Scope modes

Choose the smallest mode that fits the request:

| Mode                  | Use when                                                                         | Pilot default                         |
| --------------------- | -------------------------------------------------------------------------------- | ------------------------------------- |
| `feature_adoption`    | Add a capability to the existing implementation, possibly informed by references | One vertical slice                    |
| `language_port`       | Replace code in one language with another                                        | Up to three representative slices     |
| `framework_migration` | Replace a framework or platform while retaining public behavior                  | One boundary-first slice, then expand |
| `reconstruction`      | Rebuild an authorized application from observations                              | One approved journey                  |

Do not force three pilot units onto a bounded feature adoption. Scale inventory, evidence, and testing to the observable surfaces affected by the request.

## Verification route: oracle presence

Classify each contract property by its structured `oracle.kind` before loading an implementation skill:

- `contract-spec`, `characterization`, or `regression` — deterministic checks without an old-vs-new executable comparison.
- `executable-baseline` — replayable target baseline suitable for differential testing.
- `authorized-reference` — an explicitly authorized, executable original suitable for reconstruction parity; the property may remain `introduce` relative to the target while still being differential-eligible.
- `unresolved` — valid only for an `unknown` property. Resolve it before approval or exclude it from verification with passing run-bound `property_deferred` evidence naming the property and `decision: defer`.

Define the **in-scope verification set** as every approved contract property, including preservation properties, except explicitly deferred unknowns. A deferred unknown remains in the contract for traceability but has no plan-unit ownership, check, parity result, or contribution to parity totals. After drafting the contract, derive a provisional route; after building the plan, finalize it from every property in this set and record the decision in `evidence.jsonl` and the approval summary:

- **`contract-only`** — no property in the set has an `executable-baseline` or `authorized-reference` oracle. This covers greenfield `introduce` properties and existing behavior verified by characterization/regression tests. Do not load `differential-migration`.
- **`mixed`** — some properties in the set have executable baseline/reference oracles and others use contract, characterization, or regression oracles. Load differential guidance for every executable property, including executable preservation properties.
- **`differential`** — all properties in the set are judged against executable baseline/reference oracles. Differential testing is the primary parity signal.

Derive the route from the contract's oracle objects and the plan's in-scope property set; do not add a second editable `verification_route` field that can drift. Keep every route's common gates: contract, approval, provenance, `analyze_run`, regression checks, and a parity report. An external reference is design evidence by default and becomes an `authorized-reference` oracle only when authorization is recorded explicitly.

Common mixed case: adding streaming to an endpoint that already returns a non-streaming response. `assemble(stream(input)) == old_response(input)` is an executable oracle for the assembled result, while chunk ordering, flush cadence, mid-stream errors, and cancellation are introduced properties verified by contract tests.

## Parallel execution policy

Keep the evidence and decision spine sequential: baseline lock, contract merge and grill, human approval, all designated pilot units in dependency order, shared protocol/schema/data changes, deterministic merge, and final verification. Parallelism must not let workers redefine scope, approve behavior, or write the same canonical artifact.

Parallelize only independent leaves:

- After scope and revisions are pinned, inspect separate references, map independent target surfaces, and run isolated observation scenarios concurrently. Workers return evidence fragments; the orchestrator serializes updates to the contract, plan, and `evidence.jsonl`.
- After every designated pilot passes, run dependency-ready non-pilot units concurrently when all `depends_on` units passed, normalized repository-relative `target_paths` do not overlap, mutable test resources are isolated, and each unit has one writer. A directory overlaps its descendants; resolved aliases and undeclared generated writes require serialization.
- Treat shared protocols, schemas, database state, generated outputs, lock/build files, benchmarks, and integration tests as ordering constraints. Add `depends_on` edges when path separation alone does not express the conflict.
- Merge completed units in deterministic dependency order, rerun affected checks after each merge or wave, and block failed units plus their dependents without discarding valid evidence from unrelated units.

Derive execution waves from the existing plan; do not add `parallel_groups` or a scheduler field unless a real run proves that dependencies and resource isolation cannot express the conflict.

## Resume and progress sync

Treat `run-state.json` as a mutable progress view, not an approval-bearing source of truth. Approved request, contract, and plan define intended work; parity, validation, and append-only evidence prove completed work; repository code is corroborating evidence. Conversation history is never durable state.

At every invocation, compaction return, or session handoff, classify intent from the request and repository context rather than matching a magic phrase:

1. A clear new migration request creates a new run.
2. Continuation, remaining-work, or recovery intent scans `.mew/runs/*/run-state.json` for relevant unfinished root runs. A root state has no `parent`.
3. Resume the single relevant root. If multiple roots plausibly match, present their IDs and goals for selection; never choose only by newest timestamp.
4. Load its `focus_item`, referenced child runs, approved artifacts, and relevant evidence before selecting work.
5. Legacy runs without state require an explicit progress-sync proposal; do not infer completion silently.

Sync progress before continuing:

- Restore any item recorded by `work_items_initialized` or `work_item_added` that disappeared from state.
- Add or repair a child link only when both parent and child artifacts identify the relationship unambiguously.
- Mark an item `done` only when its approved scope has passing parity and required validation evidence. Code or tests merely existing is not completion. Append run-bound `work_item_done` with exact `contract_properties`, `plan_units`, `run_refs`, and SHA-256 hashes of contract, plan, and parity before changing the status.
- Keep implemented but unverified work `in_progress` with verification as `next_action`. Use `blocked` when ownership, approval, or evidence is ambiguous.
- Downgrade stale `done` state when its completion evidence no longer passes.
- Record every automatic repair as `progress_synced` in `evidence.jsonl`; ask only when the repair is not deterministic.

For a multi-capability program, keep the root work-item ledger in the original run. A separately approved capability run writes `parent.run_id` plus `parent.item_id`; the parent item records the child ID in `run_refs`. Child completion does not complete broader parent scope that the child explicitly deferred. Parallel workers never write state; the coordinator serializes state and evidence updates.

Update state after approval, work start, verification, defer/cancel decisions, and before compaction or handoff. Never delete a work item: mark it `deferred` or `cancelled` with human decision evidence. Keep at most one `focus_item`, but allow multiple `in_progress` items when the parallel policy permits them.

## Workflow

### 1. Intake and lock

1. Resolve the target git root and desired evolution.
2. Verify the target is a git repository and record `HEAD`, branch, remotes, and dirty state.
3. Observation may begin on a dirty tree, but do not establish a baseline or edit until the user resolves uncommitted changes.
4. Create the run directory and `migration-request.json`.
5. Create `manifest.json`, `repro.json`, `provenance.json`, and `evidence.jsonl`.
6. Create `run-state.json` from every top-level requested capability, validate it against `schemas/run-state.schema.json`, append run-bound `work_items_initialized`, and hash the exact request bytes into `request_sha256`.
7. Record the skill-pack commit and all reference revisions used.

### 2. Map the target

Load `repo-cartographer`. Apply it to the target surfaces affected by the desired evolution, then widen only when dependencies or public contracts require it.

For a feature adoption, map both:

- the target's current boundary and invariants;
- the extension seam where the new capability can enter minimally.

Produce `repo-inventory.yaml`. Do not inventory unrelated subsystems merely to make the artifact look comprehensive.

### 3. Observe target and references

Load `behavior-contract` for target behavior. References are design evidence, not the behavioral oracle.

For each named reference, follow `references/reference-inspection.md`: pin it, inspect primary artifacts rather than search snippets, record license/provenance, separate portable behavior from implementation choices, and write `reference-<name>.md` plus evidence before implementation. Stop on unresolved authorization or licensing.

If a project-local adopted-skill note adds domain-specific reference-analysis
questions, answer them before implementation. Otherwise use the generic
reference-inspection format only.

The target's existing behavior remains the oracle for preservation properties. The requested evolution defines new target properties. A reference does not silently redefine either.

### 4. Grill the request

Before drafting the contract, resolve ambiguity by interviewing the user — do
not silently pick an interpretation. Misalignment is the most expensive failure
mode: a wrong scope or a wrong assumption surfaces only after implementation.

Ask targeted questions, then stop for answers. Cover at minimum:

- **Scope boundaries** — is every capability in the request in scope, or should
  some be deferred? (A request naming two providers may only want one now.)
- **Reachability** — for every concrete item the request implies (a model, an
  endpoint, an API surface), is it actually reachable through the intended path?
  Do not add a curated item you cannot show works end to end.
- **Naming and identity** — will new names collide with or shadow existing ones?
  Propose renames explicitly rather than reusing an overloaded term.
- **Compatibility** — what existing behavior must stay byte-for-byte identical?
- **Verification** — discover formatter, linter, and test commands from project files and CI. Ask the user only if the repository leaves competing or ambiguous gates.

Grill only until the decision tree is resolved; do not interrogate settled
points. Record answers in `evidence.jsonl` with a `grill` action. A request that
sounds specific is not the same as a resolved one — the initial wording is a
starting point, not the contract.

### 5. Draft the contract

Produce `behavioral-contract.yaml` containing:

- existing properties that must remain unchanged, labeled `preserve`;
- new properties required by the desired evolution, labeled `introduce`;
- intentional changes, if any;
- unknowns and blockers;
- exact normalization and tolerance rules;
- the structured oracle for each property (`kind` plus executable command, artifact, assertion, or authorization evidence as applicable);
- tests or observations supporting each property.

Derive the provisional verification route now. Do not wait until implementation to discover that a supposed differential oracle cannot be executed.

If a project-local adopted-skill note adds contract checklist items, include
them and cite the note in `evidence.jsonl`. Otherwise keep the contract generic.

### 6. Build the minimal plan

Load `migration-planner`. Produce `migration-plan.yaml` using the selected scope mode.

A minimal feature-adoption plan should normally contain:

- one extension seam;
- one pilot unit;
- focused protocol/config/runtime changes;
- regression tests for the old default;
- contract tests for each new capability;
- stop conditions for unsupported official APIs, licensing conflicts, or auth assumptions.

Do not add abstractions, provider registries, fallback systems, or dependencies unless a contract property requires them.

If a project-local adopted-skill note adds plan requirements, include them only
when they apply to the approved scope.

### 7. Human approval gate

Finalize the verification route from the contract and pilot plan. Stop after both artifacts are schema-valid **and mutually consistent**: run `python3 scripts/analyze_run.py <run-dir>` and resolve every problem before presenting for approval. This catches properties no unit owns, plan units citing properties that do not exist, unapproved intentional changes, and dependency cycles — gaps that each artifact hides on its own. Present:

- source lock and candidate location;
- preservation properties;
- requested new properties;
- verification route (`contract-only`, `mixed`, or `differential`) and oracle for each pilot property;
- unknowns and blockers;
- proposed files and dependencies;
- test and rollback plan;
- any SDK, auth, license, or API uncertainty;
- any project-local adopted-skill notes used and the extra obligations they added.

Ask exactly:

```text
Approve Mew behavior before implementation?

- Preservation properties:
- New properties:
- Intentional changes:
- Verification route:
- Oracle mapping:
- Proposed files/dependencies:
- Verification plan:
- Unknowns/blockers:

Reply approve / revise / abort.
```

After the user approves, write `approved_by` and `approved_at` into the contract, append run-bound approval evidence containing those exact values and the contract SHA-256, and rerun schema plus consistency checks. This approval entry must precede implementation and every `work_item_done`; a later attestation cannot repair missing pre-implementation approval. Keep evidence timestamps timezone-aware and nondecreasing in append order; append order breaks equal-timestamp ties, and never replay an old lifecycle entry. Do not modify production source before those checks pass. The original request is not approval of the detailed contract. At handoff, append `final_verification` only after every terminal work-item event, and bind it to the current contract, plan, and parity SHA-256 hashes so stale checks cannot complete the run.

### 8. Implement and verify

After approval, load only the implementation context selected by the route:

- **`contract-only`** — do **not** load `differential-migration`. Implement the approved pilot directly from the contract and plan, then run the declared contract, characterization, and regression checks for every property in the in-scope verification set.
- **`mixed`** — load `differential-migration` for every property in the set using `executable-baseline` or `authorized-reference`, including preservation properties; run the declared non-executable checks for the rest.
- **`differential`** — load `differential-migration` and compare every property in the set with its executable baseline or authorized reference.

For every route:

1. Work in the candidate, never the immutable baseline.
2. Implement only the approved pilot and property set.
3. Add characterization or regression tests before changing existing behavior; add contract tests for introduced behavior.
4. Use official SDKs where one exists; do not hand-roll an API protocol to save time.
5. Run focused checks after each change and the full discovered CI-equivalent suite before handoff.
6. Classify every mismatch; never weaken the contract or test to obtain a pass.
7. Produce a schema-valid `parity-report.json` with exactly one result for every property in the in-scope verification set. Set `total_properties == len(results) == passed + mismatches`; explicitly deferred unknowns contribute to none of these values. Append all command outcomes to evidence and omit `old_output` when no executable comparison exists.
8. Before handoff, the target's own formatter, linter, and test suite must all pass on the candidate. Discover them from the repo (e.g. `cargo fmt --check` + `cargo clippy -- -D warnings` + `cargo test`, `ruff`/`pytest`, `eslint`/`vitest`) and record each command with its exit code in evidence. Append one run-bound `final_verification` entry containing the successful command list. A formatting- or lint-only failure is a failed run, not a stylistic footnote — CI will reject it.

If a project-local adopted-skill note requires extra executable checks, run them
before claiming parity.

### 9. Handoff

A run is complete only when it has:

- `migration-request.json`
- `manifest.json`
- `run-state.json` with no `pending`, `in_progress`, or `blocked` items
- `repro.json`
- `provenance.json`
- `repo-inventory.yaml`
- `behavioral-contract.yaml`
- recorded approval
- `migration-plan.yaml`
- `evidence.jsonl`
- `parity-report.json`
- final run validation passes: `python3 scripts/validate_run.py --final <run-dir>`
- final cross-artifact analysis passes: `python3 scripts/analyze_run.py --final <run-dir>`
- the target's formatter, linter, and test suite all green on the candidate, with each command and exit code in evidence
- exact verification commands and exit states
- remaining risks, unknowns, and rollback instructions

Do not claim parity from a green unit-test suite alone.

### 10. Retro

After user review, ask what escaped the gates, what work was wasted, and what the skill should have known. If the user responds, follow `references/skill-evolution.md` and write `proposed-skill-changes.md` inside the run. Never modify the shared pack automatically; if the user skips, record that choice.

## Host behavior

1. Load each component skill only when its phase or verification route requires it.
2. Before creating or continuing work, discover and sync relevant run state from repository context; do not depend on an exact resume phrase.
3. Resolve the pack path once; keep all run artifacts under the target's `.mew/runs/`.
4. Do not ask the user to enumerate component skills or restate workflow internals.
5. This orchestrator wins conflicts about phase order, approval, scope sizing, artifact location, and progress ownership.

## Failure and stop conditions

Stop and report evidence when:

- the target baseline cannot reproduce;
- the official API or SDK needed by the request does not exist or does not expose the required capability;
- authentication would require copying private tokens or unsupported credential flows;
- a reference license prevents reuse;
- the target has unresolved uncommitted changes before baseline lock;
- a new dependency or behavior change lacks approval;
- verification cannot distinguish a regression from environment nondeterminism.

A blocker is a valid Mew result. Do not fabricate support or substitute a merely OpenAI-compatible endpoint for a provider-specific contract without evidence.

## References

- `references/reference-inspection.md` — per-reference observation format
- `references/project-notes.md` — optional repository-specific guidance
- `references/skill-evolution.md` — retro and reviewed skill evolution
- Component skills: `repo-cartographer`, `behavior-contract`, `migration-planner`, `differential-migration`, `observation`
