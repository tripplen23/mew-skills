#!/usr/bin/env python3
"""Install mew-skills into a target repository for Agent Skills discovery."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

MARKER_START = "# >>> mew-skills Agent Skills (local) >>>"
MARKER_END = "# <<< mew-skills Agent Skills (local) <<<"
LEGACY_MARKERS = [
    ("# >>> mew-skills OpenCode (local) >>>", "# <<< mew-skills OpenCode (local) <<<"),
]

HOST_SKILLS_DIR = {
    "opencode": Path(".agents/skills"),
    "claude": Path(".claude/skills"),
    "codex": Path(".agents/skills"),
    "kiro": Path(".kiro/skills"),
    "agent-skills": Path(".agents/skills"),
}


def replace_exclude_block(exclude: Path, lines: list[str]) -> None:
    existing = exclude.read_text() if exclude.exists() else ""
    for marker_start, marker_end in [(MARKER_START, MARKER_END), *LEGACY_MARKERS]:
        start = existing.find(marker_start)
        if start >= 0:
            end = existing.find(marker_end, start)
            if end < 0:
                raise RuntimeError(f"unterminated mew-skills block in {exclude}")
            end += len(marker_end)
            existing = existing[:start].rstrip() + existing[end:].lstrip("\n")

    block = ""
    if lines:
        block = "\n".join([MARKER_START, *lines, MARKER_END]) + "\n"
    content = existing.rstrip()
    if content and block:
        content += "\n\n"
    content += block
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text(content)


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def skill_names(pack: Path) -> list[str]:
    skills_source = pack / "skills"
    names = sorted(p.name for p in skills_source.iterdir() if (p / "SKILL.md").is_file())
    if "mew-migration" not in names:
        raise RuntimeError("mew-migration skill is missing from this pack")
    return names


def link_or_copy(source: Path, destination: Path, copy: bool) -> None:
    remove_path(destination)
    if copy:
        shutil.copytree(source, destination)
    else:
        relative = os.path.relpath(source.resolve(), destination.parent.resolve())
        destination.symlink_to(relative, target_is_directory=True)


def install(pack: Path, target: Path, skills_dir: Path, copy: bool) -> None:
    git_dir = target / ".git"
    if not git_dir.exists():
        raise RuntimeError(f"target is not a git worktree: {target}")

    absolute_skills_dir = target / skills_dir
    absolute_skills_dir.mkdir(parents=True, exist_ok=True)

    installed: list[str] = []
    for name in skill_names(pack):
        link_or_copy(pack / "skills" / name, absolute_skills_dir / name, copy)
        installed.append(str(skills_dir / name))

    anchor = target / ".agents" / "mew-skills"
    remove_path(anchor)
    anchor.parent.mkdir(parents=True, exist_ok=True)
    if copy:
        anchor.mkdir(parents=True)
        for item in ("schemas", "policies"):
            shutil.copytree(pack / item, anchor / item)
    else:
        relative = os.path.relpath(pack.resolve(), anchor.parent.resolve())
        anchor.symlink_to(relative, target_is_directory=True)
    installed.append(".agents/mew-skills")

    replace_exclude_block(git_dir / "info" / "exclude", installed)
    mode = "copied" if copy else "linked"
    print(f"mew-skills {mode} into {target}")
    print(f"Skills directory: {skills_dir}")
    print(f"Installed {len(skill_names(pack))} skills: {', '.join(skill_names(pack))}")


def uninstall(pack: Path, target: Path, skills_dir: Path) -> None:
    for name in skill_names(pack):
        remove_path(target / skills_dir / name)
    remove_path(target / ".agents" / "mew-skills")
    replace_exclude_block(target / ".git" / "info" / "exclude", [])
    print(f"Removed mew-skills installation from {target}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install mew-skills into a target repo for Agent Skills discovery."
    )
    parser.add_argument("target", type=Path, help="Target git worktree")
    parser.add_argument(
        "--host",
        choices=sorted(HOST_SKILLS_DIR),
        default="agent-skills",
        help="Known host discovery layout (default: agent-skills)",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        help="Override skills directory relative to the target worktree",
    )
    parser.add_argument("--copy", action="store_true", help="Copy instead of creating symlinks")
    parser.add_argument("--uninstall", action="store_true", help="Remove installed skills")
    args = parser.parse_args()

    if args.copy and args.uninstall:
        parser.error("--copy and --uninstall cannot be used together")

    pack = Path(__file__).resolve().parents[1]
    target = args.target.resolve()
    skills_dir = args.skills_dir or HOST_SKILLS_DIR[args.host]
    if skills_dir.is_absolute():
        parser.error("--skills-dir must be relative to the target worktree")

    try:
        if args.uninstall:
            uninstall(pack, target, skills_dir)
        else:
            install(pack, target, skills_dir, args.copy)
    except (OSError, RuntimeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
