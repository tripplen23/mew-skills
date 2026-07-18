# Claude Code integration

Install `mew-skills` into Claude Code's project skill directory:

```bash
cd workspace
python3 mew-skills/scripts/install-agent-skills.py --host claude target
cd target
claude
```

This creates:

```text
target/
├── .claude/skills/<skill-name>/
└── .agents/mew-skills/   # schemas and policies anchor
```

Use copy mode for throwaway workspaces:

```bash
python3 mew-skills/scripts/install-agent-skills.py --host claude --copy target
```

Uninstall:

```bash
python3 mew-skills/scripts/install-agent-skills.py --host claude --uninstall target
```

Start Claude from the target repository root so project instructions, git
boundaries, and relative file tools match the migration target.
