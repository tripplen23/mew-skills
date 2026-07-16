---
name: browser-observation
description: "Reconstructs and verifies authorized web applications using Playwright browser drivers with a five-channel evidence model. Captures DOM/accessibility snapshots, network HAR, console errors, pixel screenshots, and optional vision analysis. Enforces a hard parity rule: at least two channels must agree and at least one must be deterministic. Use when the migration source is a running web application rather than source code, when cloning a website, or when the user says \"observe this site\" or \"capture browser behavior\"."
license: MIT
metadata:
  author: tripplen23
  version: "0.1.0"
  mew-phase: OBSERVE+VERIFY
---

# Browser Observation

## Purpose

Capture defensible evidence from an authorized web application for behavioral reconstruction. This skill implements a five-channel evidence model where vision is never the sole parity oracle.

## The Five Evidence Channels

| Channel | What | Determinism | Playwright API |
|---------|------|-------------|----------------|
| C1 — DOM/a11y tree | Roles, names, values, text, hierarchy | Deterministic | `toMatchAriaSnapshot`, `page.accessibility.snapshot` |
| C2 — Network contract | Request/response URLs, methods, bodies; HAR replay | Deterministic | `page.route`, `routeFromHAR`, `waitForResponse` |
| C3 — Console & page errors | `console.*` messages and uncaught errors | Deterministic | `page.on('console')`, `page.on('pageerror')` |
| C4 — Pixel screenshot | PNG of viewport/element with masking | Semi-deterministic | `toHaveScreenshot` with `maxDiffPixels` + `mask` |
| C5 — Vision (multimodal) | Model describes screenshot | Model-inferred | Mew's `VisionAnalyzer` (optional) |

## The Parity Rule

> A claim "reconstructed screen X matches authorized screen X" requires **>=2 channels to agree**, and **>=1 must be deterministic** (C1/C2/C3, or C4 with committed golden). **C5 (vision) alone never suffices.**

Rationale: vision ignores metadata, resizes before analysis, gives approximate counts, misinterprets rotated text, and struggles with line styles in graphs and precise spatial localization (OpenAI vision docs). Vision output is stochastic across calls.

## Steps

### Step 1: Authorize and scope

Confirm the target app is **authorized** for reconstruction (user-owned, license-permitted, or explicitly approved). If not, stop.

Define the parity target: which screen(s)/flow(s), viewport(s), locale/timezone. Pin them.

### Step 2: Pin the environment

```ts
use: {
  viewport: { width: 1280, height: 720 },
  locale: 'en-US', timezoneId: 'UTC',
  colorScheme: 'light', reducedMotion: 'reduce',
  trace: 'on',
  screenshot: 'only-on-failure',
}
```

Rendering varies by OS, version, hardware, power source, and headless mode. Pin everything that affects pixels.

### Step 3: Isolate the context

Each run gets a **fresh browser context** (incognito-like, own storage/cookies).

- If auth is needed: load `storageState` from a **gitignored** `playwright/.auth/*.json`. Never commit browser state.
- Block third-party deps with `page.route(...abort())` or fulfill from HAR.

### Step 4: Drive with REAL input events

Use `locator.click/fill/press`, `page.mouse.*`, `page.keyboard.*`.

**Never** use `element.dispatchEvent(new PointerEvent(...))` from `page.evaluate` — React and other delegation frameworks will not fire their handlers. `dispatchEvent` is the programmatic path, not the user path.

### Step 5: Assert with web-first matchers

```ts
await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
await expect(page.getByTestId('row-count')).toHaveText('42');
await expect(page).toMatchAriaSnapshot({ path: 'dash.aria.yml' });
await expect(page).toHaveScreenshot('dash.png', {
  maxDiffPixels: 50, stylePath: 'screenshot.css',
  mask: [page.locator('.ad-slot'), page.locator('iframe')],
});
```

Prefer `expect(...).toBeVisible()` over `expect(await ...isVisible()).toBe(true)` — the latter does not wait and is flaky.

### Step 6: Capture deterministic channels (C1-C3)

- **C1 (DOM/a11y):** `page.accessibility.snapshot()` or `toMatchAriaSnapshot()` -> commit the `.aria.yml` as a golden.
- **C2 (network):** `page.route` to fulfill/modify, or `routeFromHAR(update:false)` to replay a committed HAR. Use `updateMode:'minimal'` for replay-only.
- **C3 (console/errors):** subscribe `page.on('console')` + `page.on('pageerror')`. Assert no unexpected errors.

