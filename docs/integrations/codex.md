# Codex integration

Use the Agent Skills-compatible layout by default:

```bash
cd workspace
python3 mew-skills/scripts/install-agent-skills.py --host codex target
cd target
codex
```

This creates:

```text
target/
├── .agents/skills/<skill-name>/
└── .agents/mew-skills/   # schemas and policies anchor
```

If your Codex build expects another project skill directory, keep the same pack
but override the install path:

```bash
python3 mew-skills/scripts/install-agent-skills.py --skills-dir .codex/skills target
```

Use copy mode for disposable CI workspaces:

```bash
python3 mew-skills/scripts/install-agent-skills.py --host codex --copy target
```

Uninstall:

```bash
python3 mew-skills/scripts/install-agent-skills.py --host codex --uninstall target
```

Codex support depends on the Agent Skills-compatible skill loader in the host.
The skill pack itself stays host-neutral; only discovery paths differ.
