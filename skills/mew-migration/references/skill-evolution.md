# Self-healing skill evolution

Mew skills improve through reviewed changes to instructions, references,
schemas, fixtures, and validators. This is **self-healing skill evolution**.

## Safety invariant

A migration run may propose a skill change but must never edit or merge the
shared skill pack automatically. Human review is the gate between run feedback
and reusable infrastructure.

## Lesson tiers

Every lesson must carry exactly one tier:

- `universal` — applies across languages and repositories. It may enter a skill
  body if concise and broadly evidenced.
- `stack:<name>` — applies to a language, framework, UI class, provider class,
  or toolchain. Put it in a conditionally loaded reference file.
- `repo:<name>` — depends on one repository's terminology, architecture, or
  policy. Put it in that repository's `CONTEXT.md` or ADR, never the shared
  skill pack.

Project-local adopted-skill notes may live under
`projects/<project-id>/skill-adopted/`. This path is ignored by git on purpose:
it is a scratchpad for lessons earned while working on one project, not shared
pack doctrine. Promote a note from there only after it satisfies the promotion
rule below.

Resolve `<project-id>` from the target's git remote as the repository name (the
segment after the last `/`, without `.git`; e.g. `github.com/tripplen23/mew` →
`mew`), falling back to the repository directory name when there is no remote.
One project's notes never load for another target.

Every note must open with a provenance header so an agent reading the file alone
(not just its path) knows the scope, confidence, and origin:

```markdown
> Scope: repo:<project-id> — local lesson, not universal.
> Oracle: hard | soft. Learned: <run-id or date>. Promote only per this file.
```

A note without this header, or whose `Scope` does not match the current target,
is not loaded as guidance.

If the tier is uncertain, default narrower. Promotion from repo to stack or
stack to universal requires the same failure class in at least two independent
runs.

## Oracle tiers

- **Hard oracle:** formatter, compiler, linter, test, schema validator,
  reproducible behavior probe, or differential result. A hard-oracle lesson may
  propose an executable gate and must include a failing fixture.
- **Soft oracle:** user preference, naming taste, architecture direction, or
  perceived wasted effort. It may propose wording or a decision question only;
  it is never auto-applied.

Do not turn one user's taste into a universal rule.

## Proposal format

The retro writes `proposed-skill-changes.md` in the migration run directory.
Each proposed change includes:

- observed failure or feedback;
- exact evidence reference;
- oracle tier (`hard` or `soft`);
- lesson tier (`universal`, `stack:*`, or `repo:*`);
- proposed destination;
- existing rule it merges with or replaces;
- fixture path for hard-oracle changes;
- expected benefit and known ceiling.

The maintainer may accept, revise, defer, or reject each item independently.

## Anti-bloat rules

1. Skill bodies hold procedures and universal invariants; examples and gotchas
   live in references; run-specific evidence stays in run artifacts.
2. Search for an existing rule before adding one. Merge overlapping lessons.
3. Every addition must replace/prune existing text, add an executable fixture,
   or remain run-local until corroborated by a second independent run.
4. `scripts/validate.sh` rejects any `SKILL.md` over 500 lines.
5. A rule that has not triggered or prevented a failure across twenty recorded
   runs is a prune candidate, not automatically deleted.

## Holdout evaluation

Holdouts detect overfitting to Mew and Rust. A holdout repository must:

- be outside the Mew organization and use a different primary stack;
- have a pinned revision and compatible license;
- define a bounded task and objective contract;
- remain excluded from skill-editing evidence: do not inspect holdout failures
  while drafting a change, only when evaluating the finished candidate;
- run before and after a proposed universal skill change.

Record holdouts in `evals/holdouts.json`. A universal skill change must not
regress the holdout's contract completion, gate success, or required human
corrections. If it does, narrow the lesson tier or reject the change.

Enrollment is not evidence of a passing baseline. Each manifest entry carries
an evaluation status; `planned` means the holdout is pinned but has not yet
proved anything. Promotion requires recorded before/after runs.

## Promotion rule

A proposed lesson enters the shared pack only when:

1. evidence identifies a real failure or wasted loop;
2. the narrowest correct tier is chosen;
3. hard-oracle changes include a fixture;
4. skill validation passes;
5. relevant golden tasks pass;
6. universal changes do not regress the holdout;
7. a human maintainer approves the diff.
