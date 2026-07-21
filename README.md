# mew-skills

Evidence-driven skills for software migration, authorized reconstruction/cloning, and feature adoption.

The pack is designed as a **self-healing skill system**: real runs feed reviewed
regression evidence back into references, fixtures, schemas, and hard gates.
This is prompt/artifact evolution with human approval.

The `mew-migration` skill turns a short migration, clone/reconstruction, or
feature request into an end-to-end run. It selects contract-only, mixed, or
differential verification from the approved behavior and available oracle.
Phase skills handle repository mapping, observable-behavior capture, planning,
and specialized verification on demand.

## Skills

| Skill                    | Phase              | What it does                                                                                                                                                                                                                                           |
| ------------------------ | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `mew-migration`          | END TO END         | Orchestrates and resumes migration, authorized reconstruction/cloning, and feature adoption. Selects verification by oracle presence, maintains durable progress across sessions, and stops for approval before implementation.                        |
| `repo-cartographer`      | INGEST + REPRODUCE | Inventory source repo: public APIs, CLI, file formats, DB effects, env vars, telemetry, platforms, perf. Lock source commit.                                                                                                                           |
| `behavior-contract`      | OBSERVE + CONTRACT | Capture observable behavior and required evolution. Label properties preserve / introduce / intentionally-change / deprecate / unknown, with baseline, characterization, regression, or contract-spec oracles.                                         |
| `migration-planner`      | MIGRATION PLAN     | Build a semantic map, select pilot slices, define migration units, set stop conditions and performance budgets. Uses Strangler Fig and Branch By Abstraction patterns.                                                                                 |
| `differential-migration` | IMPLEMENT + VERIFY | Implement target-language slices, run differential tests against the old implementation, produce a parity report. 9-class failure taxonomy (McKeeman 1998).                                                                                            |
| `observation`            | OBSERVE + VERIFY   | Reconstruct an authorized running system (web, TUI, mobile, desktop, device) with a five-channel evidence model (structure, I/O contract, diagnostics, state capture, vision). Ships a Web/Playwright driver profile. Vision is never the sole oracle. |

## Schemas

JSON Schema files validate every artifact a skill produces:

- `schemas/run-manifest.schema.json` — run identity, source lock, tool registry
- `schemas/run-state.schema.json` — resumable work items, focus, and parent/child run links
- `schemas/migration-request.schema.json` — normalized intake for a short end-to-end request
- `schemas/behavioral-contract.schema.json` — property list with preservation labels
- `schemas/migration-plan.schema.json` — semantic map, pilot units, stop conditions
- `schemas/parity-report.schema.json` — differential results, mismatch queue, verdict, tolerance class
- `schemas/evidence.schema.json` — evidence.jsonl entry format
- `schemas/repro.schema.json` — Phase 0 reproducible environment pin
- `schemas/provenance.schema.json` — provenance & licensing (SPDX, SLSA)
- `schemas/repo-inventory.schema.json` — scoped target surfaces, dependencies, evidence references, and exclusions

## Policies

Human-approved guardrails that constrain agent behavior:

- `policies/sdk-selection.md` — prefer official SDKs, never hand-roll
- `policies/command-allowlist.md` — safe vs forbidden shell commands
- `policies/network-policy.md` — sandbox and network boundaries
- `policies/secret-handling.md` — redaction, no secrets in evidence
- `policies/licensing-and-provenance.md` — license compatibility tracking

## Workflow

```
INGEST → REPRODUCE → OBSERVE → GRILL → CONTRACT → MIGRATION PLAN
  → [HUMAN APPROVAL] → IMPLEMENT IN SLICES → DIFFERENTIAL VERIFY → HANDOFF → RETRO
```

Human approval gates exist at: behavioral contract, dependency/SDK substitution, accepted deviations, destructive actions.

## Validation

```bash
bash scripts/validate.sh
```

Checks: `agentskills validate` on every skill, JSON Schema syntax, frontmatter security (no `< >`), `name` == directory name.

Validation also enforces a 500-line cap per `SKILL.md` and validates the pinned holdout manifest.

`validate.sh` checks the pack itself. To gate a **run's** artifacts against the
schemas (the enforcement the skills instruct), point the run gate at a run dir:

```bash
python3 scripts/validate_run.py <target>/.mew/runs/<run-id>/
```

It validates each produced artifact and every `evidence.jsonl` line, exiting
non-zero on any schema drift.

## Installation

```bash
# Clone
git clone https://github.com/tripplen23/mew-skills.git

# Tap into Hermes
hermes skills tap add tripplen23/mew-skills

# Or copy individual skills into another agent's skills directory
cp -r skills/repo-cartographer ~/.hermes/skills/
```

### Project-local installation

Given `workspace/target/` and `workspace/mew-skills/`, install into the host's
project skill directory:

```bash
cd workspace
python3 scripts/install-agent-skills.py --host claude ../target
python3 scripts/install-agent-skills.py --host codex ../target
python3 scripts/install-agent-skills.py --host opencode ../target
python3 scripts/install-agent-skills.py --host kiro --copy ../target
```

The installer excludes local links through `.git/info/exclude`, so they do not
enter the target pull request.

A complete migration request can stay short:

```text
Use mew-migration to add <capability> to this repository while preserving
existing behavior. Treat <reference repository or URL> as design evidence,
prefer official SDKs, and keep the change minimal.
```

See `docs/integrations/` for OpenCode, Claude Code, Codex, Kiro (IDE + CLI),
copy mode, uninstall, and discovery verification notes.

## Design Principles

1. **Evidence over claims.** Every skill returns artifacts, not prose assertions.
2. **Earned autonomy.** Agents prove behavior slice by slice before receiving broader scope.
3. **Fresh-context review.** Reviewers see the diff and contract, not the author's reasoning.
4. **Deterministic gates.** CI decides whether evidence passes — not agent confidence.
5. **Human approval at boundaries.** Contracts, SDK substitution, deviations, destructive actions.
6. **Self-healing, not self-modifying.** Runs propose evidence-backed skill changes after handoff; maintainers review them before the shared pack changes.
7. **Generalization before promotion.** Repo-specific lessons stay in repo context; universal changes must not regress pinned holdouts.

## Research Base

See `docs/RESEARCH.md` for the primary sources that informed this design.

## License

MIT
