#!/usr/bin/env python3
"""Install mew-skills into a target repository for OpenCode discovery."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

MARKER_START = "# >>> mew-skills OpenCode (local) >>>"
MARKER_END = "# <<< mew-skills OpenCode (local) <<<"


def replace_exclude_block(exclude: Path, lines: list[str]) -> None:
    existing = exclude.read_text() if exclude.exists() else ""
    start = existing.find(MARKER_START)
    if start >= 0:
        end = existing.find(MARKER_END, start)
        if end < 0:
            raise RuntimeError(f"unterminated mew-skills block in {exclude}")
        end += len(MARKER_END)
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


def install(pack: Path, target: Path, copy: bool) -> None:
    git_dir = target / ".git"
    if not git_dir.exists():
        raise RuntimeError(f"target is not a git worktree: {target}")

    skills_source = pack / "skills"
    skill_names = sorted(p.name for p in skills_source.iterdir() if (p / "SKILL.md").is_file())
    if "mew-migration" not in skill_names:
        raise RuntimeError("mew-migration skill is missing from this pack")

    agents_dir = target / ".agents"
    skills_dir = agents_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    installed: list[str] = []
    for name in skill_names:
        source = skills_source / name
        destination = skills_dir / name
        remove_path(destination)
        if copy:
            shutil.copytree(source, destination)
        else:
            relative = os.path.relpath(source.resolve(), destination.parent.resolve())
            destination.symlink_to(relative, target_is_directory=True)
        installed.append(f".agents/skills/{name}")

    anchor = agents_dir / "mew-skills"
    remove_path(anchor)
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
    print(f"OpenCode skills {mode} into {target}")
    print(f"Installed {len(skill_names)} skills: {', '.join(skill_names)}")
    print(f"Start OpenCode from: {target}")


def uninstall(pack: Path, target: Path) -> None:
    skills_source = pack / "skills"
    skill_names = sorted(p.name for p in skills_source.iterdir() if (p / "SKILL.md").is_file())
    for name in skill_names:
        remove_path(target / ".agents" / "skills" / name)
    remove_path(target / ".agents" / "mew-skills")
    replace_exclude_block(target / ".git" / "info" / "exclude", [])
    print(f"Removed mew-skills OpenCode installation from {target}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install mew-skills under a target repo's .agents/ directory."
    )
    parser.add_argument("target", type=Path, help="Target git worktree (for example ../mew)")
    parser.add_argument("--copy", action="store_true", help="Copy instead of creating symlinks")
    parser.add_argument("--uninstall", action="store_true", help="Remove installed skills")
    args = parser.parse_args()

    pack = Path(__file__).resolve().parents[1]
    target = args.target.resolve()
    if args.copy and args.uninstall:
        parser.error("--copy and --uninstall cannot be used together")

    try:
        if args.uninstall:
            uninstall(pack, target)
        else:
            install(pack, target, args.copy)
    except (OSError, RuntimeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
