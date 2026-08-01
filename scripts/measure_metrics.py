#!/usr/bin/env python3
"""Per-task measurement harness for golden runs (mew#104).

Instruments the Hermes engine's SQLite state database (sessions,
session_model_usage, messages) to collect per-task measurements for a
golden run:

- context window per phase (approximated via message-token attribution);
- input/output/cache-read token counts (engine-recorded);
- retry count (agent-level rewind_count proxy);
- wall-clock time per phase and total;
- provider cost (estimated, engine-recorded).

Writes `metrics.json` (schema: schemas/metrics.schema.json) into the run
directory and appends one `measurements_recorded` evidence entry.

Usage:
    python3 scripts/measure_metrics.py --run-dir .mew/runs/<run_id> \
        [--state-db ~/.hermes/state.db]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PHASE_ORDER = ["ingest", "reproduce", "observe", "grill", "contract", "plan", "implement", "verify", "handoff"]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_ts(v):
    """Parse a Hermes timestamp (float epoch or ISO string) -> epoch float."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def load_evidence(run_dir: Path) -> list[dict]:
    ev = []
    p = run_dir / "evidence.jsonl"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    ev.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return ev


def phase_windows(evidence: list[dict]) -> dict[str, dict]:
    """phase -> {start_epoch, end_epoch} from evidence timestamps.

    Excludes the harness's own `measurements_recorded` entries — they are
    added after the run and would widen the window past the real run end.
    """
    buckets: dict[str, list[float]] = {}
    for e in evidence:
        if e.get("action") == "measurements_recorded":
            continue
        phase = e.get("phase")
        t = parse_ts(e.get("timestamp"))
        if phase and t is not None:
            buckets.setdefault(phase, []).append(t)
    windows = {}
    for phase, times in buckets.items():
        windows[phase] = {"start": min(times), "end": max(times)}
    return windows


