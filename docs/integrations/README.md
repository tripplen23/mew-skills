# Integrations

`mew-skills` uses the Agent Skills directory format. Host integrations only
decide where that directory is installed and how local files are hidden from the
target repository's git status.

| Host                            | Default install path | Command                                                                         |
| ------------------------------- | -------------------- | ------------------------------------------------------------------------------- |
| OpenCode                        | `.agents/skills/`    | `python3 mew-skills/scripts/install-agent-skills.py --host opencode target`     |
| Claude Code                     | `.claude/skills/`    | `python3 mew-skills/scripts/install-agent-skills.py --host claude target`       |
| Codex / Agent Skills compatible | `.agents/skills/`    | `python3 mew-skills/scripts/install-agent-skills.py --host codex target`        |
| Kiro (IDE + CLI)                | `.kiro/skills/`      | `python3 mew-skills/scripts/install-agent-skills.py --host kiro --copy target`  |
| Unknown/custom host             | chosen by user       | `python3 mew-skills/scripts/install-agent-skills.py --skills-dir <path> target` |

Kiro also reads global skills from `~/.kiro/skills/` and applies workspace skills
over global ones on a name clash. `--copy` is recommended for Kiro because Kiro's
own skill import copies folders; symlinks work on Linux/macOS but not portably.
See `kiro.md`.

Use `--copy` for disposable CI workspaces. Use `--uninstall` to remove local
links/copies. The installer records local paths in `.git/info/exclude`, not in
the target repository's tracked `.gitignore`.

The pack anchor is always installed at `.agents/mew-skills` so skills can find
schemas and policies independent of the host's skill directory.
