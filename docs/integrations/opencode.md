# OpenCode integration

OpenCode only discovers project skills from `.opencode/skills/`, `.claude/skills/`, or `.agents/skills/` between the current directory and the git worktree root. A sibling `mew-skills/skills/` directory is not discovered automatically.

## Install globally

OpenCode also reads global skills from `~/.agents/skills/`. Install once for
every project on the machine (shared with Codex and other
Agent-Skills-compatible agents):

```bash
curl -fsSL https://raw.githubusercontent.com/tripplen23/mew-skills/main/install.sh | bash -s -- --global
```

The global install also registers the six Mew skills as OpenCode slash
commands under `~/.config/opencode/commands/`, so `/mew-migration`,
`/repo-cartographer`, `/behavior-contract`, `/migration-planner`,
`/differential-migration`, and `/observation` are available immediately.

Re-run with `update` to pull the latest skills and commands:

```bash
curl -fsSL https://raw.githubusercontent.com/tripplen23/mew-skills/main/install.sh | bash -s -- update
```

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

The installer creates local symlinks under `target/.agents/skills/` and a `.agents/mew-skills` pack anchor for schemas and policies. It also registers the six skills as local slash commands under `target/.opencode/commands/`. It records those local paths in `target/.git/info/exclude`, so they do not appear in the target pull request.

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

The available skills should include `mew-migration`, `repo-cartographer`, `behavior-contract`, `migration-planner`, `differential-migration`, and `observation`.

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

## Slash commands

Every install also ships a matching OpenCode slash command per skill, so the
Mew workflow is reachable from `/` without typing a prompt:

| Command                     | Loads skill              |
| --------------------------- | ------------------------ |
| `/mew-migration`            | `mew-migration`          |
| `/repo-cartographer`        | `repo-cartographer`      |
| `/behavior-contract`        | `behavior-contract`      |
| `/migration-planner`        | `migration-planner`      |
| `/differential-migration`   | `differential-migration` |
| `/observation`              | `observation`            |

Each command forwards `$ARGUMENTS` to its skill. Global installs write to
`~/.config/opencode/commands/`; local installs write to
`target/.opencode/commands/`.

## Why the target repository is the OpenCode root

Starting OpenCode inside `target/` gives it:

- correct project rules and git boundary;
- target-relative file tools;
- automatic discovery of the installed `.agents/skills/` entries;
- run artifacts under `target/.mew/runs/`;
- no ambiguity about which sibling repository may be edited.

The skill pack remains read-only workflow input. Only the target repository and its run artifacts are writable during a migration.
