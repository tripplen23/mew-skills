# mew-skills

Evidence-driven skills for behavior-preserving software migration.

Each skill teaches an AI agent how to execute one phase of the Mew migration workflow: map a source repository, extract its behavioral DNA, plan a slice-by-slice migration, and prove parity through differential testing.

## Skills

| Skill | Phase | What it does |
|-------|-------|-------------|
| `repo-cartographer` | INGEST + REPRODUCE | Inventory source repo: public APIs, CLI, file formats, DB effects, env vars, telemetry, platforms, perf. Lock source commit. |
| `behavior-contract` | OBSERVE + CONTRACT | Extract behavioral DNA from the running system. Produce a behavioral contract with each property labeled preserve / change / deprecate / unknown. Includes characterization tests, golden master, and metamorphic testing. |
| `migration-planner` | MIGRATION PLAN | Build a semantic map, select pilot slices, define migration units, set stop conditions and performance budgets. Uses Strangler Fig and Branch By Abstraction patterns. |
| `differential-migration` | IMPLEMENT + VERIFY | Implement target-language slices, run differential tests against the old implementation, produce a parity report. 9-class failure taxonomy (McKeeman 1998). |
| `browser-observation` | OBSERVE + VERIFY | Reconstruct authorized web apps with a five-channel evidence model (DOM/a11y, network, console, pixels, vision). Vision is never the sole oracle. |

## Schemas

JSON Schema files validate every artifact a skill produces:

- `schemas/run-manifest.schema.json` — run identity, source lock, tool registry
- `schemas/behavioral-contract.schema.json` — property list with preservation labels
- `schemas/migration-plan.schema.json` — semantic map, pilot units, stop conditions
- `schemas/parity-report.schema.json` — differential results, mismatch queue, verdict, tolerance class
- `schemas/evidence.schema.json` — evidence.jsonl entry format
- `schemas/repro.schema.json` — Phase 0 reproducible environment pin
- `schemas/provenance.schema.json` — provenance & licensing (SPDX, SLSA)

## Policies

Human-approved guardrails that constrain agent behavior:

- `policies/sdk-selection.md` — prefer official SDKs, never hand-roll
- `policies/command-allowlist.md` — safe vs forbidden shell commands
- `policies/network-policy.md` — sandbox and network boundaries
- `policies/secret-handling.md` — redaction, no secrets in evidence
- `policies/licensing-and-provenance.md` — license compatibility tracking

## Workflow

```
INGEST → REPRODUCE → OBSERVE → CONTRACT → [HUMAN APPROVAL]
  → MIGRATION PLAN → IMPLEMENT IN SLICES → DIFFERENTIAL VERIFY → HANDOFF
```

Human approval gates exist at: behavioral contract, dependency/SDK substitution, accepted deviations, destructive actions.

## Validation

```bash
bash scripts/validate.sh
```

Checks: `agentskills validate` on every skill, JSON Schema syntax, frontmatter security (no `< >`), `name` == directory name.

## Installation

```bash
# Clone
git clone https://github.com/tripplen23/mew-skills.git

# Tap into Hermes
hermes skills tap add tripplen23/mew-skills

# Or copy individual skills into your agent's skills directory
cp -r skills/repo-cartographer ~/.hermes/skills/
```

## Design Principles

1. **Evidence over claims.** Every skill returns artifacts, not prose assertions.
2. **Earned autonomy.** Agents prove behavior slice by slice before receiving broader scope.
3. **Fresh-context review.** Reviewers see the diff and contract, not the author's reasoning.
4. **Deterministic gates.** CI decides whether evidence passes — not agent confidence.
5. **Human approval at boundaries.** Contracts, SDK substitution, deviations, destructive actions.

## Research Base

See `docs/RESEARCH.md` for the primary sources that informed this design.

## License

MIT
