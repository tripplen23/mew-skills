---
name: repo-cartographer
description: "Maps affected repository surfaces for a migration, authorized reconstruction, or feature adoption. Produces a scoped inventory and dependency map, and records the clean baseline in the canonical run manifest without modifying source behavior."
license: MIT
metadata:
  author: tripplen23
  version: "0.2.0"
  mew-phase: INGEST+REPRODUCE
---

# Repo Cartographer

Create the smallest evidence-backed repository inventory needed for contract extraction and planning.

## Invocation and artifact ownership

When invoked by `mew-migration`, use its run ID, run directory, `manifest.json`, and `evidence.jsonl`. Do not recreate or overwrite orchestrator-owned run artifacts such as the migration request, manifest, reproduction record, provenance record, or evidence log. Append evidence and create or update only `repo-inventory.yaml` for this phase.

When invoked standalone, create missing run infrastructure once. Generate the run ID as `YYYYMMDD-HHMMSS-<7chars>`, create `manifest.json` conforming to `schemas/run-manifest.schema.json`, and create `evidence.jsonl`. In every mode, `manifest.json` is the canonical baseline lock. Do not create or use `source-lock.json`.

## Dirty-tree gate

Read `git rev-parse HEAD` and `git status --porcelain` first. A dirty tree may be inspected with read-only commands, and findings must remain provisional. Do not lock a baseline, write run artifacts, or edit repository files until the user commits, reverts, or otherwise isolates the changes. After resolution, read `HEAD` and status again, require a clean tree, and record that commit in `manifest.json.source_commit` before writing the inventory.

## Workflow

1. **Set scope.** Start with observable surfaces affected by the requested evolution: public API or UI boundaries, CLI behavior, files and configuration, data effects, environment, telemetry, errors, platforms, and performance constraints. Include only applicable categories.
2. **Widen on evidence.** Follow imports, callers, shared state, generated code, runtime configuration, tests, and public contracts when they can affect the scoped behavior. Do not inventory unrelated subsystems. Record why each scope expansion was necessary.
3. **Map dependencies.** For affected modules, record direct dependencies and dependents, then identify relevant leaves, hubs, and cycles. Include package versions and licenses only where they can enter the implementation, distribution, or verification path.
4. **Collect evidence.** Inspect source, tests, build and CI configuration, examples, and documentation. Prefer executable behavior over README claims; record discrepancies. Preserve exact user-visible error text and command output where it is a contract candidate and safe to retain. Before writing either artifact, redact credentials, tokens, personal data, sensitive paths, and secret-bearing headers or environment values; use dedicated test accounts and synthetic data where possible. Never persist an unsafe verbatim value merely because exact output is useful.
5. **Write inventory.** Write `.mew/runs/<run-id>/repo-inventory.yaml` with the run ID, locked source commit, scoped surfaces, dependency map, evidence references, exclusions, and reasons for widened scope. Append findings to `evidence.jsonl` using `schemas/evidence.schema.json`; set `redacted: true` when any retained fact was sanitized and keep raw sensitive captures out of both artifacts.
6. **Validate and hand off.** Validate applicable run artifacts and report unresolved dirty state, missing revisions, authorization or license blockers, and unverified assumptions. The lock is invalid if the source commit changes; re-run mapping rather than silently updating it.
