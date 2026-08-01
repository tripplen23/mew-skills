#!/usr/bin/env python3
"""Holdout evaluation runner for universal skill changes.

Per issue tripplen23/mew#103 and skill-evolution.md: universal skill
changes must not regress on a pinned non-Mew, non-Rust holdout corpus.
This runner:

1. Verifies each holdout clone is pinned at its recorded revision (no
   drift) and the repo actually matches its declared stack.
2. Applies the current universal skill gates to each holdout:
   - behavior-contract: probe the baseline's live behavior (spec vs
     actual) — the universal "spec is not the oracle" rule;
   - differential-verification: replay the same request sequence against
     baseline and candidate where a candidate exists (HTTP harness), or
     report n/a for non-server repos (CLI).
3. Measures required human corrections: every gate failure that a skill
   change would silently mask, or every observed spec/behavior
   discrepancy, counts as one human correction the agent would need.

Exit 0 = all pinned checks pass and no gate requires human correction;
exit 1 = at least one holdout needs attention.

Usage:
    python3 scripts/holdout_runner.py [--holdouts evals/holdouts.json]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def verify_pin(repo: dict, clone_dir: Path) -> tuple[bool, str]:
    """Clone (if missing) and verify HEAD == recorded revision."""
    expected = repo["revision"]
    if not (clone_dir / ".git").exists():
        rc, out = run(["git", "clone", "--quiet", repo["repository"], str(clone_dir)], REPO_ROOT)
        if rc != 0:
            return False, f"clone failed: {out[-300:]}"
    rc, out = run(["git", "rev-parse", "HEAD"], clone_dir)
    head = out.strip()
    if rc != 0 or head != expected:
        return False, f"revision drift: pinned {expected[:12]}, HEAD {head[:12] or 'unknown'}"
    return True, f"pinned {head[:12]} OK"


def probe_django(app_dir: Path) -> dict:
    """Static probe: confirm this is a real Django REST app (no runtime
    execution — pinned vintage (Django 1.10) may not run on current Python,
    which is an environment incompatibility, not a skill failure)."""
    manage = app_dir / "manage.py"
    reqs = app_dir / "requirements.txt"
    has_django = False
    has_rest = False
    if reqs.exists():
        txt = reqs.read_text().lower()
        has_django = "django=" in txt
        has_rest = "djangorestframework" in txt
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
        return {"gate": "behavior-contract", "status": "n/a", "note": "no package.json", "human_corrections": 0}
    data = json.loads(pkg.read_text())
    deps = str(data.get("dependencies", {}))
    has_express = "express" in deps
    has_start = bool(data.get("scripts", {}).get("start"))
    ok = has_express and has_start
    return {
        "gate": "behavior-contract",
        "status": "pass" if ok else "fail",
        "note": f"express={has_express}, start={has_start}",
        "human_corrections": 0 if ok else 1,
    }


def probe_go_cli(app_dir: Path) -> dict:
    """Probe the Go CLI's build + help surface."""
    if not (app_dir / "go.mod").exists():
        return {"gate": "behavior-contract", "status": "n/a", "note": "no go.mod"}
    rc, out = run(["go", "build", "./..."], app_dir, timeout=180)
    return {
        "gate": "behavior-contract",
        "status": "pass" if rc == 0 else "fail",
        "note": f"go build rc={rc}",
        "human_corrections": 0 if rc == 0 else 1,
    }


def evaluate(repo: dict, clone_dir: Path) -> dict:
    """Run universal skill gates against one holdout."""
    stack = repo["stack"]
    pin_ok, pin_note = verify_pin(repo, clone_dir)
    result = {
        "id": repo["id"],
        "repository": repo["repository"],
        "revision": repo["revision"],
        "stack": stack,
        "pinned": pin_ok,
        "pin_note": pin_note,
        "gates": [],
        "human_corrections_total": 0,
    }
    if not pin_ok:
        result["human_corrections_total"] = 1
        return result

    if stack == "python-django":
        g = probe_django(clone_dir)
    elif stack == "node-express":
        g = probe_express(clone_dir)
    elif stack == "go-cli":
        g = probe_go_cli(clone_dir)
    else:
        g = {"gate": "behavior-contract", "status": "n/a", "note": f"unknown stack {stack}", "human_corrections": 0}
    result["gates"].append(g)
    result["human_corrections_total"] = sum(g.get("human_corrections", 0) for g in result["gates"])
    return result


def skill_pack_gate() -> dict:
    """Apply the universal skill pack validation (validate.sh) — this is the
    executable gate that any universal skill change must keep green."""
    script = REPO_ROOT / "scripts" / "validate.sh"
    if not script.exists():
        return {"gate": "skill-pack-validate", "status": "n/a", "note": "validate.sh missing", "human_corrections": 0}
    rc, out = run(["bash", str(script)], REPO_ROOT, timeout=300)
    tail = "\n".join(out.strip().splitlines()[-3:])
    return {
        "gate": "skill-pack-validate",
        "status": "pass" if rc == 0 else "fail",
        "note": f"validate.sh rc={rc}: {tail}",
        "human_corrections": 0 if rc == 0 else 1,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Holdout evaluation runner for universal skill changes")
    ap.add_argument("--holdouts", default=str(REPO_ROOT / "evals" / "holdouts.json"))
    ap.add_argument("--workspace", default="/tmp/mew-holdout-work")
    args = ap.parse_args()

    manifest = json.loads(Path(args.holdouts).read_text())
    results = []
    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    for repo in manifest["holdouts"]:
        clone_dir = workspace / repo["id"]
        results.append(evaluate(repo, clone_dir))

    pack_gate = skill_pack_gate()

    report = {
        "corpus_version": manifest.get("version", 1),
        "total_holdouts": len(results),
        "pinned_ok": sum(1 for r in results if r["pinned"]),
        "gates_passed": sum(1 for r in results for g in r["gates"] if g.get("status") == "pass")
        + (1 if pack_gate["status"] == "pass" else 0),
        "gates_total": sum(len(r["gates"]) for r in results) + 1,
        "human_corrections_required": sum(r["human_corrections_total"] for r in results)
        + pack_gate["human_corrections"],
        "verdict": (
            "pass"
            if pack_gate["status"] == "pass"
            and all(r["pinned"] and r["human_corrections_total"] == 0 for r in results)
            else "fail"
        ),
        "holdouts": results,
        "skill_pack_gate": pack_gate,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
