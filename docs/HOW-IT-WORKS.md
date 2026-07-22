# How mew-skills works (visual)

Diagrams over prose. Every diagram here mirrors a rule already written in the
`skills/*/SKILL.md` files — this doc does not add new behavior, it makes the
existing behavior scannable. GitHub renders the Mermaid blocks natively; no
extra tooling needed.

## 1. The whole run, end to end

```mermaid
flowchart LR
    A[User request] --> B[mew-migration<br/>intake + lock]
    B --> C[repo-cartographer<br/>INGEST]
    C --> D[behavior-contract<br/>OBSERVE]
    D --> E[GRILL<br/>resolve ambiguity]
    E --> F[behavioral-contract.yaml<br/>CONTRACT]
    F --> G[migration-planner<br/>MIGRATION PLAN]
    G --> H{HUMAN<br/>APPROVAL}
    H -- revise --> F
    H -- abort --> Z[Stop, report evidence]
    H -- approve --> I[differential-migration<br/>IMPLEMENT + VERIFY]
    I --> J[parity-report.json]
    J --> K[HANDOFF]
    K --> L[RETRO]
    L --> M[proposed-skill-changes.md]

    style H fill:#ffd966,stroke:#333,stroke-width:2px
    style Z fill:#f4a3a3,stroke:#333
```

One orchestrator (`mew-migration`), five phase skills, one hard stop for human
approval before anything gets written to production code.

## 2. Who owns what

```mermaid
flowchart TD
    ORC["mew-migration<br/>(orchestrator)"]
    ORC -->|loads| RC[repo-cartographer]
    ORC -->|loads| BC[behavior-contract]
    ORC -->|loads| MP[migration-planner]
    ORC -->|loads if oracle exists| DM[differential-migration]
    ORC -->|loads for black-box refs| OB[observation]

    RC -->|writes| A1[repo-inventory.yaml]
    BC -->|writes| A2[behavioral-contract.yaml]
    MP -->|writes| A3[migration-plan.yaml]
    DM -->|writes| A4[parity-report.json]
    OB -->|writes| A5["reference-*.md<br/>+ evidence"]

    A5 -.->|feeds properties into| A2
    A1 -->|feeds scope into| A2
    A2 -->|feeds contract into| A3
    A3 -->|feeds units into| A4
```

Every phase skill writes exactly one canonical artifact and appends to the
shared `evidence.jsonl`. Nobody overwrites another skill's artifact.

## 3. The verification route decision (oracle presence)

This is the logic buried in `mew-migration`'s "Verification route" section —
the thing that decides whether `differential-migration` gets loaded at all.

```mermaid
flowchart TD
    P[Every contract property] --> Q{oracle.kind?}
    Q -->|executable-baseline or<br/>authorized-reference| EXE[Differential-eligible]
    Q -->|contract-spec /<br/>characterization /<br/>regression| CHK[Checked, not diffed]
    Q -->|unresolved + unknown| BLOCK[Blocks approval<br/>unless deferred]

    EXE --> ROUTE
    CHK --> ROUTE
    ROUTE{Route for the run}
    ROUTE -->|no property is<br/>differential-eligible| CO["contract-only<br/>(skip differential-migration)"]
    ROUTE -->|some exec, some not| MX["mixed<br/>(diff the exec ones only)"]
    ROUTE -->|all exec| DF["differential<br/>(diff everything)"]
```

A greenfield feature adoption with no old implementation to compare against
almost always lands on `contract-only` — most requests never need
`differential-migration` loaded at all.

## 4. What a run looks like on disk

```
<target>/.mew/runs/<run-id>/
├── migration-request.json      ← intake, validated against migration-request.schema.json
├── manifest.json                ← run identity, source commit lock
├── repro.json                   ← pinned build/test/bench environment
├── provenance.json              ← license + SBOM-style tracking
├── repo-inventory.yaml          ← from repo-cartographer
├── reference-<name>.md          ← from observation / reference-inspection (one per reference)
├── behavioral-contract.yaml     ← from behavior-contract  (approved_by + approved_at gate)
├── migration-plan.yaml          ← from migration-planner
├── parity-report.json           ← from differential-migration (skipped if contract-only)
├── run-state.json               ← durable W### work-item ledger, survives compaction
├── evidence.jsonl                ← one JSON line per observed fact, append-only
└── proposed-skill-changes.md    ← written at RETRO, never auto-merged
```

