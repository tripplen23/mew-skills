# Research Base

Primary sources that informed the mew-skills design. Each source was inspected directly (not from memory) during 2026-07-17 research sessions.

## Agent Skills Specification

**Source**: [agentskills.io/specification](https://agentskills.io/specification)

Key takeaways applied to mew-skills:
- **SKILL.md format**: YAML frontmatter (name, description required; license, compatibility, metadata, allowed-tools optional) + Markdown body. `name` max 64 chars, kebab-case, must match parent directory. `description` max 1024 chars.
- **Progressive disclosure**: metadata (~50-100 tokens) -> body (<5000 tokens) -> linked files (on-demand). SKILL.md under 500 lines.
- **Directory structure**: `scripts/` (executable), `references/` (documentation), `assets/` (templates)
- **Security**: XML angle brackets `< >` forbidden in frontmatter (system-prompt injection risk). No `README.md` inside skill folders.
- **Validation**: `agentskills validate ./my-skill` checks frontmatter and naming conventions

## Agent Skills Best Practices

**Source**: [agentskills.io/skill-creation/best-practices](https://agentskills.io/skill-creation/best-practices)

Key patterns applied:
- **Start from real expertise**: Extract from hands-on tasks, not generic LLM knowledge
- **Refine with real execution**: Execute -> revise -> re-execute. Read agent traces, not just outputs
- **Add what the agent lacks, omit what it knows**: Don't explain what HTTP is; do explain project-specific conventions
- **Provide defaults, not menus**: Pick a default approach, mention alternatives briefly
- **Favor procedures over declarations**: Teach how to approach a class of problems
- **Gotchas sections**: Highest-value content — concrete corrections to mistakes agents will make
- **Plan-validate-execute**: For destructive operations, create intermediate plan -> validate -> execute
- **Validation loops**: Do work -> run validator -> fix -> repeat until pass

## Matt Pocock: Skills for Real Engineers

**Source**: [github.com/mattpocock/skills](https://github.com/mattpocock/skills)
(inspected 2026-07-18)

Key patterns adopted selectively:

- **Small, composable disciplines**: orchestration and reusable engineering
  discipline are separate, so a migration workflow can invoke focused research,
  TDD, diagnosis, or review behavior without duplicating it.
- **Grill before commitment**: resolve the user's decision tree before writing a
  spec. Mew bounds this to questions that target evidence cannot answer, rather
  than interviewing settled details.
- **Feedback loops are the speed limit**: static checks, formatter, linter,
  executable tests, and red-green-refactor provide hard oracles. A green unit
  suite alone is not a handoff.
- **Shared domain language**: repository-specific terminology belongs in
  `CONTEXT.md` or ADRs, not universal skill instructions.
- **Two-axis review**: standards/architecture review and contract/spec review are
  distinct checks; passing one does not imply the other.

Mew does not copy the repository's issue-tracker workflow or vendor-specific
invocation model. The portable lesson is to keep skills adaptable and to harden
them through real engineering feedback rather than adding one monolithic process.

## Anthropic Skills Guide (PDF)

**Source**: [resources.anthropic.com](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf) (33 pages, Jan 2026)

Key patterns applied:
- **Sequential workflow orchestration**: Explicit step ordering, dependencies, validation at each stage, rollback instructions
- **Iterative refinement**: Initial draft -> quality check -> refinement loop -> finalization
- **Context-aware tool selection**: Decision tree with fallback options and transparency
- **Domain-specific intelligence**: Compliance before action, comprehensive documentation
- **Testing**: Triggering tests (load on right prompts), functional tests (correct outputs), performance comparison (baseline vs with-skill)
- **Iteration**: Undertriggering -> add detail to description; Overtriggering -> add negative triggers; Execution issues -> improve instructions
- **PDF p.26**: "Code is deterministic; language interpretation isn't" — put validations in scripts, not prose

## Anthropic Tool Design Guide

**Source**: [anthropic.com/engineering/writing-tools-for-agents](https://www.anthropic.com/engineering/writing-tools-for-agents) (Sep 2025)

Key principles applied:
- **Tools = contract between deterministic and non-deterministic**: Design for agents, not for other developers
- **Consolidate, don't wrap**: Build thoughtful tools targeting high-impact workflows, not 1:1 API wrappers
- **Return meaningful context**: High-signal fields (name, not uuid), natural language identifiers
- **Token efficiency**: Pagination, filtering, truncation with sensible defaults
- **Prompt-engineer descriptions**: Unambiguous parameter names, clear inputs/outputs, strict data models
- **Evaluation-driven**: Generate test tasks from real-world uses, track tool calls and errors
- **Error design**: Actionable messages (what failed + expected + fix example), never raw tracebacks

## Bun's AI Rust Rewrite: Verification Playbook

**Source**: [nxcode.io](https://www.nxcode.io/resources/news/bun-rust-ai-migration-verification-playbook-2026) (2026-07-12)

This is the most directly applicable source. Key concepts adopted:

### Four-plane architecture
- **Contract plane**: Public behavior, compatibility promises, intentional changes, performance budgets. Human-maintained, versioned.
- **Execution plane**: Isolated implementation agents. One writer per unit, narrow tools, cannot change contract.
- **Verification plane**: Independent. Compiles, runs tests, performs differential checks, fuzzes, benchmarks. Deterministic CI decides gates.
- **Release plane**: Controls integration and production exposure. Merges in dependency order, canary, rollback.

### Key definitions
- **Port**: Reimplementation preserving a defined set of behaviors
- **Behavioral contract**: Explicit property list (inputs, outputs, errors, ordering, side effects, concurrency, resource limits, platform support, performance)
- **Test oracle**: Decides whether output is correct (assertion, reference impl, spec, golden file, human rubric)
- **Differential test**: Feed equivalent inputs to old and new, compare observable results
- **Metamorphic test**: Check relationships between multiple executions (serialize->parse preserves, idempotent twice = once)
- **Unsafe surface**: Code where language guarantees are weakened (Rust unsafe, FFI)
- **Escaped defect**: Migration-caused bug found after the gate that should have caught it

### Six phases adopted into mew-skills
1. **Define contract + stop conditions**: Inventory, label preserve/change/deprecate/unknown, define hard stops
2. **Build semantic map**: Map risky patterns before generating at scale. Version the map.
3. **Run deliberately difficult pilot**: 3 shapes (simple, dependency-heavy, semantic hotspot). Introduce faults on purpose.
4. **Fan out with isolation**: Separate worktrees, one writer per unit, atomic commits, restrict destructive commands
5. **Compiler errors + tests as queues**: Group errors, ban stubs, widen test circles, separate test authorship
6. **Differential testing + fuzzing + performance**: Old vs new on same corpus, fuzz parsers, benchmark distributions, soak tests

### Earned autonomy principle
"Make the agent prove behavior slice by slice, then earn broader autonomy through measured results." Capability, evidence, and authority remain separate.

## Academic Sources — Behavior-Preserving Migration

### Characterization Tests / Golden Master
- **Feathers, M. C.** *Working Effectively with Legacy Code.* Prentice Hall PTR, 2004. Ch. 13. — Defines characterization tests as capturing actual behavior (including bugs) as a protective net before refactoring. The "legacy code dilemma": you need tests to change code safely, but need to change code to add tests.

### Differential Testing
- **McKeeman, W. M.** "Differential Testing for Software." *Digital Technical Journal* 10(1):100-107, 1998. — Defines differential testing as feeding mechanically generated test cases to two or more comparable systems; if results differ, the tester has a candidate bug. Notes the technique is "important for applications for which there is a high premium on independently duplicating the behavior of some existing application ... when old software is being retired in favor of a new implementation." Identifies four issues: test case quality, false positives, noise reduction, cross-platform comparison.

### Metamorphic Testing
- **Chen, T. Y. et al.** "Metamorphic Testing: A Review of Challenges and Opportunities." *ACM Computing Surveys* 51(1), Art. 4, Jan 2018. DOI 10.1145/3143561. — MT addresses both the oracle problem and the reliable-test-set problem. A metamorphic relation (MR) is a necessary property relating multiple inputs and their expected outputs. Source test cases are transformed into follow-up test cases; MT verifies outputs together against the MR.
- **Segura, S. et al.** "A Survey on Metamorphic Testing." *IEEE TSE* 42(9):805-824, 2016. DOI 10.1109/TSE.2016.2532875. — Surveyed 119 papers; an MR = an input transformation + an output relation. Example: `sin(x) = sin(pi - x)` lets you test without knowing the exact value.
- **Weyuker, E. J.** "On Testing Non-Testable Programs." *The Computer Journal* 25(4):465-470, 1982. — Defines the oracle problem: a program is non-testable if an oracle does not exist or requires extraordinary effort.

### Reproducible Builds
- **reproducible-builds.org** — `SOURCE_DATE_EPOCH` spec; a build is reproducible when "building the same source code with the same set of tools ... the output is always exactly the same."
- **pip docs** — `--require-hashes` for tamper checks; repeatable installs via version pinning + hash recording.
- **Python docs** — `PYTHONHASHSEED=0` disables hash randomization (enabled by default since Python 3.3).

### Strangler Fig / Incremental Migration
- **Fowler, M.** "Strangler Fig" (martinfowler.com, 2004, rev. 2024). — Gradual modernization: new functionality built on top of yet separate to legacy; behavior moved piece by piece. "Wholesale replacements go down in flames most of the time." Names four activities: understand outcomes, break into parts, deliver parts, sustain organizationally.
- **Fowler, M.** "Branch By Abstraction" — Introduce abstraction layer over component to be replaced, reroute callers, swap implementations behind it.
- **Fowler, M.** "Parallel Change" (expand -> migrate -> contract) — Lowers risk by allowing incremental client migration.
- **AWS Prescriptive Guidance** / **Microsoft Azure Architecture Center** — Strangler fig pattern for monolith-to-microservices.

### Python-to-Rust Seam
- **PyO3** (pyo3.rs) — Rust bindings for Python; `PyModule::import` gets a handle to any Python module.
- **maturin** (maturin.rs) — Builds and publishes crates with PyO3 bindings as Python packages; supports "mixed" layout (Python package + Rust module).

### Contract Testing
- **Pact** (docs.pact.io) — Consumer-driven contract testing; Pact Broker `can-i-deploy` checks for CI/CD.
- **OpenAPI Specification v3.1.1** (spec.openapis.org) — Standard, language-agnostic interface description for HTTP APIs.

### Numerical Tolerance
- **PEP 485** — `math.isclose(a, b, *, rel_tol=1e-09, abs_tol=0.0)`: `abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)`.
- **Rust `approx` crate** (docs.rs/approx) — Approximate float equality via relative difference or ULPs (units in the last place).
- **Python `json`** — `allow_nan=False` raises `ValueError` for strict JSON compliance; Rust's `serde_json` rejects non-finite floats by default (common cross-language divergence).

### Performance Benchmarking
- **pyperf** (pyperf.readthedocs.io) — Python benchmark toolkit; detects multimodal distributions.
- **Criterion.rs** (bheisler.github.io/criterion.rs) — Statistics-driven Rust micro-benchmarking; regression detection.
- **Google benchmark** — CPU scaling warnings; disable frequency scaling for stable measurements.

### Provenance & Licensing
- **SPDX 3.0.1** (spdx.github.io) — ISO/IEC-recognized standard for SBOMs.
- **REUSE 3.2** (reuse.software) — SPDX identifiers in file headers + `LICENSES/` + `REUSE.toml`.
- **SLSA v1.1** (slsa.dev) — Supply-chain levels for artifact provenance; L1 = basic provenance, L2 = signed by hosted build service, L3 = strong isolation.
- **No license = no permission** (choosealicense.com, GitHub Docs, OSD) — A source-available repo without an OSI-approved license is not open source and may not be legally modifiable or redistributable.

## Browser/Computer-Use Observation

### Playwright
- **Best Practices** (playwright.dev/docs/best-practices) — Test user-visible behavior; isolate tests; avoid testing third-party deps; use locators + web-first assertions.
- **Trace Viewer** (playwright.dev/docs/trace-viewer) — `trace.playwright.dev` loads traces entirely in-browser, no external transmission. Per-action DOM snapshots, network, console, screenshots.
- **Visual comparisons** (playwright.dev/docs/test-snapshots) — `toHaveScreenshot` with `maxDiffPixels`, `stylePath` for masking; rendering varies by OS/version/hardware/power/headless.
- **Aria snapshots** (playwright.dev/docs/aria-snapshots) — `toMatchAriaSnapshot`; YAML accessibility-tree snapshot; roles/attributes/values/text.
- **Input** (playwright.dev/docs/input) — `dispatchEvent` is the programmatic, non-user path; real handlers need `page.mouse/keyboard/locator` pipeline.
- **CI** (playwright.dev/docs/ci-intro) — Artifacts (trace, HTML report, console logs) can contain credentials — encrypt before sharing, trusted stores only.
- **Auth** (playwright.dev/docs/auth) — `storageState` in gitignored `playwright/.auth/`; browser-state file may contain sensitive cookies/headers.
- **Accessibility** (playwright.dev/docs/accessibility-testing) — "Automated testing cannot detect all types of WCAG violations"; manual review required.

### Vision Limitations
- **OpenAI vision docs** (platform.openai.com/docs/guides/vision) — Model ignores metadata/filenames, resizes before analysis, approximate counts, misinterprets rotated text, struggles with line styles in graphs and precise spatial localization. Not suitable for medical images.

### Provenance Standards
- **W3C PROV-O** (w3.org/TR/prov-o) — Provenance data model: Entity, Activity, Agent; `wasGeneratedBy`, `wasAttributedTo`, `used`.
- **NIST AI 600-1** (nvlpubs.nist.gov) — Content provenance is a named GenAI risk category; verify generated content.

## behavior-preservation-checker skill

**Source**: [skillproof.dev](https://skillproof.dev/discover/behavior-preservation-checker) (GitHub: ArabelaTso/Skills-4-SE)

An existing Claude skill for comparing runtime behavior between original and migrated repositories. Confirms that the problem space is recognized and that the Agent Skills format is appropriate for this domain. The mew-skills approach is more structured: it separates cartography, contract, planning, verification, and browser observation into distinct skills rather than combining them into one.