### Step 7: Capture pixel channel (C4) with masking

- `toHaveScreenshot` generates the golden on first run; commit it. Subsequent runs diff via pixelmatch with `maxDiffPixels`.
- Mask volatile regions (ads, iframes, timestamps, avatars) with `mask: [...]` or hide via `stylePath` CSS.
- Keep baselines **per browser+platform** (`name-chromium-darwin.png`); never cross-diff.

### Step 8: (Optional) Capture vision channel (C5) — corroborating only

- Run `VisionAnalyzer` on the same screenshot C4 captured.
- Use vision for holistic/plausible questions only: "is the hero section visually balanced?", "does the empty state look intentional?"
- **Never** let vision be the sole basis for a parity PASS.
- Document vision limitations in the report: approximate counts, no metadata, resize-before-analysis, rotation/line-style/spatial weaknesses.

### Step 9: Bundle provenance (the trace)

The trace ZIP is the single provenance artifact: per-action DOM snapshots (C1), timeline screenshots (C4), network (C2), console+errors (C3), source, call log.

`trace.playwright.dev` loads it entirely in-browser, no external transmission — safe for local review.

For CI: upload traces/reports only to **trusted artifact stores**; encrypt before sharing. They can contain credentials, access tokens, or application source code.

### Step 10: Redact and store

- Never persist real credentials/tokens in traces, HARs, screenshots, or `storageState`.
- Use dedicated test accounts; per-worker accounts for shared-state tests.
- For HAR content: `recordHarContent: 'omit'` when you only need routing, or `'attach'` (separate files) so secrets can be scrubbed individually.
- Mask credential input fields in screenshots.

### Step 11: Report parity with channel attribution

For each reconstructed screen/flow, the report states:
- Which channels agreed (C1, C2, C3, C4 w/ diff=Npx, C5 corroborating).
- Which golden files were used (paths + hashes).
- Environment pin (browser, version, viewport, locale, TZ, OS).
- Any channel that disagreed and the resolution.
- Vision findings labeled "model-inferred, corroborating only".

## Determinism Ladder

| Rung | Oracle | When to use |
|------|--------|-------------|
| 6 | HAR replay (byte-exact) | Network-contract parity |
| 5 | Aria snapshot (structural) | DOM/a11y structure parity |
| 4 | `toHaveScreenshot` + golden + masking | Pixel parity |
| 3 | Web-first assertions (`toHaveText`, `toHaveCount`) | Element-state parity |
| 2 | `page.evaluate` bounding-box math | Layout/overlap parity |
| 1 | Vision description | Holistic plausibility only — always pair with rung >=3 |

A defensible Mew golden task lives at **rung >=3**, with vision allowed only as a corroborating signal at rung 1.

## Gotchas

- **Vision is approximate.** It ignores metadata, resizes before analysis, gives approximate counts, misinterprets rotated text, and struggles with line styles in graphs. Never use it as the sole oracle.
- **`dispatchEvent` is not a user gesture.** React synthetic handlers will not fire. Always use the real `page.mouse/keyboard/locator` pipeline.
- **Screenshot baselines are platform-specific.** Rendering varies by OS, version, hardware, power source, headless mode. Keep per-browser+platform baselines; never cross-diff.
- **Traces can contain credentials.** Treat them as sensitive. Encrypt before sharing. Upload only to trusted stores.
- **`storageState` contains cookies and headers.** Never commit it to git. Store in gitignored `playwright/.auth/`.
- **Automated a11y testing is necessary but not sufficient.** Axe-core catches structural issues, but many WCAG violations require manual review. Vision cannot certify WCAG conformance.
- **Pin time.** Use `clock.setFixedTime()` for any time-dependent UI (countdowns, "time ago" text, scheduled content).
- **Retries are for flake, not for parity.** A parity PASS must be stable across retries, not an artifact of a lucky re-run.

## Provenance Record

For each golden/screenshot/HAR/aria-snapshot, record:

```yaml
entity:          dash.aria.yml
generatedBy:     recon-run-<run-id>
attributedTo:    mew-driver@<version> + playwright@<version>
used:            authorized-app=<url> (commit <sha>)
env:             <browser> <version>, <os>, <viewport>, <locale>, <tz>, <colorScheme>
channels:        [C1]
hash:            sha256:...
siblingEvidence: dash.png (C4, diff=Npx), dash.har (C2)
vision:          none | corroborating (model=<name>, temp=0)
```

This maps to W3C PROV-O's Entity/Activity/Agent model and satisfies NIST AI 600-1's content-provenance expectation.