Every file above has a matching file in `schemas/`. `scripts/validate_run.py`
fails the run if any artifact drifts from its schema — this is a deterministic
gate, not a vibe check.

## 5. The approval gate, concretely

```mermaid
sequenceDiagram
    participant U as User
    participant M as mew-migration
    participant V as analyze_run.py

    M->>M: draft behavioral-contract.yaml
    M->>M: draft migration-plan.yaml
    M->>V: run cross-artifact + schema checks
    V-->>M: pass/fail
    M->>U: "Approve Mew behavior before implementation?"
    Note over U,M: preserve / introduce / intentional changes /<br/>verification route / oracle mapping /<br/>files+deps / unknowns
    U-->>M: approve | revise: <change> | abort
    alt approve
        M->>M: write approved_by + approved_at
        M->>M: unlock implementation
    else revise
        M->>M: back to contract draft
    else abort
        M->>M: stop, no code written
    end
```

Nothing under step 8 (Implement and verify) in `mew-migration/SKILL.md` runs
before this exchange happens.

## 6. Observation's 5-channel model (today: Web/Playwright only)

```mermaid
flowchart LR
    subgraph Deterministic
        C1[C1 Structure<br/>ARIA tree, roles]
        C2[C2 I/O<br/>requests/responses]
        C3[C3 Diagnostics<br/>console, errors]
    end
    subgraph "Semi-deterministic"
        C4[C4 Rendered state<br/>masked screenshot golden]
    end
    subgraph Corroborating
        C5[C5 Vision<br/>model reads the C4 image]
    end

    C1 & C2 & C3 & C4 --> RULE{"parity claim needs:<br/>≥2 non-vision channels AND<br/>≥1 deterministic channel"}
    C5 -.->|never sufficient alone| RULE
    RULE -->|pass| CLAIM[Accepted behavioral<br/>contract property]
```

A screenshot plus a vision model looking at it is **one** channel, not two —
it can never pass parity by itself. This is the rule that stops "the AI looked
at a screenshot and said it matches" from counting as evidence.

## 7. The self-healing loop

```mermaid
flowchart LR
    RUN[Real run] --> FAIL{Failure or<br/>wasted loop?}
    FAIL -->|yes| RETRO[RETRO: ask user<br/>what escaped the gates]
    RETRO --> PROP[proposed-skill-changes.md<br/>tier: universal / stack:x / repo:x<br/>oracle: hard / soft]
    PROP --> HUMAN{Maintainer review}
    HUMAN -->|reject/defer| DONE1[stays run-local]
    HUMAN -->|accept, repo tier| REPO[projects/&lt;id&gt;/skill-adopted/<br/>gitignored, project-only]
    HUMAN -->|accept, universal| HOLD{Holdout eval<br/>regresses?}
    HOLD -->|yes| DONE1
    HOLD -->|no| PACK[Merged into skills/*.md<br/>+ fixture + validate.sh]
```

A run can *propose* a change to the shared pack. It can never merge one. Only
a human, after a holdout check, promotes anything to `universal`.

## Today vs. tomorrow

**Today**, `observation`'s only shipped driver is Web/Playwright, and it's
still fairly manual: someone (agent or human) has to drive the browser through
locators, capture the 5 channels, and write `reference-<name>.md` by hand per
scenario. It works, but it's scripted observation, not autonomous exploration.

**Once [`tripplen23/mew`](https://github.com/tripplen23/mew) matures** — a
proper computer-use runtime instead of a scripted Playwright driver — the plan
is for `observation` to plug into it as a second driver profile alongside
Web/Playwright (see the driver-profile table in `skills/observation/SKILL.md`):
the same authorization gate, the same 5-channel model, the same
multi-channel-parity rule, but the exploration itself (finding flows, trying
inputs, noticing edge states) becomes agentic instead of pre-scripted. That
turns `reconstruction` from "the agent replays scenarios a human enumerated"
into "the agent explores an authorized reference and proposes its own
scenario coverage, still gated by the same C1–C5 evidence rule before
anything becomes a contract property." The contract, approval gate, and
parity rules in this doc do not change — only how C1–C4 evidence gets
captured does.
