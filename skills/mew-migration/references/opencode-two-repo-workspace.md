# OpenCode with sibling `mew` and `mew-skills` repositories

OpenCode only discovers project skills from `.opencode/skills/`, `.claude/skills/`, or `.agents/skills/` between the current directory and the git worktree root. A sibling `mew-skills/skills/` directory is not discovered automatically.

## Install locally

Given:

```text
workspace/
├── mew/
└── mew-skills/
```

Run:

```bash
cd workspace
python3 mew-skills/scripts/install-opencode.py mew
cd mew
opencode
```

The installer creates local symlinks under `mew/.agents/skills/` and a `.agents/mew-skills` pack anchor for schemas and policies. It records those local paths in `mew/.git/info/exclude`, so they do not appear in the Mew pull request.

Use `--copy` instead of symlinks for a disposable CI workspace:

```bash
python3 mew-skills/scripts/install-opencode.py --copy mew
```

Remove the local installation with:

```bash
python3 mew-skills/scripts/install-opencode.py --uninstall mew
```

## Verify discovery

Start OpenCode from the target repository, not the parent directory. Ask:

```text
List the available Mew migration skills. Do not start a migration.
```

The available skills should include `mew-migration`, `repo-cartographer`, `behavior-contract`, `migration-planner`, `differential-migration`, and `browser-observation`.

## Minimal provider-adoption prompt

```text
Use mew-migration to add native OpenAI API and GitHub Copilot provider support
in this Mew repo while preserving the existing OpenCode Go path. Treat
https://github.com/anomalyco/opencode and
https://github.com/NousResearch/hermes-agent as references, prefer official
SDKs, and keep the change minimal.
```

That prompt intentionally does not specify phase order, run ID, artifact paths, schemas, test commands, model enum changes, environment-variable names, or implementation details. The skill must discover and propose those from evidence.

The first invocation should end at the approval gate with a contract and plan. Review them, then reply with one of:

```text
approve
revise: <specific change>
abort
```

## Why the target repository is the OpenCode root

Starting OpenCode inside `mew/` gives it:

- correct project rules and git boundary;
- target-relative file tools;
- automatic discovery of the installed `.agents/skills/` entries;
- run artifacts under `mew/.mew/runs/`;
- no ambiguity about which sibling repository may be edited.

The skill pack remains read-only workflow input. Only the target repository and its run artifacts are writable during a migration.
