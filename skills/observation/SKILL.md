---
name: observation
description: "Captures authorized black-box runtime behavior for reconstruction, clone, or parity work when source is unavailable or intentionally excluded. Use for an explicitly authorized running web app, TUI, mobile or desktop app, or device whose executable behavior or interactive and visual states must be reproduced. Do not trigger for generic observation, product research, screenshots alone, source-code migration, or casual requests such as observe this. Uses a surface-neutral channel model and ships a Web/Playwright profile."
license: MIT
metadata:
  author: tripplen23
  version: "0.3.0"
  mew-phase: OBSERVE+VERIFY
---

# Observation

## Purpose

Capture defensible behavior evidence from an authorized running system for black-box reconstruction. The model is surface-neutral; the shipped driver profile is Web/Playwright. Vision may corroborate captured evidence but never establishes parity.

## Authorization gate

Before interacting with the reference, record that the user owns it, has license permission, or has explicit approval to reconstruct and test it. Also define the allowed screens, flows, accounts, endpoints, and data. Stop if authorization or scope is missing.

Authorization to inspect a reference does not automatically make it an oracle. The handoff rules below separately require a recorded executable comparison before using `oracle.kind: authorized-reference`.

## Evidence channels

| Channel             | Captures                                                                            | Strength                                                                       |
| ------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| C1 — Structure      | Semantic or accessibility tree, roles, names, values, text, hierarchy               | Deterministic                                                                  |
| C2 — I/O            | Requests, responses, stdin/stdout, IPC, events, or telemetry at the system boundary | Deterministic                                                                  |
| C3 — Diagnostics    | Console, stderr, logs, uncaught errors, and exit status                             | Deterministic                                                                  |
| C4 — Rendered state | Screenshot, rendered text, or serialized visible state with volatile regions masked | Semi-deterministic; deterministic comparison when pinned to a committed golden |
| C5 — Vision         | Model interpretation of the same C4 capture                                         | Corroborating only                                                             |

## Multi-channel parity rule

For every interactive or visual reconstruction claim:

1. Capture the initiating input or action and the resulting observable state.
2. Require agreement from at least two **non-vision** channels.
3. Require at least one deterministic channel: C1, C2, C3, or a pinned C4 golden comparison.
4. Attribute every pass or mismatch to the channels and artifacts that support it.

A screenshot plus vision analysis is still one evidence channel and cannot pass parity. C5 may explain or corroborate a C1–C4 result, but it does not satisfy the two-channel minimum and cannot override deterministic evidence.

## Driver profiles

A driver profile maps the channels to surface tooling without changing the parity rule.

| Channel | Web/Playwright — shipped              | TUI/terminal               | Mobile              | Desktop              | Device                    |
| ------- | ------------------------------------- | -------------------------- | ------------------- | -------------------- | ------------------------- |
| C1      | ARIA snapshot or accessibility tree   | terminal buffer            | accessibility tree  | OS accessibility API | state/config dump         |
| C2      | routing, HAR replay, response capture | stdin/stdout and exit code | proxied API traffic | IPC or API calls     | telemetry or bus messages |
| C3      | console and page errors               | stderr and logs            | device logs         | app logs             | error logs                |
| C4      | masked screenshot golden              | rendered text snapshot     | screenshot          | window screenshot    | image or sensor snapshot  |
| C5      | optional vision review of C4          | optional                   | optional            | optional             | optional                  |

Only Web/Playwright is implemented by this skill. For another surface, use equivalent tooling and retain the same authorization, channel, parity, evidence, and handoff rules.

## Workflow

### 1. Scope and pin the run

Record the authorized reference, flows, expected inputs and outputs, viewport or terminal size, locale, timezone, clock, platform, runtime versions, and any normalization or masks. Use dedicated test accounts and synthetic data.

### 2. Isolate execution

Start each scenario from fresh state. For Web/Playwright, use a fresh browser context, keep authentication state gitignored, and block or replay unrelated third-party traffic. Never persist credentials, tokens, or personal data in traces, HARs, screenshots, logs, or browser state.

### 3. Exercise real boundaries

Drive the reference through user-visible or documented interfaces. In Playwright, use locator, mouse, and keyboard APIs rather than dispatching synthetic DOM events. Capture the input, transition, output, and errors needed to state the behavior precisely.

### 4. Capture the strongest practical channels

For the shipped Web profile:

- C1: capture an ARIA or accessibility snapshot and stable semantic assertions.
- C2: capture or replay relevant requests and responses; redact secrets before storage.
- C3: record console messages and page errors, and classify expected diagnostics.
- C4: compare a masked screenshot against a platform-specific golden under a pinned environment.
- C5: if useful, review the C4 artifact for qualitative corroboration and label the result `model-inferred`.

Prefer stable semantic and boundary assertions over pixel checks. Do not hide a deterministic mismatch with retries, broad screenshot tolerances, normalization, or vision commentary.

### 5. Evaluate each claim

State claims narrowly enough that supporting channels can agree or disagree. Record the observed value, environment, channel artifacts, normalization, and outcome. A parity pass must be reproducible from the saved evidence.

### 6. Redact and retain evidence

Treat traces and captures as sensitive. Store only what the claim needs, redact before sharing, and use trusted artifact storage. A Playwright trace is evidence; it is not the run's provenance record.

## Run handoff

Before leaving observation:

1. Save a concise `reference-<name>.md` under the run directory. Include authorization and scope references, environment pins, scenarios, claims, channel outcomes, artifact paths and hashes, redactions, and unresolved mismatches. Keep raw captures as linked run evidence rather than embedding them in the note.
2. Append one schema-valid line per observed fact to the run's `evidence.jsonl` using `phase: observe`. Follow `schemas/evidence.schema.json`; keep claim IDs, channels, artifact paths, hashes, and authorization references inside `details`.
3. Map each accepted claim into a property in `behavioral-contract.yaml`, with the observation artifacts cited in the property's `evidence` and an oracle appropriate to how the claim will be checked.
4. Use `oracle.kind: authorized-reference` only when both authorization evidence and an executable comparison are recorded in the property, using `oracle.authorization` and `oracle.command`. Record the compared artifact when applicable.
5. Otherwise use the reference only as design evidence and set the property oracle to `contract-spec`; do not imply that the reference is an executable parity oracle. Existing target behavior remains the preservation oracle when a target baseline exists.

Example evidence entry:

```json
{"timestamp":"2025-01-01T00:00:00Z","phase":"observe","action":"capture_reference_behavior","result":"pass","details":{"property_id":"P001","reference":"reference-dashboard.md","claim":"Submitting valid input shows the result state","channels":["C1","C2"],"artifacts":["captures/dashboard.aria.yml","captures/dashboard.har"],"authorization":"migration-request.json"},"redacted":true}
```

Use the canonical run `provenance.json`, governed by `schemas/provenance.schema.json`, for source, license, and build provenance. Use `evidence.jsonl` and the reference observation for capture-specific facts. Do not create a separate or look-alike provenance record for screenshots, traces, HARs, or snapshots.

## Completion check

Observation is complete only when:

- authorization and scope are recorded;
- each accepted interactive or visual claim satisfies the multi-channel parity rule;
- vision findings are labeled corroborating only;
- sensitive data is removed or access-controlled;
- the concise reference observation and `phase: observe` evidence entries are saved under the run;
- claims are mapped into behavioral-contract properties with valid oracle treatment; and
- the run artifacts pass the repository's run validation when the surrounding workflow provides a complete run.
