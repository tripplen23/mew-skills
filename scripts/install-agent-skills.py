#!/usr/bin/env python3
"""Install or update mew-skills for Agent Skills discovery.

Project-local installs write into a target git worktree. Global installs
write into user-level skill directories that multiple agents share.

Symlinks (the default) point into the pack directory, so re-pulling the
pack automatically updates every installed copy; --update refreshes links
and picks up newly added skills.
"""

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

GLOBAL_ANCHOR = Path.home() / ".agents" / "mew-skills"


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


def resolve_install_paths(
    target: Path, skills_dir: Path, global_install: bool
) -> tuple[Path, Path, Path | None]:
    """Return (skills_root, anchor, git_dir) for project or global installs."""
    if global_install:
        return Path.home() / skills_dir, GLOBAL_ANCHOR, None
    git_dir = target / ".git"
    if not git_dir.exists():
        raise RuntimeError(f"target is not a git worktree: {target}")
    return target / skills_dir, target / ".agents" / "mew-skills", git_dir


def install(pack: Path, target: Path, skills_dir: Path, copy: bool, global_install: bool) -> None:
    skills_root, anchor, git_dir = resolve_install_paths(target, skills_dir, global_install)
    skills_root.mkdir(parents=True, exist_ok=True)

    installed: list[str] = []
    for name in skill_names(pack):
        link_or_copy(pack / "skills" / name, skills_root / name, copy)
        installed.append(str(skills_dir / name))

    remove_path(anchor)
    anchor.parent.mkdir(parents=True, exist_ok=True)
    if copy:
        anchor.mkdir(parents=True)
        for item in ("schemas", "policies"):
            shutil.copytree(pack / item, anchor / item)
    else:
        relative = os.path.relpath(pack.resolve(), anchor.parent.resolve())
        anchor.symlink_to(relative, target_is_directory=True)

    if global_install:
        installed.append(str(GLOBAL_ANCHOR))
    else:
        installed.append(".agents/mew-skills")
        replace_exclude_block(git_dir / "info" / "exclude", installed)

    mode = "copied" if copy else "linked"
    scope = "globally" if global_install else f"into {target}"
    print(f"mew-skills {mode} {scope}")
    print(f"Skills directory: {skills_root}")
    print(f"Installed {len(skill_names(pack))} skills: {', '.join(skill_names(pack))}")


def uninstall(pack: Path, target: Path, skills_dir: Path, global_install: bool) -> None:
    skills_root, anchor, git_dir = resolve_install_paths(target, skills_dir, global_install)
    for name in skill_names(pack):
        remove_path(skills_root / name)
    remove_path(anchor)
    if not global_install:
        replace_exclude_block(git_dir / "info" / "exclude", [])
    where = "global installation" if global_install else f"installation from {target}"
    print(f"Removed mew-skills {where}")


def global_update(pack: Path, copy: bool) -> None:
    seen: set[Path] = set()
    updated: list[str] = []
    for host, rel in HOST_SKILLS_DIR.items():
        root = (Path.home() / rel).resolve()
        if root in seen:
            continue
        seen.add(root)
        present = any((root / name).exists() for name in skill_names(pack))
        if not present:
            continue
        install(pack, Path.home(), rel, copy, global_install=True)
        updated.append(host)
    if not updated:
        print("No global mew-skills installation found. Install first with --global.")
    else:
        print(f"Updated global installs for: {', '.join(updated)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install or update mew-skills for Agent Skills discovery."
    )
    parser.add_argument(
        "target", nargs="?", type=Path, help="Target git worktree (project install)"
    )
    parser.add_argument(
        "--host",
        choices=sorted(HOST_SKILLS_DIR),
        default="agent-skills",
        help="Known host discovery layout (default: agent-skills)",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        help="Override skills directory (project: relative to worktree, global: relative to home)",
    )
    parser.add_argument("--copy", action="store_true", help="Copy instead of creating symlinks")
    parser.add_argument(
        "--global",
        dest="global_install",
        action="store_true",
        help="Install into user-level skill directories instead of a target repo",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Refresh all installed global skill directories from the pack (requires --global)",
    )
    parser.add_argument("--uninstall", action="store_true", help="Remove installed skills")
    args = parser.parse_args()

    if args.copy and args.uninstall:
        parser.error("--copy and --uninstall cannot be used together")
    if args.update and args.uninstall:
        parser.error("--update and --uninstall cannot be used together")

    pack = Path(__file__).resolve().parents[1]

    if args.update:
        if not args.global_install:
            parser.error("--update requires --global")
        global_update(pack, args.copy)
        return 0

    if args.global_install:
        skills_dir = args.skills_dir or HOST_SKILLS_DIR[args.host]
        target = args.target or Path.home()
        if args.uninstall:
            uninstall(pack, target, skills_dir, True)
        else:
            install(pack, target, skills_dir, args.copy, True)
        return 0

    if args.target is None:
        parser.error("target is required for project install (or use --global)")

    target = args.target.resolve()
    skills_dir = args.skills_dir or HOST_SKILLS_DIR[args.host]
    if skills_dir.is_absolute():
        parser.error("--skills-dir must be relative to the target worktree")

    try:
        if args.uninstall:
            uninstall(pack, target, skills_dir, False)
        else:
            install(pack, target, skills_dir, args.copy, False)
    except (OSError, RuntimeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