def find_sessions(db_path: str, start_epoch: float, end_epoch: float) -> list[str]:
    """Sessions genuinely overlapping the run's time window.

    A session whose ended_at is NULL is still running; it can only match
    when the window lies inside [started_at, now] — but closed sessions
    that overlap the window are preferred (they are the run's sessions,
    not the long-lived interactive session that happens to span it).
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = conn.execute(
        """SELECT id, started_at, ended_at FROM sessions
           WHERE started_at <= ? AND (ended_at IS NULL OR ended_at >= ?)""",
        (end_epoch + 600, start_epoch - 600),
    ).fetchall()
    conn.close()
    # closed sessions overlapping the window first, then open ones
    def key(r):
        ended = parse_ts(r[2])
        return (0 if ended is not None else 1, r[1])
    return [r[0] for r in sorted(rows, key=key)]


def session_metrics(db_path: str, session_ids: list[str]) -> dict | None:
    if not session_ids:
        return None
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = []
    for sid in session_ids:
        row = conn.execute(
            """SELECT model, billing_provider, started_at, ended_at,
                       input_tokens, output_tokens, cache_read_tokens,
                       cache_write_tokens, reasoning_tokens, rewind_count,
                       estimated_cost_usd, actual_cost_usd, cost_status,
                       api_call_count
                FROM sessions WHERE id = ?""",
            (sid,),
        ).fetchone()
        if row:
            rows.append(row)
    conn.close()
    if not rows:
        return None

    model = rows[0][0]
    provider = rows[0][1]
    starts = [parse_ts(r[2]) for r in rows]
    ends = [parse_ts(r[3]) for r in rows]
    start = min(s for s in starts if s is not None)
    end = max((e for e in ends if e is not None), default=datetime.now(timezone.utc).timestamp())
    wall = max(end - start, 0.0)
    agg = {
        "input_tokens": sum(r[4] or 0 for r in rows),
        "output_tokens": sum(r[5] or 0 for r in rows),
        "cache_read_tokens": sum(r[6] or 0 for r in rows),
        "cache_write_tokens": sum(r[7] or 0 for r in rows),
        "reasoning_tokens": sum(r[8] or 0 for r in rows),
        "retry_count": sum(r[9] or 0 for r in rows),
        "estimated_cost_usd": round(sum(r[10] or 0.0 for r in rows), 6),
        "actual_cost_usd": round(sum(r[11] or 0.0 for r in rows), 6),
        "cost_status": rows[0][12],
        "api_call_count": sum(r[13] or 0 for r in rows),
    }
    return {
        "model": model,
        "billing_provider": provider,
        "wall_clock_seconds": round(wall, 2),
        **agg,
    }


def phase_attribution(db_path: str, session_ids: list[str], windows: dict[str, dict], run_end: float | None = None) -> list[dict]:
    """Attribute message tokens to phases by message timestamp.

    NOTE: the Hermes engine records message timestamps but not per-message
    token_count (column is NULL). Phase token splits are therefore only
    meaningful when the engine stores them; when every message has NULL
    token_count, phase tokens are reported as 0 with an explicit note and
    totals (engine-recorded at session level) remain authoritative.
    """
    if not session_ids:
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    placeholders = ",".join("?" * len(session_ids))
    msgs = conn.execute(
        f"SELECT timestamp, token_count, role FROM messages WHERE session_id IN ({placeholders})",
        session_ids,
    ).fetchall()
    conn.close()

    any_tokens = any(m[1] is not None for m in msgs)
    attribution_note = (
        "message-timestamp attribution via Hermes state.db (approximate)"
        if any_tokens
        else "engine records no per-message token_count; phase split unavailable, totals are session-level engine-recorded"
    )

    # build ordered phase boundary list
    boundaries = []
    for phase in PHASE_ORDER:
        if phase in windows:
            boundaries.append((windows[phase]["start"], phase))
    boundaries.sort()

    # extend the last phase to the session end so late messages attribute
    last_boundary = boundaries[-1][0] if boundaries else None
    final_end = run_end if run_end is not None else (last_boundary + 3600 if last_boundary is not None else None)

    phases: dict[str, dict] = {}
    for i, (ts, phase) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else (final_end if final_end is not None else float("inf"))
        phases[phase] = {
            "phase": phase,
            "start": ts,
            "end": end,
            "input_tokens": 0,
            "output_tokens": 0,
            "wall_clock_seconds": 0.0,
        }

    if any_tokens:
        for ts_raw, tokens, role in msgs:
            t = parse_ts(ts_raw)
            if t is None or tokens is None:
                continue
            for phase, p in phases.items():
                if p["start"] <= t < p["end"]:
                    if role == "assistant":
                        p["output_tokens"] += int(tokens)
                    elif role in ("user", "system", "tool"):
                        p["input_tokens"] += int(tokens)
                    break

    result = []
    for phase in PHASE_ORDER:
        if phase not in phases:
            continue
        p = phases[phase]
        wall = p["end"] - p["start"]
        result.append({
            "phase": phase,
            "wall_clock_seconds": round(wall if wall != float("inf") else 0.0, 2),
            "input_tokens": p["input_tokens"],
            "output_tokens": p["output_tokens"],
            "attribution": attribution_note,
        })
    return result


def append_evidence(run_dir: Path, run_id: str, totals: dict, session_ids: list[str]) -> None:
    entry = {
        "timestamp": iso_now(),
        "phase": "handoff",
        "action": "measurements_recorded",
        "result": "info",
        "details": {
            "run_id": run_id,
            "instrument": "measure_metrics.py (Hermes state.db)",
            "session_ids": session_ids,
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
            "cache_read_tokens": totals["cache_read_tokens"],
            "retry_count": totals["retry_count"],
            "wall_clock_seconds": totals["wall_clock_seconds"],
            "estimated_cost_usd": totals["estimated_cost_usd"],
        },
    }
    ev_path = run_dir / "evidence.jsonl"
    lines = [l for l in ev_path.read_text().splitlines() if l.strip()]
    kept = [l for l in lines if not (
        (json.loads(l).get("action") == "measurements_recorded") if l.strip().startswith("{") else False
    )]
    kept.append(json.dumps(entry))
    ev_path.write_text("\n".join(kept) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-task measurement harness for golden runs")
    ap.add_argument("--run-dir", required=True, help="path to .mew/runs/<run_id>")
    ap.add_argument("--state-db", default=str(Path.home() / ".hermes" / "state.db"))
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    run_id = run_dir.name

    evidence = load_evidence(run_dir)
    if not evidence:
        print("ERROR: no evidence.jsonl in run dir")
        return 1

    windows = phase_windows(evidence)
    if not windows:
        print("ERROR: no phase timestamps in evidence.jsonl")
        return 1

    all_ts = [t for w in windows.values() for t in (w["start"], w["end"])]
    session_ids = find_sessions(args.state_db, min(all_ts), max(all_ts))
    if not session_ids:
        print(f"WARNING: no Hermes sessions overlap run {run_id} time window")

    # keep only sessions that genuinely belong to the run: closed, with
    # recorded tokens, overlapping the window. Open long-lived interactive
    # sessions are excluded so their tokens are never attributed here.
    conn = sqlite3.connect(f"file:{args.state_db}?mode=ro", uri=True)
    kept = []
    for sid in session_ids:
        row = conn.execute(
            "SELECT started_at, ended_at, input_tokens, output_tokens FROM sessions WHERE id = ?",
            (sid,),
        ).fetchone()
        if not row:
            continue
        ended = parse_ts(row[1])
        started = parse_ts(row[0])
        tokens = (row[2] or 0) + (row[3] or 0)
        if (
            ended is not None
            and started is not None
            and tokens > 0
            and started <= max(all_ts) + 600
            and ended >= min(all_ts) - 600
        ):
            kept.append(sid)
    conn.close()
    session_ids = kept
    print(f"run sessions: {session_ids}")

    sess = session_metrics(args.state_db, session_ids)
    # run_end = session end epoch for attribution extension
    conn = sqlite3.connect(f"file:{args.state_db}?mode=ro", uri=True)
    ends = []
    for sid in session_ids:
        r = conn.execute("SELECT ended_at FROM sessions WHERE id = ?", (sid,)).fetchone()
        if r and r[0] is not None:
            ends.append(parse_ts(r[0]))
    conn.close()
    run_end = max(ends) if ends else None
    phases = phase_attribution(args.state_db, session_ids, windows, run_end=run_end)

    totals = {
        "input_tokens": sess["input_tokens"] if sess else 0,
        "output_tokens": sess["output_tokens"] if sess else 0,
        "cache_read_tokens": sess["cache_read_tokens"] if sess else 0,
        "retry_count": sess["retry_count"] if sess else 0,
        "estimated_cost_usd": sess["estimated_cost_usd"] if sess else 0.0,
        "wall_clock_seconds": sess["wall_clock_seconds"] if sess else 0.0,
    }

    report = {
        "run_id": run_id,
        "measured_at": iso_now(),
        "source": {
            "instrument": "measure_metrics.py (Hermes engine state.db)",
            "state_db": args.state_db,
            "session_ids": session_ids,
        },
        "session": sess or {},
        "totals": totals,
        "phases": phases,
    }

    out = run_dir / "metrics.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"metrics.json written: {out}")
    print(json.dumps(totals, indent=2))

    append_evidence(run_dir, run_id, totals, session_ids)
    print("evidence entry appended: measurements_recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
