# How to inspect a remote reference implementation

## Purpose

When the mew-migration orchestrator or behavior-contract skill instructs you to
**inspect a reference implementation**, it means:

- Code references are **design evidence**, not the preservation oracle.
- You must inspect official APIs, SDKs, or source artifacts rather than only
  running web searches.
- You must produce a structured observation before drafting the contract.

## Minimum per reference

For each reference implementation the user names, produce a short markdown
observation saved to the run root (for example
`.mew/runs/<run-id>/reference-<name>.md`). Include:

1. **Revision** — git SHA, release tag, or retrieval timestamp.
2. **License** — exact SPDX identifier or license file path.
3. **Architecture** — one paragraph describing how the reference organizes the
   capability the user wants.
4. **Configuration** — which files or env vars control the capability. Quote key
   defaults.
5. **Authentication** — how the reference identifies itself to external services.
   Pay attention to credential format, header shape, and token scope.
6. **Routing** — how the reference selects between multiple backends, providers,
   or services. Look for dispatch maps, registry patterns, build flags, or
   feature gates.
7. **Error mapping** — how the reference surfaces provider, auth, or
   protocol-level errors to its own caller or UI.
8. **Protocol facts** — reusable HTTP paths, request schemas, response shapes,
   or auth flows that the service itself defines. These are the portable facts
   the target must reproduce.
9. **Implementation choices** — decisions that are specific to the reference's
   language, framework, build system, or deployment model. These are design
   input, not behavioral requirements for the target.
10. **Blockers** — anything that would prevent reuse: unresolved license,
    missing auth path, unsupported official SDK, incompatible protocol, or
    documentation gap.

## Evidence rules

- Append to `evidence.jsonl` with a `reference_inspection` action.
- Cite exact files, function names, or docs URLs.
- Screenshots or raw HTTP exchanges are fine as supplementary observations but
  are not a substitute for inspecting the source or official docs.
- If a reference is only searched on the web and never inspected structurally,
  it is not an observation — record the gap as an unknown.

## When a reference is unreachable

If the reference repository is private, the user must provide the access path
(a local clone, a mirror, or documentation). Missing access is a blocker — do
not fabricate architecture from blog posts or issue comments.
