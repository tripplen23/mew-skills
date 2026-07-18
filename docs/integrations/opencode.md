# OpenCode integration

OpenCode only discovers project skills from `.opencode/skills/`, `.claude/skills/`, or `.agents/skills/` between the current directory and the git worktree root. A sibling `mew-skills/skills/` directory is not discovered automatically.

## Install locally

Given:

```text
workspace/
├── target/
└── mew-skills/
```

Run:

```bash
cd workspace
python3 mew-skills/scripts/install-agent-skills.py --host opencode target
cd target
opencode
```

The installer creates local symlinks under `target/.agents/skills/` and a `.agents/mew-skills` pack anchor for schemas and policies. It records those local paths in `target/.git/info/exclude`, so they do not appear in the target pull request.

Use `--copy` instead of symlinks for a disposable CI workspace:

```bash
python3 mew-skills/scripts/install-agent-skills.py --host opencode --copy target
```

Remove the local installation with:

```bash
python3 mew-skills/scripts/install-agent-skills.py --host opencode --uninstall target
```

## Verify discovery

Start OpenCode from the target repository, not the parent directory. Ask:

```text
List the available Mew migration skills. Do not start a migration.
```

The available skills should include `mew-migration`, `repo-cartographer`, `behavior-contract`, `migration-planner`, `differential-migration`, and `browser-observation`.

## Invoke a migration

```text
Use mew-migration in this target repository to adopt <capability> from
<reference> while preserving existing behavior.
```

The prompt does not need to specify phase order, run ID, artifact paths,
schemas, or discoverable test commands. The skill owns those mechanics.

The first invocation should end at the approval gate with a contract and plan. Review them, then reply with one of:

```text
approve
revise: <specific change>
abort
```

## Why the target repository is the OpenCode root

Starting OpenCode inside `target/` gives it:

- correct project rules and git boundary;
- target-relative file tools;
- automatic discovery of the installed `.agents/skills/` entries;
- run artifacts under `target/.mew/runs/`;
- no ambiguity about which sibling repository may be edited.

The skill pack remains read-only workflow input. Only the target repository and its run artifacts are writable during a migration.
