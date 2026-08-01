# Python -> Rust migration gotchas (stack:rust)

Conditionally loaded reference for planning Python→Rust ports. Every gotcha
carries provenance per skill-evolution.md: scope, oracle tier, source run,
and review status. Each was observed in a real migration run; none is
speculative. Lessons marked `proposed` were routed through
`proposed-skill-changes.md` and await maintainer approval.

## Timestamp parity: pin the chrono format string to datetime.isoformat()

> Scope: stack:rust. Oracle: hard. Learned: run 20260801-145954-217cab5. Review: proposed.

Python `datetime.utcnow().isoformat()` (marshmallow serialization) emits:

```text
2026-08-01T14:59:39.765321
```

- ISO-8601 UTC, **no timezone suffix** (`Z` or `+00:00`),
- exactly **6-digit microseconds** (`.765321`).

Rust chrono's `Utc::now().to_rfc3339()` appends `Z` and may vary precision
(`2026-08-01T14:59:39.765321Z`) — a differential mismatch if the contract
compares timestamp strings.

Correct target pattern (verified in run 20260801-145954-217cab5):

```rust
use chrono::Utc;
Utc::now().format("%Y-%m-%dT%H:%M:%S%.6f").to_string()
```

Rules:

1. Before implementing, pin the exact Python output format
   (`python -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec='microseconds'))"`)
   and translate it field-by-field into the chrono format string. Use
   `isoformat(timespec="microseconds")` for the probe — the default
   `timespec="auto"` omits the fractional part when microseconds are 0,
   which would hide the `.dddddd` requirement.
2. Use `%.6f` for fixed 6-digit microseconds — chrono `%f` alone is
   nanoseconds by default and would emit 9 digits.
3. No `Z` / timezone suffix unless the baseline emits one. `datetime.utcnow()`
   is naive; `datetime.now(timezone.utc)` adds `+00:00` (strip it with
   `.replace(tzinfo=None)` when the baseline shape is naive UTC).
4. Apply the same format string in seed, create, and update paths (the
   Python baseline uses `default=datetime.utcnow, onupdate=datetime.utcnow`).

## axum route params: `:param` (0.7) vs `{param}` (0.8)

> Scope: stack:rust. Oracle: hard. Learned: run 20260801-145954-217cab5. Review: proposed.

axum 0.7 route syntax uses `:person_id`; axum 0.8 changed to
`{person_id}`. Using `{param}` on axum 0.7 **fails silently**: the server
starts, no compile error, and every request to that route returns the
default 404 — which a differential harness will surface late and
misleadingly as a per-endpoint failure.

Observed in run 20260801-145954-217cab5: `{person_id}` on axum 0.7 → all
`/api/people/{id}` requests 404; fixed by switching to `:person_id`.

Rules:

1. Check the axum version in `Cargo.toml` before writing route strings.
2. Probe one path-param route with a real request (e.g.
   `curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/api/items/1`)
   early — before running the full differential harness — and confirm it
   returns 200/404 from your handler, not the framework default 404.
3. If a whole route family 404s with an empty body (not your problem+json
   shape), suspect route syntax before handler logic.

## Error body shapes: match the exact serialized form

> Scope: stack:rust. Oracle: hard. Learned: run 20260801-145954-217cab5. Review: proposed.

Connexion (Flask) emits RFC 9457 problem+json for `abort()`:

```json
{"type": "about:blank", "title": "Not Found", "detail": "...", "status": 404}
```

with `Content-Type: application/problem+json`. axum's default
`Json(...)` returns `application/json` — status and 4 body fields are what
differential compares; do not rely on the media type. A single operation
may have multiple distinct 404 wordings (observed: GET `"Person with
person_id X not found"`, PUT `"Person with id: X not found"`, DELETE
`"Person not found for id X"`) — each must be preserved exactly.

## POST returning 204: the spec may lie

> Scope: stack:rust. Oracle: hard. Learned: run 20260801-145954-217cab5. Review: proposed.

If a Python handler returns `None` (e.g. `create()` with no `return`),
Connexion responds **204 No Content** regardless of what swagger.yml
declares (people-api declared `201`). The Rust handler must return
`StatusCode::NO_CONTENT` with no body. Treat the running baseline as the
oracle (see behavior-contract Lesson 2); never port the spec's declared
status verbatim.

## DELETE returning 200 with text, not 204

> Scope: stack:rust. Oracle: hard. Learned: run 20260801-145954-217cab5. Review: proposed.

Flask `make_response("... deleted", 200)` returns `200` with a text body.
axum's idiomatic delete returns `204`. Preserve the actual baseline:
`(StatusCode::OK, format!("Person with id {} successfully deleted", id))`.

## Content-Type is NOT globally non-contractual

> Scope: stack:rust. Oracle: soft (guidance). Learned: run 20260801-145954-217cab5. Review: proposed.

The DELETE-200 example above ignores the media type (`text/html` vs
`text/plain`) only because that specific contract property declared body
text contractual and header comparison out of scope. Do not generalize:
header normalization is **property-specific**. By default, behavior-contract
captures exact response headers; ignore `Content-Type` (or any header) only
when the individual sequence property explicitly declares header
normalization or a status/body-only comparison.
