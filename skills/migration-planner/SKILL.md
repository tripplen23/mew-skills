---
name: migration-planner
description: "Builds a schema-valid plan for a migration, authorized reconstruction, or feature adoption. Maps only applicable semantic risks, selects bounded pilots, orders dependency-aware units, and defines verification and stop gates. Use after a behavioral contract draft exists and before implementation."
license: MIT
metadata:
  author: tripplen23
  version: "0.2.0"
  mew-phase: MIGRATION_PLAN
---

# Migration Planner

Turn a behavioral contract into the smallest executable plan that preserves target behavior and introduces only the requested change.

## Input and approval gate

Load `.mew/runs/<run-id>/behavioral-contract.yaml` and validate it against `schemas/behavioral-contract.schema.json`.

- When invoked by `mew-migration`, accept its schema-valid draft. Build the plan so the contract and plan can receive one combined human approval; do not require prior contract approval.
- When invoked standalone, require explicit human approval of the contract before planning.
- Never implement production changes during planning.

## Workflow

1. **Confirm scope.** Use the request mode selected by the orchestrator: migration, authorized reconstruction, or feature adoption. Treat the target baseline as the preservation oracle. Treat references as design evidence unless an authorized executable reference is recorded as an oracle.
2. **Build `semantic_map`.** Include only risk categories that occur in the scoped units. Allowed categories are `ownership`, `nullable`, `exceptions`, `integer_overflow`, `time`, `string_encoding`, `concurrency`, `allocator`, `ffi`, `debug_release`, and `platform`. Do not add empty or speculative entries to cover the list. Each entry records `source_pattern`, `target_pattern`, `risk`, and applicable `gotchas`.
3. **Define units.** Group work at the smallest boundary that owns complete contract properties. Record source and target paths, dependencies, contract properties, and risk. Order units by dependencies and keep contract tests protected from implementation changes.
4. **Choose pilots.** A bounded feature adoption gets one minimal vertical pilot covering its extension seam, old default behavior, new behavior, and one representative failure or edge path. For larger migrations or reconstructions, add pilots only when distinct risks cannot be exercised by one bounded slice.
5. **Encode parallel safety.** Run all IDs in `pilot_units` sequentially in dependency order. After every pilot passes, non-pilot units may share an execution wave only when every dependency has passed, mutable test resources are isolated, and each unit has one writer. Compare normalized repository-relative `target_paths`: a directory overlaps its descendants, aliases resolve to the same path, and every direct or generated write must be declared. Add `depends_on` edges for uncertain path ownership, shared protocols, schemas, database state, generated outputs, lock/build files, benchmarks, or integration order even when source imports do not require them. Do not add a second `parallel_groups` field; the orchestrator derives waves from these constraints.
6. **Set gates.** Add concrete stop conditions for unresolved oracles, unsupported APIs, licensing or authorization conflicts, repeated parity failures, failed rollback, and material budget regressions when applicable. Copy measurable performance gates from the contract; do not invent budgets.
7. **Set worker policy.** Limit editable paths to the unit, protect contract and run artifacts, use one writer per unit, and select isolation supported by the repository. Parallel workers return evidence fragments; one coordinator serializes canonical plan, contract, and evidence updates. Do not prescribe a language pair, framework, interop layer, or migration pattern unless the contract or repository requires it.
8. **Write and validate.** Write `.mew/runs/<run-id>/migration-plan.yaml` exactly to `schemas/migration-plan.schema.json`, then run the pack's schema and cross-artifact checks available for the run.

## Handoff

Under `mew-migration`, return the schema-valid plan to the orchestrator for its combined contract-and-plan approval gate. Standalone, present the validated plan and require `approve / revise / abort` before implementation. Report blockers instead of weakening properties, tests, provenance, or stop conditions.
