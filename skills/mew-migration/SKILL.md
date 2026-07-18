---
name: mew-migration
description: "Orchestrates an evidence-driven, behavior-preserving migration or feature adoption from a short request. Use when the user asks to migrate, port, rewrite, transplant, or add a capability from reference implementations while preserving existing behavior. Requires only a target repository and desired evolution; creates the run, loads the phase skills, produces validated artifacts, and stops for human approval before implementation."
license: MIT
compatibility: "OpenCode, Hermes, and Agent Skills-compatible clients"
metadata:
  author: tripplen23
  version: "0.3.0"
  mew-phase: END_TO_END
---

# Mew Migration

Turn a short migration request into a bounded Mew run. This skill owns orchestration; the phase skills own specialized reasoning. Do not make the user restate the workflow, artifact paths, schemas, or phase order.

## When to use

Load this skill when the user asks to:

- migrate or port an implementation while preserving behavior;
- replace a framework, language, SDK, service, or provider;
- adopt a capability from one or more reference implementations;
- rewrite a subsystem with evidence-backed parity;
- run the complete Mew workflow rather than one isolated phase.

For AI model providers, gateways, SDKs, or model-selection UX, **always**
read `references/provider-adoption.md` and follow its contract checklist
before proposing any implementation. Provider-adoption runs that skip the
structured reference-analysis or the provider/model approval gate will
produce the wrong behavior — flattening model lists, ignoring credential
scoping, and skipping provider-level selection.

For browser reconstruction, load `browser-observation` as the observation driver. For a single already-established phase, use that phase skill directly.

## Minimum input

Only two fields are required:

1. **Target repository** — path to the repository that will change. If OpenCode is running inside that repository, use the current git root.
2. **Desired evolution** — one sentence describing the intended capability or replacement.

Everything else is optional:

- reference repositories or URLs;
- paths included or excluded from scope;
- compatibility constraints;
- required providers, SDKs, languages, or platforms;
- explicit performance or resource budgets.

Ask one concise clarification only when a required field cannot be inferred. Do not ask the user for a run ID, artifact directory, phase sequence, schemas, test commands discoverable from the repo, or a complete acceptance-criteria list.

## Quick start

A sufficient request is:

```text
Use mew-migration to add native OpenAI API and GitHub Copilot provider support
in this Mew repo while preserving the existing OpenCode Go path. Treat
anomalyco/opencode and NousResearch/hermes-agent as references, prefer official
SDKs, and keep the change minimal.
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

Write a `migration-request.json` first and validate it against `schemas/migration-request.schema.json`. Record inferred values explicitly so the user can correct them.

## Scope modes

Choose the smallest mode that fits the request:

| Mode | Use when | Pilot default |
| --- | --- | --- |
| `feature_adoption` | Add a capability to the existing implementation, possibly informed by references | One vertical slice |
| `language_port` | Replace code in one language with another | Up to three representative slices |
| `framework_migration` | Replace a framework or platform while retaining public behavior | One boundary-first slice, then expand |
| `reconstruction` | Rebuild an authorized application from observations | One approved journey |

Do not force three pilot units onto a bounded feature adoption. Scale inventory, evidence, and testing to the observable surfaces affected by the request.

## Workflow

### 1. Intake and lock

1. Resolve the target git root and desired evolution.
2. Verify the target is a git repository and record `HEAD`, branch, remotes, and dirty state.
3. Observation may begin on a dirty tree, but do not establish a baseline or edit until the user resolves uncommitted changes.
4. Create the run directory and `migration-request.json`.
5. Create `manifest.json`, `repro.json`, `provenance.json`, and `evidence.jsonl`.
6. Record the skill-pack commit and all reference revisions used.

### 2. Map the target

Load `repo-cartographer`. Apply it to the target surfaces affected by the desired evolution, then widen only when dependencies or public contracts require it.

For a feature adoption, map both:

- the target's current boundary and invariants;
- the extension seam where the new capability can enter minimally.

Produce `repo-inventory.yaml`. Do not inventory unrelated subsystems merely to make the artifact look comprehensive.

### 3. Observe target and references

Load `behavior-contract` for target behavior. References are design evidence, not the behavioral oracle.

Produce a structured observation for each reference **before touching the target
source or writing any code**. See `references/reference-inspection.md` for the
minimum per-reference format. A web search result is not sufficient — inspect
source files, documentation, or API docs and cite exact evidence in the run's
`evidence.jsonl`.

For every reference implementation you must:

1. pin a revision or retrieval timestamp to the nearest minute;
2. inspect official documentation and official SDKs before community code;
3. extract architecture, configuration, authentication, routing, dispatch,
   error-mapping, and model/feature selection relevant to the request;
4. record provenance and license constraints (exact SPDX identifier);
5. distinguish reusable protocol facts from implementation-specific choices;
6. produce `reference-<name>.md` with all findings and append to evidence;
7. never copy code whose license or provenance is unresolved.

Provider-adoption runs must also produce `reference-analysis.md` that answers
the questions in `references/provider-adoption.md` before any implementation
code is written.

The target's existing behavior remains the oracle for preservation properties. The requested evolution defines new target properties. A reference does not silently redefine either.

### 4. Draft the contract

Produce `behavioral-contract.yaml` containing:

- existing properties that must remain unchanged;
- new properties required by the desired evolution;
- intentional changes, if any;
- unknowns and blockers;
- exact normalization and tolerance rules;
- tests or observations supporting each property.

For a new provider or SDK, the contract must include the provider/model DNA checklist from `references/provider-adoption.md`:

- provider-catalog shape;
- model-filtering rule;
- credential/env/config shape;
- default compatibility behavior;
- UI/API behavior;
- a dedicated approval prompt for provider/model behavior before implementation proceeds.

### 5. Build the minimal plan

Load `migration-planner`. Produce `migration-plan.yaml` using the selected scope mode.

A minimal feature-adoption plan should normally contain:

- one extension seam;
- one pilot unit;
- focused protocol/config/runtime changes;
- regression tests for the old default;
- contract tests for each new capability;
- stop conditions for unsupported official APIs, licensing conflicts, or auth assumptions.

Do not add abstractions, provider registries, fallback systems, or dependencies unless a contract property requires them.

Provider-adoption plans must describe the model-list contract and its impact on the inventory, TUI, API `/models`, and engine dispatch.

### 6. Human approval gate

Stop after the contract and plan are schema-valid. Present:

- source lock and candidate location;
- preservation properties;
- requested new properties;
- unknowns and blockers;
- proposed files and dependencies;
- test and rollback plan;
- any SDK, auth, license, or API uncertainty;
- for provider-adoption: the provider/model behavior contract items and reference-analysis summary.

Ask exactly:

```text
Approve provider/model behavior before implementation?

