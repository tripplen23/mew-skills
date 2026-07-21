# Project-local adopted notes

Use these notes only when a target repository has project-specific workflow obligations that should not become universal skill rules.

## Resolve the note

1. Locate the checked-out skill pack used for schemas and policies.
2. Derive `<project-id>` from the target git remote's repository name (last path segment without `.git`); fall back to the target directory name when no remote exists.
3. Look under `<pack>/projects/<project-id>/skill-adopted/`.
4. Load only notes whose declared scope is `repo:<project-id>`.

These notes are local guidance, not required pack content. They may be git-ignored and are not guaranteed to exist in an installed `.agents/mew-skills` anchor.

## Apply the note

- Add only obligations relevant to the approved request scope.
- Cite the note in `evidence.jsonl` when it changes observation, planning, or verification.
- Never promote a project-specific rule to the shared pack automatically.
- If a note conflicts with the orchestrator's phase order, approval gate, artifact paths, or safety policy, the orchestrator wins.