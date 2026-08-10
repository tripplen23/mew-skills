# Proposed skill changes — run 20260801-181337-217cab5

Golden task 2 clean re-run (people-api Python→Rust), 11/11 parity via
http_diff_test.py (mew-skills e00f584, PR #12 deliverable).

## Open proposals (minor, parked — promote later in one batch)

### L-A: HTTP harness — servers must not share state files (universal, hard)
Two live servers started in the same cwd silently shared `people.db`; the
candidate then observed baseline writes/deletes (P004 POST and P009 DELETE
mismatched). Fix: document in SKILL.md that baseline and candidate must use
separate data files (e.g. distinct `--db`/env paths), or make the harness
copy the sequence state per side.
- Oracle: differential (hard) | Source run: 20260801-181337-217cab5
- Review status: pending user review

### L-B: HTTP harness — timestamps normalizer is mandatory for live servers (universal, soft)
Two live servers always emit different `timestamp` values (20s skew caused
P006 to fail without the normalizer). The `timestamps` normalizer exists
but SKILL.md's example sequence does not show it on GET/PUT cases.
Fix: show `normalize: ["timestamps", "json_order"]` on read/update cases in
the SKILL.md example.
- Oracle: differential (hard) | Source run: 20260801-181337-217cab5
- Review status: pending user review