- Provider catalog shape:
- Model filtering rule:
- Credential/env/config shape:
- Default compatibility behavior:
- UI/API behavior:
- Unknowns/blockers:

Reply approve / revise / abort.
```

Do not treat the original request as approval of the detailed contract. Do not modify production source before explicit approval.

### 7. Implement and verify

After approval, load `differential-migration` and implement only the approved pilot.

1. Work in the candidate, never the immutable baseline.
2. Add characterization or regression tests before changing behavior.
3. Use official SDKs where one exists; do not hand-roll an API protocol to save time.
4. Run focused checks after each change and the full discovered CI-equivalent suite before handoff.
5. Compare baseline and candidate at the contracted boundary.
6. Classify every mismatch; never weaken the contract or test to obtain a pass.
7. Produce a schema-valid `parity-report.json` and append command outcomes to evidence.

Provider-adoption runs must include executable checks for the six cases in `references/provider-adoption.md` section "Minimal tests" before claiming parity.

### 8. Handoff

A run is complete only when it has:

- `migration-request.json`
- `manifest.json`
- `repro.json`
- `provenance.json`
- `repo-inventory.yaml`
- `behavioral-contract.yaml`
- recorded approval
- `migration-plan.yaml`
- `evidence.jsonl`
- `parity-report.json`
- exact verification commands and exit states
- remaining risks, unknowns, and rollback instructions

Do not claim parity from a green unit-test suite alone.

## OpenCode behavior

When this skill is loaded in OpenCode:

1. Use the native `skill` tool to load each phase skill when its phase begins.
2. Do not ask the user to paste or enumerate the component skills.
3. Resolve shared schemas and policies from `.agents/mew-skills/` when installed by `scripts/install-opencode.py`; otherwise locate the checked-out pack once and reuse that path.
4. Keep artifacts under the target's `.mew/runs/`, not inside the skill repository.
5. If a component skill conflicts with this orchestrator on phase order, approval, scope sizing, or artifact location, this orchestrator wins.

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

- `references/opencode-two-repo-workspace.md` — install and invoke this pack when `mew/` and `mew-skills/` are sibling directories
- `references/provider-adoption.md` — required contract checklist and test cases for provider/model DNA migration
- `references/reference-inspection.md` — minimum per-reference structured observation format
- OpenCode Agent Skills: https://opencode.ai/docs/skills/
- Component skills: `repo-cartographer`, `behavior-contract`, `migration-planner`, `differential-migration`, `browser-observation`
