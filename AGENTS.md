# AGENTS.md

This repository is a reusable Agent Skills pack for evidence-driven, behavior-preserving migration. Treat it as product infrastructure, not notes.

## 1. Skills must own workflow mechanics

A user should be able to describe the target and desired evolution in plain language. The skill owns phase order, artifact paths, schemas, approval gates, and validation commands. If a user must restate those internals for the skill to work, improve the skill.

## 2. Evidence before implementation

For migration workflows, do not jump from a user request to code. First produce or update the required artifacts: migration request, reference analysis, behavioral contract, migration plan, and approval gate.

## 3. Reference code is not the oracle

Reference implementations provide design evidence. The target baseline remains the preservation oracle. Requested evolution defines new target behavior.

## 4. Minimal means complete

Prefer the smallest complete workflow. Do not remove required behavior, schema validation, approval, provenance, or parity checks to make the skill look simpler.

## 5. Keep skills agent-neutral

Write instructions in plain Markdown. Do not depend on one agent vendor's private commands. OpenCode, Hermes, Claude, Codex, and human reviewers should all be able to follow the skill.

## 6. Validate before handoff

Run:

```bash
bash scripts/validate.sh
```

If scripts or schemas change, test them with at least one real fixture.

## 7. M0 failures become skill improvements

When a real agent run fails, record the failure as:

- a gotcha;
- a hard gate;
- a reference file;
- a schema field;
- or a validation check.

Do not explain the failure away as model weakness until the skill has made the desired path explicit.
