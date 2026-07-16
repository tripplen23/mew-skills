# Research Base

Primary sources that informed the mew-skills design.

## Agent Skills Specification

**Source**: [agentskills.io/specification](https://agentskills.io/specification)

Key takeaways applied to mew-skills:
- **SKILL.md format**: YAML frontmatter (name, description required; license, compatibility, metadata, allowed-tools optional) + Markdown body
- **Progressive disclosure**: metadata (~100 tokens) → body (<5000 tokens) → linked files (on-demand). SKILL.md under 500 lines.
- **Directory structure**: `scripts/` (executable), `references/` (documentation), `assets/` (templates)
- **Validation**: `skills-ref validate ./my-skill` checks frontmatter and naming conventions

## Agent Skills Best Practices

**Source**: [agentskills.io/skill-creation/best-practices](https://agentskills.io/skill-creation/best-practices)

Key patterns applied:
- **Start from real expertise**: Extract from hands-on tasks, not generic LLM knowledge
- **Refine with real execution**: Execute → revise → re-execute. Read agent traces, not just outputs
- **Add what the agent lacks, omit what it knows**: Don't explain what HTTP is; do explain project-specific conventions
- **Provide defaults, not menus**: Pick a default approach, mention alternatives briefly
- **Favor procedures over declarations**: Teach how to approach a class of problems
- **Gotchas sections**: Highest-value content — concrete corrections to mistakes agents will make
- **Plan-validate-execute**: For destructive operations, create intermediate plan → validate → execute
- **Validation loops**: Do work → run validator → fix → repeat until pass

## Anthropic Skills Guide (PDF)

**Source**: [resources.anthropic.com](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf) (33 pages)

Key patterns applied:
- **Sequential workflow orchestration**: Explicit step ordering, dependencies, validation at each stage, rollback instructions
- **Iterative refinement**: Initial draft → quality check → refinement loop → finalization
- **Context-aware tool selection**: Decision tree with fallback options and transparency
- **Domain-specific intelligence**: Compliance before action, comprehensive documentation
- **Testing**: Triggering tests (load on right prompts), functional tests (correct outputs), performance comparison (baseline vs with-skill)
- **Iteration**: Undertriggering → add detail to description; Overtriggering → add negative triggers; Execution issues → improve instructions

## Anthropic Tool Design Guide

**Source**: [anthropic.com/engineering/writing-tools-for-agents](https://www.anthropic.com/engineering/writing-tools-for-agents)

Key principles applied:
- **Tools = contract between deterministic ↔ non-deterministic**: Design for agents, not for other developers
- **Consolidate, don't wrap**: Build thoughtful tools targeting high-impact workflows, not 1:1 API wrappers
- **Return meaningful context**: High-signal fields (name, not uuid), natural language identifiers
- **Token efficiency**: Pagination, filtering, truncation with sensible defaults
- **Prompt-engineer descriptions**: Unambiguous parameter names, clear inputs/outputs, strict data models
- **Evaluation-driven**: Generate test tasks from real-world uses, track tool calls and errors

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
- **Metamorphic test**: Check relationships between multiple executions (serialize→parse preserves, idempotent twice = once)
- **Unsafe surface**: Code where language guarantees are weakened (Rust unsafe, FFI)
- **Escaped defect**: Migration-caused bug found after the gate that should have caught it

### Six phases adopted into mew-skills
1. **Define contract + stop conditions**: Inventory, label preserve/change/deprecate/unknown, define hard stops
2. **Build semantic map**: Map risky patterns before generating at scale. Version the map.
3. **Run deliberately difficult pilot**: 3 shapes (simple, dependency-heavy, semantic hotspot). Introduce faults on purpose.
4. **Fan out with isolation**: Separate worktrees, one writer per unit, atomic commits, restrict destructive commands
5. **Compiler errors + tests as queues**: Group errors, ban stubs, widen test circles, separate test authorship
6. **Differential testing + fuzzing + performance**: Old vs new on same corpus, fuzz parsers, benchmark distributions, soak tests

### YAML policy artifact
The migration-planner skill's `worker_policy` and `stop_conditions` sections are directly modeled on the NxCode YAML policy template.

### Earned autonomy principle
"Make the agent prove behavior slice by slice, then earn broader autonomy through measured results." Capability, evidence, and authority remain separate.

## behavior-preservation-checker skill

**Source**: [skillproof.dev](https://skillproof.dev/discover/behavior-preservation-checker) (GitHub: ArabelaTso/Skills-4-SE)

An existing Claude skill for comparing runtime behavior between original and migrated repositories. Confirms that the problem space is recognized and that the Agent Skills format is appropriate for this domain. The mew-skills approach is more structured: it separates cartography, contract, planning, and verification into distinct skills rather than combining them into one.

## Playwright Visual Testing

**Source**: [playwright.dev/docs](https://playwright.dev/docs/test-snapshots) (referenced via web search)

Relevant for the website-cloning migration journey (observing browser behavior → rebuilding). Playwright trace viewer, visual comparisons, and accessibility testing patterns inform the OBSERVE phase when the "source" is a running web application rather than source code.
