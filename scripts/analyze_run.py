#!/usr/bin/env python3
"""Analyze cross-artifact consistency of a Mew run directory.

Usage:
  python3 scripts/analyze_run.py <run-dir>
  python3 scripts/analyze_run.py --final <run-dir>
  python3 scripts/analyze_run.py --selfcheck

`validate_run.py` proves each artifact is valid on its own. This gate proves the
request, manifest, progress state, contract, plan, evidence, and parity report
agree. Normal mode checks the pre-implementation set and resumable work index;
`--final` also requires approval metadata, terminal work items, and a parity
report.

Exit code: 0 consistent, 1 inconsistent, 2 usage or missing required artifacts.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

try:
    import yaml  # optional; contract + plan are YAML
    from yaml import YAMLError
except ImportError:  # ponytail: YAML artifacts skipped (not failed) without pyyaml.
    yaml = None
    YAMLError = ValueError

# artifact key -> filename on disk
FILES = {
    "request": "migration-request.json",
    "manifest": "manifest.json",
    "state": "run-state.json",
    "repro": "repro.json",
    "provenance": "provenance.json",
    "inventory": "repo-inventory.yaml",
    "contract": "behavioral-contract.yaml",
    "plan": "migration-plan.yaml",
    "parity": "parity-report.json",
}
SCHEMAS = {
    "request": "migration-request.schema.json",
    "manifest": "run-manifest.schema.json",
    "state": "run-state.schema.json",
    "repro": "repro.schema.json",
    "provenance": "provenance.schema.json",
    "inventory": "repo-inventory.schema.json",
    "contract": "behavioral-contract.schema.json",
    "plan": "migration-plan.schema.json",
    "parity": "parity-report.schema.json",
    "evidence": "evidence.schema.json",
}
FINAL_REQUIRED = set(FILES) | {"evidence"}
PACK = Path(__file__).resolve().parents[1]
RUN_ID_RE = re.compile(r"^\d{8}-\d{6}-[a-z0-9]{7}$")


def _artifact_path(run_dir: Path, filename: str) -> Path | None:
    """Return a contained regular artifact; reject symlinks and path escapes."""
    root = run_dir.resolve()
    path = root / filename
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError(f"artifact must not be a symlink: {filename}")
    resolved = path.resolve()
    if resolved.parent != root or not resolved.is_file():
        raise ValueError(f"artifact escapes run directory or is not a file: {filename}")
    return resolved


def _load(path: Path):
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError("pyyaml not installed")
        return yaml.safe_load(text)
    return json.loads(text)


def _load_evidence(path: Path) -> list[dict]:
    """Load append-only evidence while preserving malformed-line failures."""
    entries = []
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        if not raw.strip():
            continue
        try:
            entries.append(json.loads(raw))
        except ValueError as exc:
            raise ValueError(f"evidence.jsonl:{lineno}: {exc}") from exc
    return entries


def _evidence_order_problems(evidence: list[dict]) -> list[str]:
    """Reject timestamp regression and exact lifecycle-event replay.

    Timestamps must be timezone-aware and nondecreasing; append order breaks ties.
    """
    problems: list[str] = []
    previous: datetime | None = None
    seen_lifecycle: set[str] = set()
    lifecycle_actions = {
        "approval_recorded", "approval_gate", "approval_confirmed",
        "work_item_done", "work_item_deferred", "work_item_cancelled",
        "final_verification",
    }
    for index, entry in enumerate(evidence):
        raw = entry.get("timestamp")
        try:
            timestamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("timezone is required")
        except (AttributeError, TypeError, ValueError):
            problems.append(f"evidence[{index}] has an invalid timezone-aware timestamp")
            continue
        if previous is not None and timestamp < previous:
            problems.append(f"evidence[{index}] timestamp regresses in append order")
        previous = timestamp

        if entry.get("action") in lifecycle_actions:
            fingerprint = json.dumps(entry, sort_keys=True, separators=(",", ":"))
            if fingerprint in seen_lifecycle:
                problems.append(f"evidence[{index}] replays a lifecycle event")
            seen_lifecycle.add(fingerprint)
    return problems


def _bundle(run_dir: Path) -> dict[str, object]:
    """Load and hash contained artifacts for a current, parent, or child run."""
    hashes: dict[str, str] = {}
    bundle: dict[str, object] = {"_hashes": hashes}
    for key, filename in FILES.items():
        path = _artifact_path(run_dir, filename)
        if path is not None:
            bundle[key] = _load(path)
            hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    evidence = _artifact_path(run_dir, "evidence.jsonl")
    if evidence is not None:
        bundle["evidence"] = _load_evidence(evidence)
        hashes["evidence"] = hashlib.sha256(evidence.read_bytes()).hexdigest()
    if "request" in hashes:
        bundle["_request_sha256"] = hashes["request"]
    return bundle


def _schema_problems(bundle: dict, label: str, required: set[str]) -> list[str]:
    """Return stable shape errors before cross-artifact code touches values."""
    problems = [f"{label} is missing {key}" for key in sorted(required - bundle.keys())]
    for key, schema_name in SCHEMAS.items():
        if key not in bundle:
            continue
        schema = json.loads((PACK / "schemas" / schema_name).read_text())
        validator = Draft202012Validator(schema)
        values = bundle[key] if key == "evidence" else [bundle[key]]
        for index, value in enumerate(values):
            errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
            if errors:
                location = f"[{index}]" if key == "evidence" else ""
                problems.append(f"{label} {key}{location} is invalid: {errors[0].message}")
                break
    return problems


def _identity_problems(bundle: dict, expected_run_id: str) -> list[str]:
    """Bind every related artifact and request hash to its directory ID."""
    fields = {
        "request": (bundle.get("request") or {}).get("run_id"),
        "manifest": (bundle.get("manifest") or {}).get("run_id"),
        "state": (bundle.get("state") or {}).get("run_id"),
        "contract": (bundle.get("contract") or {}).get("contract_id"),
        "plan": (bundle.get("plan") or {}).get("run_id"),
        "parity": (bundle.get("parity") or {}).get("run_id"),
    }
    problems = [
        f"related run {expected_run_id} has {name} identity {value!r}"
        for name, value in fields.items()
        if value is not None and value != expected_run_id
    ]
    state = bundle.get("state") or {}
    actual_hash = bundle.get("_request_sha256")
    if actual_hash and state.get("request_sha256") != actual_hash:
        problems.append(f"related run {expected_run_id} request hash does not match its state")
    item_ids = [item.get("id") for item in (state.get("items", []) or [])]
    for item_id, count in Counter(item_ids).items():
        if item_id and count > 1:
            problems.append(f"related run {expected_run_id} contains duplicate work item {item_id}")
    return problems


def _safe_run_dir(runs_root: Path, run_id: object) -> Path | None:
    """Resolve only canonical immediate-child run directories; reject escapes."""
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        return None
    root = runs_root.resolve()
    candidate = (root / run_id).resolve()
    if candidate.parent != root:
        return None
    return candidate


def _has_cycle(units: list[dict]) -> bool:
    """True if depends_on edges among known unit ids contain a cycle (Kahn)."""
    ids = {u.get("id") for u in units if u.get("id")}
    indeg = {i: 0 for i in ids}
    adj: dict[str, list[str]] = {i: [] for i in ids}
    for u in units:
        uid = u.get("id")
        if uid not in ids:
            continue
        for dep in u.get("depends_on", []) or []:
            if dep in ids:  # dangling deps are reported separately, not here
                adj[dep].append(uid)
                indeg[uid] += 1
    queue = deque(i for i in ids if indeg[i] == 0)
    seen = 0
    while queue:
        seen += 1
        for m in adj[queue.popleft()]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    return seen != len(ids)


def _matching_done_event(
    item: dict,
    evidence: list[dict],
    run_id: str,
    artifact_hashes: dict[str, str],
) -> int | None:
    """Return the index of run-bound evidence for this exact completion."""
    defined_at = None
    expected = {
        "contract_properties": sorted(item.get("contract_properties", []) or []),
        "plan_units": sorted(item.get("plan_units", []) or []),
        "run_refs": sorted(item.get("run_refs", []) or []),
    }
    expected_hashes = {
        key: artifact_hashes.get(key) for key in ("contract", "plan", "parity")
    }
    for index, entry in enumerate(evidence):
        details = entry.get("details") or {}
        initialized = entry.get("action") == "work_items_initialized" and any(
            definition.get("id") == item.get("id")
            for definition in (details.get("items", []) or [])
            if isinstance(definition, dict)
        )
        added = entry.get("action") == "work_item_added" and details.get("item_id") == item.get("id")
        if details.get("run_id") == run_id and (initialized or added):
            defined_at = index if defined_at is None else defined_at
        if (
            defined_at is not None
            and index > defined_at
            and entry.get("action") == "work_item_done"
            and details.get("run_id") == run_id
            and details.get("item_id") == item.get("id")
            and details.get("artifact_hashes") == expected_hashes
            and all(
                isinstance(details.get(field), list) and sorted(details[field]) == values
                for field, values in expected.items()
            )
        ):
            return index
    return None


def _approval_evidence_indexes(
    contract: dict,
    evidence: list[dict],
    run_id: str,
    artifact_hashes: dict[str, str],
) -> list[int]:
    """Return approval entries bound to this run and exact contract bytes."""
    return [
        index
        for index, entry in enumerate(evidence)
        if entry.get("action") in {"approval_recorded", "approval_gate", "approval_confirmed"}
        and entry.get("result") == "pass"
        and (entry.get("details") or {}).get("run_id") == run_id
        and (entry.get("details") or {}).get("approved_by") == contract.get("approved_by")
        and (entry.get("details") or {}).get("approved_at") == contract.get("approved_at")
        and (entry.get("details") or {}).get("contract_sha256") == artifact_hashes.get("contract")
    ]


def _final_verification_indexes(
    evidence: list[dict],
    run_id: str,
    artifact_hashes: dict[str, str],
) -> list[int]:
    """Return passing final checks bound to the current contract, plan, and parity."""
    expected_hashes = {
        key: artifact_hashes.get(key) for key in ("contract", "plan", "parity")
    }
    matches = []
    for index, entry in enumerate(evidence):
        details = entry.get("details") or {}
        commands = details.get("commands")
        if (
            entry.get("action") == "final_verification"
            and entry.get("result") == "pass"
            and details.get("run_id") == run_id
            and details.get("artifact_hashes") == expected_hashes
            and isinstance(commands, list)
            and commands
            and all(
                isinstance(command, dict)
                and isinstance(command.get("command"), str)
                and command.get("command")
                and command.get("exit_code") == 0
                for command in commands
            )
        ):
            matches.append(index)
    return matches


def _state_problems(
    state: dict,
    manifest: dict,
    contract: dict,
    plan: dict,
    parity: dict | None,
    evidence: list[dict],
    related: dict[str, dict],
    *,
    final: bool,
) -> list[str]:
    """Check that mutable progress agrees with canonical artifacts and evidence."""
    problems: list[str] = []
    problems.extend(_evidence_order_problems(evidence))
    run_id = state.get("run_id")
    artifact_hashes = (related.get(run_id) or {}).get("_hashes") or {}
    items = state.get("items", []) or []
    item_ids = [item.get("id") for item in items if item.get("id")]
    duplicate_items = sorted(item for item, count in Counter(item_ids).items() if count > 1)
    for item_id in duplicate_items:
        problems.append(f"run state contains duplicate work item {item_id}")
    item_by_id = {item.get("id"): item for item in items if item.get("id")}
    approval_indexes = _approval_evidence_indexes(contract, evidence, run_id, artifact_hashes)
    terminal_event_indexes: list[int] = []

    expected_items: dict[str, str | None] = {}
    defined_at: dict[str, int] = {}
    progress_actions = {
        "work_items_initialized", "work_item_added", "work_item_done",
        "work_item_deferred", "work_item_cancelled",
    }
    for index, entry in enumerate(evidence):
        action = entry.get("action")
        details = entry.get("details") or {}
        if action in progress_actions and details.get("run_id") != run_id:
            problems.append(f"progress evidence {action} is not bound to run {run_id}")
            continue
        definitions = []
        if action == "work_items_initialized":
            definitions = [item for item in (details.get("items", []) or []) if isinstance(item, dict)]
        elif action == "work_item_added" and details.get("item_id"):
            definitions = [{"id": details["item_id"], "title": details.get("title")}]
        for definition in definitions:
            item_id = definition.get("id")
            if not item_id:
                continue
            title = definition.get("title")
            if item_id in expected_items and expected_items[item_id] != title:
                problems.append(f"work item {item_id} has conflicting evidence definitions")
                continue
            expected_items.setdefault(item_id, title)
            defined_at.setdefault(item_id, index)
    if not expected_items:
        problems.append("run state has no work_items_initialized evidence")
    for item_id, title in expected_items.items():
        current = item_by_id.get(item_id)
        if current is None:
            problems.append(f"initialized work item {item_id} is missing from run state")
        elif title and current.get("title") != title:
            problems.append(f"work item {item_id} title changed from initialized evidence")

    terminal_actions = {
        "work_item_done": "done",
        "work_item_deferred": "deferred",
        "work_item_cancelled": "cancelled",
    }
    latest_terminal: dict[str, tuple[int, str]] = {}
    for index, entry in enumerate(evidence):
        status = terminal_actions.get(entry.get("action"))
        if status is None:
            continue
        details = entry.get("details") or {}
        if details.get("run_id") != run_id:
            continue
        item_id = details.get("item_id")
        terminal_event_indexes.append(index)
        if item_id not in item_by_id:
            problems.append(f"terminal evidence references unknown work item {item_id}")
        if item_id not in defined_at or index <= defined_at[item_id]:
            problems.append(f"terminal evidence for work item {item_id} precedes its definition")
        latest_terminal[item_id] = (index, status)
        if status == "done" and not any(approval < index for approval in approval_indexes):
            problems.append(
                f"work_item_done for {item_id} lacks matching approval evidence before completion"
            )
    for item_id, (_, evidence_status) in latest_terminal.items():
        current = item_by_id.get(item_id)
        if current is not None and current.get("status") != evidence_status:
            problems.append(
                f"work item {item_id} status {current.get('status')} disagrees with latest terminal evidence {evidence_status}"
            )

    terminal = {"done", "deferred", "cancelled"}
    unfinished = [item for item in items if item.get("status") not in terminal]
    focus = state.get("focus_item")
    if unfinished:
        if not focus:
            problems.append("unfinished run state has no focus_item")
        if not state.get("next_action"):
            problems.append("unfinished run state has no next_action")
    if focus:
        if focus not in item_by_id:
            problems.append(f"focus_item references unknown work item {focus}")
        elif item_by_id[focus].get("status") in terminal:
            problems.append(f"focus_item {focus} is already terminal")

    if manifest.get("status") == "complete" and unfinished:
        problems.append("manifest is complete but run state still has unfinished work")
    if final:
        for item in unfinished:
            problems.append(f"final run has unfinished work item {item.get('id')} ({item.get('status')})")
        if manifest.get("status") != "complete":
            problems.append(f"final run manifest status is '{manifest.get('status')}', not 'complete'")
        if not approval_indexes:
            problems.append("final run lacks run-bound approval evidence matching the contract")

    props = contract.get("properties", []) or []
    prop_ids = {prop.get("id") for prop in props if prop.get("id")}
    desired_props = {
        prop.get("id")
        for prop in props
        if prop.get("id") and prop.get("preservation") in {"introduce", "intentionally-change", "deprecate"}
    }
    units = plan.get("units", []) or []
    unit_ids = {unit.get("id") for unit in units if unit.get("id")}
    state_props = {ref for item in items for ref in (item.get("contract_properties") or [])}
    state_units = {ref for item in items for ref in (item.get("plan_units") or [])}

    for item in items:
        item_id = item.get("id")
        for ref in item.get("contract_properties", []) or []:
            if ref not in prop_ids:
                problems.append(f"work item {item_id} references unknown contract property {ref}")
        for ref in item.get("plan_units", []) or []:
            if ref not in unit_ids:
                problems.append(f"work item {item_id} references unknown plan unit {ref}")
    for prop_id in sorted(desired_props - state_props):
        problems.append(f"desired-evolution property {prop_id} is not tracked by run state")
    for unit_id in sorted(unit_ids - state_units):
        problems.append(f"plan unit {unit_id} is not tracked by run state")

    for item in items:
        item_id = item.get("id")
        refs = item.get("run_refs", []) or []
        for ref in refs:
            bundle = related.get(ref)
            if bundle is None:
                problems.append(f"work item {item_id} references missing run {ref}")
                continue
            if ref != run_id:
                child_state = bundle.get("state") or {}
                parent = child_state.get("parent") or {}
                if parent.get("run_id") != run_id or parent.get("item_id") != item_id:
                    problems.append(f"child run {ref} does not link back to {run_id}/{item_id}")

        if item.get("status") == "done":
            if not refs:
                problems.append(f"done work item {item_id} has no run_refs")
            if item.get("remaining_scope"):
                problems.append(f"done work item {item_id} still has remaining_scope")
            if not (contract.get("approved_by") and contract.get("approved_at")):
                problems.append(f"done work item {item_id} has no approved contract")
            done_index = _matching_done_event(item, evidence, run_id, artifact_hashes)
            if done_index is None:
                problems.append(f"done work item {item_id} lacks matching work_item_done evidence")
            result_by_prop = {
                result.get("property_id"): result.get("status")
                for result in ((parity or {}).get("results", []) or [])
            }
            for prop_id in item.get("contract_properties", []) or []:
                if result_by_prop.get(prop_id) != "pass":
                    problems.append(f"done work item {item_id} lacks passing parity for {prop_id}")

    parent = state.get("parent") or {}
    if parent:
        parent_id = parent.get("run_id")
        parent_item_id = parent.get("item_id")
        parent_bundle = related.get(parent_id)
        if parent_bundle is None:
            problems.append(f"parent run {parent_id} does not exist")
        else:
            parent_state = parent_bundle.get("state") or {}
            parent_items = {
                item.get("id"): item for item in (parent_state.get("items", []) or [])
            }
            parent_item = parent_items.get(parent_item_id)
            if parent_item is None:
                problems.append(f"parent run {parent_id} has no work item {parent_item_id}")
            elif run_id not in (parent_item.get("run_refs") or []):
                problems.append(f"parent work item {parent_item_id} does not reference child run {run_id}")

    for item in items:
        status = item.get("status")
        if status not in {"deferred", "cancelled"}:
            continue
        has_decision = any(
            entry.get("action") == f"work_item_{status}"
            and (entry.get("details") or {}).get("run_id") == run_id
            and (entry.get("details") or {}).get("item_id") == item.get("id")
            for entry in evidence
        )
        if not has_decision:
            problems.append(f"work item {item.get('id')} is {status} without recorded decision evidence")

    if final:
        verification_indexes = _final_verification_indexes(evidence, run_id, artifact_hashes)
        if not verification_indexes:
            problems.append(
                "final run lacks passing run-bound final verification evidence for current artifacts"
            )
        elif terminal_event_indexes and max(verification_indexes) <= max(terminal_event_indexes):
            problems.append("final verification evidence precedes the last terminal work-item event")

    return problems


def analyze(
    request,
    contract,
    plan,
    parity,
    *,
    state=None,
    manifest=None,
    evidence=None,
    related=None,
    request_sha256=None,
    final: bool = False,
) -> list[str]:
    """Return cross-artifact consistency problems."""
    problems: list[str] = []
    if final and parity is None:
        problems.append("final run is missing parity-report.json")

    # Contract uses contract_id; the other artifacts use run_id.
    run_ids = {
        name: value
        for name, value in (
            ("request", request.get("run_id") if request else None),
            ("manifest", manifest.get("run_id") if manifest else None),
            ("state", state.get("run_id") if state else None),
            ("contract", contract.get("contract_id") if contract else None),
            ("plan", plan.get("run_id") if plan else None),
            ("parity", parity.get("run_id") if parity else None),
        )
        if value
    }
    if len(set(run_ids.values())) > 1:
        problems.append(f"run_id mismatch across artifacts: {run_ids}")

    if state and request_sha256 and state.get("request_sha256") != request_sha256:
        problems.append("run state request_sha256 does not match migration-request.json")

    props = contract.get("properties", []) if contract else []
    prop_id_list = [p.get("id") for p in props if p.get("id")]
    for prop_id, count in Counter(prop_id_list).items():
        if count > 1:
            problems.append(f"contract contains duplicate property {prop_id}")
    all_prop_ids = set(prop_id_list)
    kind = {p.get("id"): p.get("preservation") for p in props if p.get("id")}
    to_verify = {pid for pid, label in kind.items() if label != "unknown"}
    contract_run_id = contract.get("contract_id") if contract else None
    deferred_unknowns = set()
    for entry in evidence or []:
        details = entry.get("details") or {}
        if (
            entry.get("action") == "property_deferred"
            and entry.get("result") == "pass"
            and details.get("run_id") == contract_run_id
            and details.get("decision") == "defer"
            and isinstance(details.get("property_id"), str)
        ):
            deferred_unknowns.add(details.get("property_id"))

    for pid, label in kind.items():
        if label == "unknown" and pid not in deferred_unknowns:
            problems.append(f"property {pid} is unresolved (preservation=unknown)")
    for pid in sorted(deferred_unknowns - set(kind)):
        problems.append(f"deferred evidence references unknown contract property {pid}")
    for pid in sorted(deferred_unknowns & {pid for pid, label in kind.items() if label != "unknown"}):
        problems.append(f"property {pid} is deferred but preservation is '{kind[pid]}', not 'unknown'")

    if final and contract and not (contract.get("approved_by") and contract.get("approved_at")):
        problems.append("final contract is missing approved_by or approved_at")

    # --- plan <-> contract ---
    if contract and plan:
        units = plan.get("units", []) or []
        planned_props = {cp for u in units for cp in (u.get("contract_properties") or [])}

        for uid, cp in [
            (u.get("id"), cp) for u in units for cp in (u.get("contract_properties") or [])
        ]:
            if cp not in all_prop_ids:
                problems.append(f"plan unit {uid} references unknown contract property {cp}")

        for pid in sorted(to_verify - planned_props):
            problems.append(f"property {pid} ({kind[pid]}) is not owned by any plan unit")

        # plan internal integrity
        unit_id_list = [u.get("id") for u in units if u.get("id")]
        for unit_id, count in Counter(unit_id_list).items():
            if count > 1:
                problems.append(f"plan contains duplicate unit {unit_id}")
        unit_ids = set(unit_id_list)
        for pilot in plan.get("pilot_units", []) or []:
            if pilot not in unit_ids:
                problems.append(f"pilot_units lists unknown unit {pilot}")
        for u in units:
            for dep in u.get("depends_on", []) or []:
                if dep not in unit_ids:
                    problems.append(f"unit {u.get('id')} depends_on unknown unit {dep}")
        if _has_cycle(units):
            problems.append("plan units contain a dependency cycle (fan-out cannot order)")

    # --- parity <-> contract ---
    if parity:
        results = parity.get("results", []) or []
        result_ids = [result.get("property_id") for result in results if result.get("property_id")]
        for property_id, count in Counter(result_ids).items():
            if count > 1:
                problems.append(f"parity report contains duplicate result for {property_id}")
        verified = set(result_ids)

        if contract:
            for pid in sorted(to_verify - verified):
                problems.append(f"property {pid} ({kind[pid]}) has no result in the parity report")
            for r in results:
                pid = r.get("property_id")
                if pid not in all_prop_ids:
                    problems.append(f"parity report scores unknown property {pid}")

        # count + verdict sanity (only when a results array is actually present)
        if results:
            n = len(results)
            passed = sum(1 for r in results if r.get("status") == "pass")
            mismatches = sum(1 for r in results if r.get("status") == "mismatch")
            if parity.get("total_properties") != n:
                problems.append(
                    f"parity total_properties={parity.get('total_properties')} but results has {n} entries"
                )
            if parity.get("passed") != passed:
                problems.append(
                    f"parity passed={parity.get('passed')} but {passed} results have status=pass"
                )
            if parity.get("mismatches") != mismatches:
                problems.append(
                    f"parity mismatches={parity.get('mismatches')} but {mismatches} results have status=mismatch"
                )
        if parity.get("verdict") == "pass" and parity.get("mismatches"):
            problems.append(
                f"parity verdict=pass but mismatches={parity.get('mismatches')} (must be 0)"
            )
        if final:
            if parity.get("verdict") != "pass":
                problems.append(f"final parity verdict is '{parity.get('verdict')}', not 'pass'")
            if parity.get("mismatches") != 0:
                problems.append(f"final parity has mismatches={parity.get('mismatches')}, not 0")
            statuses = {
                property_id: [r.get("status") for r in results if r.get("property_id") == property_id]
                for property_id in to_verify
            }
            for property_id, property_statuses in statuses.items():
                if property_statuses != ["pass"]:
                    problems.append(
                        f"final property {property_id} requires exactly one pass result; got {property_statuses}"
                    )

    # --- intentional_changes <-> contract ---
    if contract:
        changes = contract.get("intentional_changes", []) or []
        refs = {c.get("property_ref") for c in changes}
        for c in changes:
            ref = c.get("property_ref")
            if ref not in all_prop_ids:
                problems.append(f"intentional_change {c.get('id')} references unknown property {ref}")
            elif kind.get(ref) != "intentionally-change":
                problems.append(
                    f"intentional_change {c.get('id')} targets {ref} but its preservation is '{kind.get(ref)}', not 'intentionally-change'"
                )
        for p in props:
            if p.get("preservation") == "intentionally-change" and p.get("id") not in refs:
                problems.append(
                    f"property {p.get('id')} is marked intentionally-change but has no intentional_changes entry"
                )
        # approval gate when the request demands per-change approval
        if request and request.get("approval_policy") == "each_semantic_change":
            for c in changes:
                if not c.get("approved"):
                    problems.append(f"intentional_change {c.get('id')} is not approved (policy: each_semantic_change)")

    if state and manifest and contract and plan:
        problems.extend(
            _state_problems(
                state,
                manifest,
                contract,
                plan,
                parity,
                evidence or [],
                related or {},
                final=final,
            )
        )

    return problems


def _child_graph_problems(root_run_id: str, related: dict[str, dict]) -> list[str]:
    """Require every child of a done item to pass the same complete final gate."""
    problems: list[str] = []
    queue = deque([(root_run_id, (root_run_id,))])
    validated: set[str] = set()
    while queue:
        parent_id, ancestry = queue.popleft()
        parent = related.get(parent_id) or {}
        parent_state = parent.get("state") or {}
        for item in parent_state.get("items", []) or []:
            if item.get("status") != "done":
                continue
            for child_id in item.get("run_refs", []) or []:
                if child_id == parent_id:
                    continue
                if child_id in ancestry:
                    problems.append(f"run-state child graph contains a cycle through {child_id}")
                    continue
                child = related.get(child_id)
                if child is None:
                    continue
                if child_id not in validated:
                    child_shape = _schema_problems(
                        child, f"child run {child_id}", FINAL_REQUIRED
                    )
                    if child_shape:
                        problems.extend(child_shape)
                    else:
                        child_problems = analyze(
                            child.get("request"),
                            child.get("contract"),
                            child.get("plan"),
                            child.get("parity"),
                            state=child.get("state"),
                            manifest=child.get("manifest"),
                            evidence=child.get("evidence"),
                            related=related,
                            request_sha256=child.get("_request_sha256"),
                            final=True,
                        )
                        problems.extend(f"child run {child_id}: {problem}" for problem in child_problems)
                    validated.add(child_id)
                queue.append((child_id, ancestry + (child_id,)))
    return problems


def analyze_run(run_dir: Path, *, final: bool = False) -> int:
    if not run_dir.is_dir():
        print(f"not a directory: {run_dir}")
        return 2

    try:
        loaded = _bundle(run_dir)
    except (OSError, UnicodeError, RuntimeError, ValueError, YAMLError) as exc:
        print(f"FAIL run artifacts: cannot load ({exc})")
        return 2

    required = (
        FINAL_REQUIRED
        if final
        else {"request", "manifest", "state", "contract", "plan", "evidence"}
    )
    missing = sorted(required - loaded.keys())
    if missing:
        filenames = ["evidence.jsonl" if key == "evidence" else FILES[key] for key in missing]
        print("missing required artifacts:", ", ".join(filenames))
        return 2

    shape_problems = _schema_problems(loaded, run_dir.name, required)
    if shape_problems:
        for problem in shape_problems:
            print(f"FAIL {problem}")
        return 2

    identity_problems = _identity_problems(loaded, run_dir.name)
    state = loaded["state"]
    current_run_id = state["run_id"]
    initial_related = {
        ref for item in state["items"] for ref in (item.get("run_refs", []) or [])
    }
    parent = state.get("parent") or {}
    if parent.get("run_id"):
        initial_related.add(parent["run_id"])

    related: dict[str, dict] = {current_run_id: loaded}
    related_required = {"request", "manifest", "state", "contract", "plan", "evidence"}
    pending = deque(sorted(initial_related - {current_run_id}))
    while pending:
        related_id = pending.popleft()
        if related_id in related:
            continue
        related_dir = _safe_run_dir(run_dir.parent, related_id)
        if related_dir is None:
            print(f"FAIL related run ID or path is unsafe: {related_id!r}")
            return 2
        if not related_dir.is_dir():
            continue
        try:
            bundle = _bundle(related_dir)
        except (OSError, UnicodeError, RuntimeError, ValueError, YAMLError) as exc:
            print(f"FAIL related run {related_id}: cannot load ({exc})")
            return 2
        related_shape = _schema_problems(bundle, f"related run {related_id}", related_required)
        if related_shape:
            for problem in related_shape:
                print(f"FAIL {problem}")
            return 2
        identity_problems.extend(_identity_problems(bundle, related_id))
        related[related_id] = bundle
        related_state = bundle["state"]
        discovered = {
            ref
            for item in related_state["items"]
            for ref in (item.get("run_refs", []) or [])
        }
        related_parent = related_state.get("parent") or {}
        if related_parent.get("run_id"):
            discovered.add(related_parent["run_id"])
        pending.extend(sorted(discovered - related.keys()))

    request_sha256 = loaded["_request_sha256"]
    print("cross-checking:", ", ".join(sorted(key for key in loaded if not key.startswith("_"))))
    problems = identity_problems + analyze(
        loaded.get("request"),
        loaded.get("contract"),
        loaded.get("plan"),
        loaded.get("parity"),
        state=state,
        manifest=loaded.get("manifest"),
        evidence=loaded.get("evidence"),
        related=related,
        request_sha256=request_sha256,
        final=final,
    )
    problems.extend(_child_graph_problems(current_run_id, related))
    if problems:
        for p in problems:
            print(f"  FAIL: {p}")
        print(f"\n{len(problems)} consistency problem(s) found.")
        return 1
    print("\nArtifacts are mutually consistent.")
    return 0


def _selfcheck() -> int:
    """Smallest runnable proof: a coherent set passes, broken sets are caught."""

    def check(condition: bool, message: str) -> None:
        if not condition:
            raise RuntimeError(f"selfcheck failed: {message}")

    good_contract = {
        "contract_id": "R",
        "properties": [
            {"id": "P001", "preservation": "preserve"},
            {"id": "P002", "preservation": "intentionally-change"},
            {"id": "P003", "preservation": "introduce"},  # greenfield behavior
        ],
        "intentional_changes": [
            {"id": "C001", "property_ref": "P002", "approved": True}
        ],
    }
    good_plan = {
        "run_id": "R", "pilot_units": ["U001"],
        "units": [
            {"id": "U001", "contract_properties": ["P001"], "depends_on": []},
            {"id": "U002", "contract_properties": ["P002"], "depends_on": ["U001"]},
            {"id": "U003", "contract_properties": ["P003"], "depends_on": []},
        ],
    }
    # Every resolved property is owned and scored, regardless of preservation label.
    good_parity = {
        "run_id": "R", "verdict": "pass", "total_properties": 3, "passed": 3, "mismatches": 0,
        "results": [
            {"property_id": "P001", "status": "pass"},
            {"property_id": "P002", "status": "pass"},
            {"property_id": "P003", "status": "pass"},
        ],
    }
    good_request = {"run_id": "R", "approval_policy": "each_semantic_change"}
    check(analyze(good_request, good_contract, good_plan, good_parity) == [], "coherent set must pass")
    approved_contract = {**good_contract, "approved_by": "reviewer", "approved_at": "2026-01-01T00:00:00Z"}
    check(analyze(good_request, approved_contract, good_plan, good_parity, final=True) == [], "approved final set must pass")
    check(
        any("missing approved_by" in p for p in analyze(good_request, good_contract, good_plan, good_parity, final=True)),
        "unapproved final contract must fail",
    )
    deferred_contract = {
        **good_contract,
        "properties": good_contract["properties"] + [
            {"id": "P004", "preservation": "unknown", "oracle": {"kind": "unresolved"}}
        ],
    }
    deferred_evidence = [{
        "action": "property_deferred",
        "result": "pass",
        "details": {"run_id": "R", "property_id": "P004", "decision": "defer"},
    }]
    check(
        analyze(
            good_request, deferred_contract, good_plan, good_parity,
            evidence=deferred_evidence,
        ) == [],
        "explicitly deferred unknown must be excluded from verification accounting",
    )
    check(
        any("P004 is unresolved" in problem for problem in analyze(
            good_request, deferred_contract, good_plan, good_parity,
        )),
        "unknown without run-bound defer evidence must fail",
    )

    # Break every relationship at once and confirm each is reported.
    bad_contract = {
        "contract_id": "R",
        "properties": [
            {"id": "P001", "preservation": "preserve"},
            {"id": "P002", "preservation": "intentionally-change"},  # no change entry
            {"id": "P003", "preservation": "introduce"},  # unowned + unscored
        ],
        "intentional_changes": [{"id": "C009", "property_ref": "P404", "approved": False}],
    }
    bad_plan = {
        "run_id": "R2",  # run_id mismatch
        "pilot_units": ["U999"],  # unknown pilot
        "units": [
            {"id": "U001", "contract_properties": ["P404"], "depends_on": ["U002"]},  # unknown prop
            {"id": "U002", "contract_properties": [], "depends_on": ["U001"]},  # cycle w/ U001
        ],
    }
    bad_parity = {
        "run_id": "R", "verdict": "pass", "total_properties": 5, "passed": 5, "mismatches": 3,
        "results": [{"property_id": "P404", "status": "mismatch"}],  # unknown + counts wrong
    }
    problems = analyze(good_request, bad_contract, bad_plan, bad_parity)
    needles = [
        "run_id mismatch",
        "references unknown contract property P404",
        "property P001 (preserve) is not owned",
        "property P003 (introduce) is not owned by any plan unit",
        "property P003 (introduce) has no result in the parity report",
        "pilot_units lists unknown unit U999",
        "dependency cycle",
        "scores unknown property P404",
        "total_properties=5 but results has 1",
        "verdict=pass but mismatches=3",
        "intentional_change C009 references unknown property P404",
        "P002 is marked intentionally-change but has no intentional_changes entry",
        "not approved",
    ]
    for needle in needles:
        check(any(needle in p for p in problems), f"missed {needle}; got {problems}")

    # Progress state is a resumable view: pending work survives, and code alone is not completion.
    state = {
        "run_id": "R",
        "request_sha256": "hash",
        "focus_item": "W004",
        "next_action": "Start context compaction",
        "items": [
            {
                "id": "W001", "title": "Completed pilot", "status": "done", "run_refs": ["R"],
                "contract_properties": ["P001", "P002", "P003"],
                "plan_units": ["U001", "U002", "U003"],
            },
            {"id": "W004", "title": "Context compaction", "status": "pending", "run_refs": []},
        ],
    }
    state_evidence = [
        {
            "action": "work_items_initialized",
            "details": {"run_id": "R", "items": [
                {"id": "W001", "title": "Completed pilot"},
                {"id": "W004", "title": "Context compaction"},
            ]},
        },
        {
            "action": "approval_recorded",
            "result": "pass",
            "details": {
                "run_id": "R", "approved_by": "reviewer",
                "approved_at": "2026-01-01T00:00:00Z", "contract_sha256": "c",
            },
        },
        {
            "action": "work_item_done",
            "details": {
                "run_id": "R",
                "item_id": "W001",
                "contract_properties": ["P001", "P002", "P003"],
                "plan_units": ["U001", "U002", "U003"],
                "run_refs": ["R"],
                "artifact_hashes": {"contract": "c", "plan": "p", "parity": "y"},
            },
        },
    ]
    for index, entry in enumerate(state_evidence):
        entry["timestamp"] = f"2026-01-01T00:00:0{index}Z"
    state_args = {
        "state": state,
        "manifest": {"run_id": "R", "status": "implementing"},
        "evidence": state_evidence,
        "related": {"R": {"_hashes": {"contract": "c", "plan": "p", "parity": "y"}}},
        "request_sha256": "hash",
    }
    check(
        analyze(good_request, approved_contract, good_plan, good_parity, **state_args) == [],
        "coherent progress state must pass",
    )

    forgotten = {**state, "items": state["items"][:1]}
    forgotten_problems = analyze(
        good_request, approved_contract, good_plan, good_parity,
        **{**state_args, "state": forgotten},
    )
    check(any("W004 is missing" in problem for problem in forgotten_problems), "forgotten W004 must fail")

    unverified = {
        **state,
        "focus_item": "W004",
        "items": [
            {**state["items"][0], "contract_properties": ["P001", "P002", "P003"]},
            state["items"][1],
        ],
    }
    unverified_problems = analyze(
        good_request, approved_contract, good_plan, None,
        **{**state_args, "state": unverified},
    )
    check(any("lacks passing parity" in problem for problem in unverified_problems), "unverified done item must fail")
    check(any("final run has unfinished work item W004" in problem for problem in analyze(
        good_request, approved_contract, good_plan, good_parity,
        **state_args, final=True,
    )), "unfinished final state must fail")

    no_done_evidence = analyze(
        good_request,
        approved_contract,
        good_plan,
        good_parity,
        **{**state_args, "evidence": state_evidence[:1]},
    )
    check(
        any("lacks matching work_item_done evidence" in problem for problem in no_done_evidence),
        "done state without completion evidence must fail",
    )
    failed_parity = {
        **good_parity,
        "verdict": "fail",
        "passed": 2,
        "mismatches": 1,
        "results": [
            {"property_id": "P001", "status": "pass"},
            {"property_id": "P002", "status": "mismatch"},
            {"property_id": "P003", "status": "pass"},
        ],
    }
    check(
        any("final parity verdict" in problem for problem in analyze(
            good_request, approved_contract, good_plan, failed_parity, final=True,
        )),
        "failed final parity must fail",
    )
    check(_safe_run_dir(Path("/tmp/runs"), "../escape") is None, "unsafe run ID must be rejected")
    added_item = {
        "id": "W005", "title": "Added later", "status": "done", "run_refs": ["R"],
        "contract_properties": [], "plan_units": [],
    }
    added_evidence = [
        {"action": "work_item_added", "details": {"run_id": "R", "item_id": "W005", "title": "Added later"}},
        {"action": "work_item_done", "details": {
            "run_id": "R", "item_id": "W005", "contract_properties": [], "plan_units": [],
            "run_refs": ["R"], "artifact_hashes": {"contract": "c", "plan": "p", "parity": "y"},
        }},
    ]
    check(
        _matching_done_event(
            added_item, added_evidence, "R", {"contract": "c", "plan": "p", "parity": "y"}
        ) is not None,
        "dynamically added item must accept later completion evidence",
    )

    completed_state = {
        **state,
        "items": [state["items"][0]],
        "focus_item": None,
        "next_action": None,
    }
    completed_state.pop("focus_item")
    completed_state.pop("next_action")
    completion_evidence = [
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "action": "work_items_initialized",
            "details": {"run_id": "R", "items": [{"id": "W001", "title": "Completed pilot"}]},
        },
        state_evidence[1],
        state_evidence[2],
        {
            "timestamp": "2026-01-01T00:00:03Z",
            "action": "final_verification",
            "result": "pass",
            "details": {
                "run_id": "R",
                "artifact_hashes": {"contract": "c", "plan": "p", "parity": "y"},
                "commands": [{"command": "check", "exit_code": 0}],
            },
        },
    ]
    completed_args = {
        **state_args,
        "state": completed_state,
        "manifest": {"run_id": "R", "status": "complete"},
        "evidence": completion_evidence,
    }
    check(
        analyze(
            good_request, approved_contract, good_plan, good_parity,
            **completed_args, final=True,
        ) == [],
        "chronological, hash-bound final evidence must pass",
    )
    approval_after_done = [
        completion_evidence[0], completion_evidence[2],
        completion_evidence[1], completion_evidence[3],
    ]
    check(
        any("approval evidence before completion" in problem for problem in analyze(
            good_request, approved_contract, good_plan, good_parity,
            **{**completed_args, "evidence": approval_after_done}, final=True,
        )),
        "approval after completion must fail",
    )
    preapproval_duplicate = [
        completion_evidence[0], completion_evidence[2], completion_evidence[1],
        completion_evidence[2], completion_evidence[3],
    ]
    check(
        any("approval evidence before completion" in problem for problem in analyze(
            good_request, approved_contract, good_plan, good_parity,
            **{**completed_args, "evidence": preapproval_duplicate}, final=True,
        )),
        "later completion must not hide pre-approval completion",
    )
    verification_before_done = [
        completion_evidence[0], completion_evidence[1],
        completion_evidence[3], completion_evidence[2],
    ]
    check(
        any("precedes the last terminal" in problem for problem in analyze(
            good_request, approved_contract, good_plan, good_parity,
            **{**completed_args, "evidence": verification_before_done}, final=True,
        )),
        "final verification before completion must fail",
    )
    terminal_after_verification = completion_evidence + [completion_evidence[2]]
    check(
        any("precedes the last terminal" in problem for problem in analyze(
            good_request, approved_contract, good_plan, good_parity,
            **{**completed_args, "evidence": terminal_after_verification}, final=True,
        )),
        "terminal evidence after final verification must fail",
    )
    unknown_terminal = {
        **completion_evidence[2],
        "details": {**completion_evidence[2]["details"], "item_id": "W999"},
    }
    unknown_terminal_problems = analyze(
        good_request, approved_contract, good_plan, good_parity,
        **{**completed_args, "evidence": completion_evidence + [unknown_terminal]},
        final=True,
    )
    check(
        any("unknown work item W999" in problem for problem in unknown_terminal_problems)
        and any("precedes the last terminal" in problem for problem in unknown_terminal_problems),
        "unknown terminal evidence after verification must fail",
    )
    predefinition_cancel = {
        "timestamp": "2026-01-01T00:00:00Z",
        "action": "work_item_cancelled",
        "details": {"run_id": "R", "item_id": "W001"},
    }
    check(
        any("precedes its definition" in problem for problem in analyze(
            good_request, approved_contract, good_plan, good_parity,
            **{**completed_args, "evidence": [predefinition_cancel] + completion_evidence},
            final=True,
        )),
        "terminal evidence before item definition must fail",
    )
    newer_event = {
        "timestamp": "2026-01-01T00:01:00Z",
        "action": "final_verification",
        "result": "pass",
    }
    older_event = {**newer_event, "timestamp": "2026-01-01T00:00:00Z"}
    check(
        any("timestamp regresses" in problem for problem in _evidence_order_problems(
            [newer_event, older_event]
        )),
        "appended stale evidence timestamp must fail",
    )
    check(
        any("replays a lifecycle event" in problem for problem in _evidence_order_problems(
            [newer_event, newer_event]
        )),
        "exact lifecycle-event replay must fail",
    )
    stale_verification = {
        **completion_evidence[3],
        "details": {
            **completion_evidence[3]["details"],
            "artifact_hashes": {"contract": "stale", "plan": "p", "parity": "y"},
        },
    }
    check(
        any("current artifacts" in problem for problem in analyze(
            good_request, approved_contract, good_plan, good_parity,
            **{**completed_args, "evidence": completion_evidence[:3] + [stale_verification]},
            final=True,
        )),
        "stale final-verification hashes must fail",
    )
    check(
        any("missing parity-report.json" in problem for problem in analyze(
            good_request, approved_contract, good_plan, None, final=True,
        )),
        "final analysis without parity must fail",
    )
    child_gate_problems = _child_graph_problems(
        "ROOT",
        {
            "ROOT": {"state": {"items": [{"status": "done", "run_refs": ["CHILD"]}]}},
            "CHILD": {},
        },
    )
    check(
        any("child run CHILD is missing parity" in problem for problem in child_gate_problems),
        "completed child without parity must fail",
    )
    check(
        any("child run CHILD is missing repro" in problem for problem in child_gate_problems)
        and any("child run CHILD is missing inventory" in problem for problem in child_gate_problems),
        "completed child without final artifacts must fail",
    )

    with tempfile.TemporaryDirectory() as temporary:
        run_dir = Path(temporary) / "run"
        run_dir.mkdir()
        outside = Path(temporary) / "outside.json"
        outside.write_text("{}")
        (run_dir / "manifest.json").symlink_to(outside)
        try:
            _artifact_path(run_dir, "manifest.json")
        except ValueError:
            pass
        else:
            check(False, "symlinked artifact must be rejected")

    print(f"selfcheck OK ({len(problems)} artifact problems plus progress-state failures detected)")
    return 0


def main() -> int:
    if sys.argv[1:] == ["--selfcheck"]:
        return _selfcheck()
    if len(sys.argv) == 2:
        return analyze_run(Path(sys.argv[1]).resolve())
    if len(sys.argv) == 3 and sys.argv[1] == "--final":
        return analyze_run(Path(sys.argv[2]).resolve(), final=True)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
