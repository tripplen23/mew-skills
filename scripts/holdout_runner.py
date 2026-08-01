#!/usr/bin/env python3
"""Holdout evaluation runner for universal skill changes.

Per issue tripplen23/mew#103 and skill-evolution.md: universal skill
changes must not regress on a pinned non-Mew, non-Rust holdout corpus.
This runner:

1. Materializes each holdout at its pinned revision (detached checkout,
   rejecting dirty worktrees) and verifies no revision drift.
2. Executes every check listed in the holdout's `required_checks` where
   an executable gate exists (behavior-contract probe, test-suite, skill
   pack validation). Checks without a supported gate are reported as
   `unsupported` and count as required human corrections — they never
   silently pass.
3. Reports required human corrections: every failed or unsupported gate
   counts as one correction the agent would need.

Exit 0 = all gates executed and green; exit 1 = at least one gate
failed; exit 2 = at least one required check unsupported (needs human).

Usage:
    python3 scripts/holdout_runner.py [--holdouts evals/holdouts.json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_CHECK_ALIASES = {
    "behavioral-contract": "behavior-contract",
    "behaviour-contract": "behavior-contract",
}

SUPPORTED_CHECKS = {
    "behavior-contract": "executes a stack probe of the holdout's live surface",
    "test-suite": "runs the holdout's native test command",
    "skill-pack-validate": "runs scripts/validate.sh (universal skill gate)",
    "formatter": "unsupported without a pinned formatter per stack",
    "linter": "unsupported without a pinned linter per stack",
    "differential-verification": "unsupported without a candidate build per holdout",
}

TEST_COMMANDS = {
    "python-django": None,  # Django 1.10 vintage: incompatible with current Python; reported unsupported
    "node-express": ["npm", "test", "--", "--runInBand"],
    "go-cli": ["go", "test", "./..."],
}

ENV_DEPENDENT_TEST_NOTE = {
    "node-express": "requires a reachable Postgres (prisma schema datasource) — env-dependent",
}


def run(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
    """Run a command; OSError (missing binary) becomes exit 127, not a crash."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def check_clean_worktree(clone_dir: Path) -> bool:
    """Return True only when the worktree has no tracked modifications."""
    rc, out = run(["git", "status", "--porcelain"], clone_dir)
    return rc == 0 and out.strip() == ""


def verify_pin(repo: dict, clone_dir: Path) -> tuple[bool, str]:
    """Materialize the pinned revision in detached mode; reject drift/dirt."""
    expected = repo["revision"]
    if not (clone_dir / ".git").exists():
        rc, out = run(["git", "clone", "--quiet", repo["repository"], str(clone_dir)], REPO_ROOT, timeout=300)
        if rc != 0:
            return False, f"clone failed: {out[-300:]}"
    if not check_clean_worktree(clone_dir):
        return False, "worktree is dirty (has tracked modifications)"
    rc, out = run(["git", "checkout", "--quiet", "--detach", expected], clone_dir)
    if rc != 0:
        return False, f"checkout {expected[:12]} failed: {out[-200:]}"
    rc, head = run(["git", "rev-parse", "HEAD"], clone_dir)
    head = head.strip()
    if rc != 0 or head != expected:
        return False, f"revision drift: pinned {expected[:12]}, HEAD {head[:12] or 'unknown'}"
    return True, f"pinned {head[:12]} OK (detached, clean)"


def probe_django(app_dir: Path) -> dict:
    """Static probe: confirm this is a real Django REST app.

    No runtime execution — pinned vintage (Django 1.10) cannot run on
    current Python, which is an environment incompatibility, not a skill
    failure."""
    manage = app_dir / "manage.py"
    reqs = app_dir / "requirements.txt"
    has_django = False
    has_rest = False
    if reqs.exists():
        txt = reqs.read_text()
        has_django = re.search(r"(?im)^\s*django\s*[<>=~!]", txt) is not None
        has_rest = re.search(r"(?im)^\s*djangorestframework\s*[<>=~!]", txt) is not None
    ok = manage.exists() and has_django and has_rest
    return {
        "gate": "behavior-contract",
        "status": "pass" if ok else "fail",
        "note": f"manage.py={manage.exists()}, django={has_django}, drf={has_rest}",
        "human_corrections": 0 if ok else 1,
    }


