# Measurements — run 20260801-181337-217cab5 (GT2 clean re-run)

Per-task measurements recorded by `measure_metrics.py` (mew-skills,
mew#104) instrumenting the Hermes engine state.db.

## Totals (engine-recorded, session-level)
| Metric | Value |
|---|---|
| Sessions | `20260801_181559_e95755`, `20260801_181558_dd9947` |
| Model | deepseek-v4-flash (provider: deepseek) |
| Input tokens | 76,383 |
| Output tokens | 21,059 |
| Cache-read tokens | 965,120 |
| Reasoning tokens | 12,259 |
| API calls | 29 |
| Retry count (rewind proxy) | 0 |
| Wall clock | 190.05 s |
| Estimated cost | $0.019292 (cost_status: estimated) |

## Phase wall-clock (evidence timestamps)
| Phase | Wall clock (s) |
|---|---|
| reproduce | 205.56 |
| contract | 411.33 |
| verify | 525.98 |

Phase token splits: **not available** — the Hermes engine does not store
per-message `token_count` (NULL); session-level totals above are the
authoritative engine-recorded numbers. Phase attribution note is carried
in `metrics.json` per phase.

## Artifacts
- `metrics.json` — schema-valid (schemas/metrics.schema.json)
- `evidence.jsonl` — `measurements_recorded` entry appended
