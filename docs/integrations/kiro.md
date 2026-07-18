# Kiro integration (IDE and CLI)

Kiro supports the Agent Skills standard natively, so `mew-skills` installs with no
format changes. The Kiro IDE and the Kiro CLI use the same skill locations and the
same discovery rules.

## Skill locations

| Path              | Scope     | Use for                           |
| ----------------- | --------- | --------------------------------- |
| `.kiro/skills/`   | Workspace | This project's migration runs     |
| `~/.kiro/skills/` | Global    | Personal use across every project |

On a name clash, the workspace skill wins over the global skill. The default agent
loads both locations automatically.

## Install into a target repository

Given:

```text
workspace/
├── target/
└── mew-skills/
```

Run:

```bash
cd workspace
python3 mew-skills/scripts/install-agent-skills.py --host kiro --copy target
```

This creates:

```text
target/
├── .kiro/skills/<skill-name>/   # the 6 mew skills
└── .agents/mew-skills/          # schemas and policies anchor
```

The installer records these local paths in `target/.git/info/exclude`, so they do
not appear in the target pull request.

### Copy vs symlink

Prefer `--copy` for Kiro. Kiro's own skill import copies folders, and copies are
portable across Linux, macOS, and Windows. Symlinks work on Linux/macOS but are not
portable, so use them only for a local checkout you control:

```bash
python3 mew-skills/scripts/install-agent-skills.py --host kiro target   # symlinks
```

### Global install (optional)

To make the skills available in every workspace, install into your home directory:

```bash
python3 mew-skills/scripts/install-agent-skills.py --skills-dir ~/.kiro/skills --copy .
```

Global install is convenient for pack development but not recommended for real
migrations — keep run artifacts and skill scope tied to the target workspace.

## Verify discovery

Kiro discovers skills when a chat session starts, so after installing you must
**open a new chat session** (or reload the window) in the target workspace.

- **IDE**: open `target/` as the workspace, start a new chat, type `/` and confirm
  `mew-migration`, `repo-cartographer`, `behavior-contract`, `migration-planner`,
  `differential-migration`, and `browser-observation` appear. You can also open the
  **Agent Steering & Skills** section in the Kiro panel.
- **CLI**: run `kiro` inside `target/`, then `/context show` to confirm the skills
  are loaded.

The slash command uses the full skill folder name, so the orchestrator is
`/mew-migration`, not `/mew`.

## Invoke a migration

Automatic activation (Kiro matches the skill description):

```text
Use mew-migration in this repository to adopt <capability> from <reference>
while preserving existing behavior.
```

Or invoke explicitly as a slash command:

```text
/mew-migration adopt <capability> from <reference>, preserve existing behavior
```

In the CLI, text after the slash command is passed to the skill as context (and
substituted into `$ARGUMENTS` / `${N}` placeholders if the skill defines them).

The prompt does not need to specify phase order, run ID, artifact paths, schemas,
or discoverable test commands — the skill owns those mechanics. The first
invocation ends at the approval gate with a contract and plan. Review them, then
reply with one of:

```text
approve
revise: <specific change>
abort
```

## Custom agents

The **default** Kiro agent loads skills from both locations with no configuration.
A **custom agent** does not load skills by default — add the skill URIs to its
`resources` field:

```json
{
  "name": "my-agent",
  "resources": [
    "skill://.kiro/skills/*/SKILL.md",
    "skill://~/.kiro/skills/*/SKILL.md"
  ]
}
```

## Uninstall

```bash
python3 mew-skills/scripts/install-agent-skills.py --host kiro --uninstall target
```

## Skills vs steering vs powers

- Use **skills** (this pack) for the portable migration workflow.
- **Steering** (`.kiro/steering/`) is Kiro-specific always/auto/fileMatch/manual
  context — use it for target-repo conventions, not for the workflow itself.
- **Powers** bundle MCP tools with guidance — not required by `mew-skills`.

Start Kiro from the target repository root so project rules, git boundaries, and
relative file tools match the migration target, and run artifacts land under
`target/.mew/runs/`.