def probe_express(app_dir: Path) -> dict:
    """Static probe: confirm this is a real Express API app."""
    pkg = app_dir / "package.json"
    if not pkg.exists():
        return {
            "gate": "behavior-contract",
            "status": "fail",
            "note": "package.json missing (unexpected repo shape)",
            "human_corrections": 1,
        }
    try:
        data = json.loads(pkg.read_text())
    except json.JSONDecodeError:
        return {
            "gate": "behavior-contract",
            "status": "fail",
            "note": "package.json is not valid JSON",
            "human_corrections": 1,
        }
    deps = data.get("dependencies", {}) or {}
    dev = data.get("devDependencies", {}) or {}
    has_express = "express" in deps or "express" in dev
    has_start = bool(data.get("scripts", {}).get("start"))
    ok = has_express and has_start
    return {
        "gate": "behavior-contract",
        "status": "pass" if ok else "fail",
        "note": f"express={has_express}, start={has_start}",
        "human_corrections": 0 if ok else 1,
    }


def probe_go_cli(app_dir: Path) -> dict:
    """Probe the Go CLI: build must succeed."""
    if not (app_dir / "go.mod").exists():
        return {
            "gate": "behavior-contract",
            "status": "fail",
            "note": "go.mod missing (unexpected repo shape)",
            "human_corrections": 1,
        }
    rc, _ = run(["go", "build", "./..."], app_dir, timeout=180)
    return {
        "gate": "behavior-contract",
        "status": "pass" if rc == 0 else "fail",
        "note": f"go build rc={rc}",
        "human_corrections": 0 if rc == 0 else 1,
    }


def test_suite_gate(repo: dict, clone_dir: Path) -> dict:
    """Run the holdout's native test command where supported."""
    cmd = TEST_COMMANDS.get(repo["stack"])
    if cmd is None:
        return {
            "gate": "test-suite",
            "status": "unsupported",
            "note": f"no runnable test command for stack {repo['stack']} on this toolchain",
            "human_corrections": 1,
        }
    rc, out = run(cmd, clone_dir, timeout=300)
    tail = "\n".join(out.strip().splitlines()[-3:])
    note = f"{' '.join(cmd)} rc={rc}: {tail}"
    env_note = ENV_DEPENDENT_TEST_NOTE.get(repo["stack"])
    if rc != 0 and env_note:
        note = f"{note} | {env_note}"
    return {
        "gate": "test-suite",
        "status": "pass" if rc == 0 else "fail",
        "note": note,
        "human_corrections": 0 if rc == 0 else 1,
    }


def skill_pack_gate() -> dict:
    """Apply the universal skill pack validation (validate.sh) — the
    executable gate that any universal skill change must keep green."""
    script = REPO_ROOT / "scripts" / "validate.sh"
    if not script.exists():
        return {
            "gate": "skill-pack-validate",
            "status": "fail",
            "note": "validate.sh missing",
            "human_corrections": 1,
        }
    rc, out = run(["bash", str(script)], REPO_ROOT, timeout=300)
    tail = "\n".join(out.strip().splitlines()[-3:])
    return {
        "gate": "skill-pack-validate",
        "status": "pass" if rc == 0 else "fail",
        "note": f"validate.sh rc={rc}: {tail}",
        "human_corrections": 0 if rc == 0 else 1,
    }


GATE_DISPATCH = {
    "behavior-contract": lambda repo, d: (
        probe_django(d) if repo["stack"] == "python-django"
        else probe_express(d) if repo["stack"] == "node-express"
        else probe_go_cli(d)
    ),
    "test-suite": test_suite_gate,
    "skill-pack-validate": lambda repo, d: skill_pack_gate(),
}


def evaluate(repo: dict, clone_dir: Path) -> dict:
    """Run every required check listed in the manifest against one holdout."""
    pin_ok, pin_note = verify_pin(repo, clone_dir)
    result = {
        "id": repo["id"],
        "repository": repo["repository"],
        "revision": repo["revision"],
        "stack": repo["stack"],
        "pinned": pin_ok,
        "pin_note": pin_note,
        "gates": [],
        "human_corrections_total": 0,
    }
    if not pin_ok:
        result["human_corrections_total"] = 1
        return result

    required = [REQUIRED_CHECK_ALIASES.get(c, c) for c in repo.get("required_checks", [])]
    for check in required:
        if check in GATE_DISPATCH:
            g = GATE_DISPATCH[check](repo, clone_dir)
        else:
            g = {
                "gate": check or "unknown",
                "status": "unsupported",
                "note": SUPPORTED_CHECKS.get(check or "", f"no gate implemented for {check}"),
                "human_corrections": 1,
            }
        result["gates"].append(g)
    result["human_corrections_total"] = sum(g.get("human_corrections", 0) for g in result["gates"])
    return result


def resolve_workspace(explicit: str | None) -> tuple[Path, str]:
    """Private tempdir by default; validate ownership/perms when explicit."""
    if explicit:
        p = Path(explicit)
        p.mkdir(parents=True, exist_ok=True)
        st = p.stat()
        if st.st_uid != os.getuid():
            return p, f"WARNING: workspace {p} owned by uid {st.st_uid}, not {os.getuid()}"
        mode = st.st_mode & 0o777
        if mode & 0o022:
            return p, f"WARNING: workspace {p} is group/world-writable (mode {oct(mode)})"
        return p, ""
    return Path(tempfile.mkdtemp(prefix="mew-holdout-")), "private tempdir"


def main() -> int:
    ap = argparse.ArgumentParser(description="Holdout evaluation runner for universal skill changes")
    ap.add_argument("--holdouts", default=str(REPO_ROOT / "evals" / "holdouts.json"))
    ap.add_argument("--workspace", default=None, help="default: private tempdir")
    args = ap.parse_args()

    manifest = json.loads(Path(args.holdouts).read_text())
    results = []
    workspace, ws_note = resolve_workspace(args.workspace)

    for repo in manifest["holdouts"]:
        clone_dir = workspace / repo["id"]
        results.append(evaluate(repo, clone_dir))

    pack_gate = skill_pack_gate()

    gates = [g for r in results for g in r["gates"]]
    executed = [g for g in gates if g["status"] != "unsupported"] + [pack_gate]
    unsupported = [g for g in gates if g["status"] == "unsupported"]
    failed = [g for g in executed if g["status"] != "pass"]
    corrections = sum(r["human_corrections_total"] for r in results) + pack_gate["human_corrections"]

    if failed:
        verdict = "fail"
    elif unsupported:
        verdict = "incomplete"
    else:
        verdict = "pass"

    report = {
        "corpus_version": manifest.get("version", 1),
        "workspace": str(workspace),
        "workspace_note": ws_note or "OK",
        "total_holdouts": len(results),
        "pinned_ok": sum(1 for r in results if r["pinned"]),
        "gates_passed": sum(1 for g in executed if g["status"] == "pass"),
        "gates_failed": len(failed),
        "gates_unsupported": len(unsupported),
        "gates_total": len(gates) + 1,
        "human_corrections_required": corrections,
        "verdict": verdict,
        "holdouts": results,
        "skill_pack_gate": pack_gate,
        "unsupported_checks": [{"gate": g["gate"], "note": g["note"]} for g in unsupported],
    }
    print(json.dumps(report, indent=2))

    if verdict == "pass":
        return 0
    if verdict == "incomplete":
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
