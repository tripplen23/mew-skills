# Provider adoption: preserve provider/model DNA

Use this reference when a migration adds or replaces AI model providers, gateways, SDKs, or model-selection UX.

## Core invariant

A provider is not just a base URL. It is a configured capability boundary:

- credential source;
- base URL and protocol shape;
- request/response compatibility;
- supported model catalog;
- enabled/disabled state;
- error and auth behavior;
- streaming/tool-call support;
- UI selection and filtering.

Do not flatten all models from every provider into one global model list unless the target already has that behavior and the contract explicitly preserves it.

## Required reference analysis

Before implementation, produce `reference-analysis.md` with one section per reference implementation. Each section must answer:

1. How does the reference represent providers?
2. How does it represent models under a provider?
3. How does it load credentials and base URLs?
4. How does it decide which models are available to the user?
5. What happens when a provider is not configured?
6. What request format does each provider use?
7. What error/auth behavior is surfaced to the user?
8. Which parts are reusable protocol facts, and which are implementation choices?

A web search result is not enough. The run must inspect source files, documentation, or API docs and cite exact evidence in `evidence.jsonl`.

## Target contract checklist

For Mew-style provider adoption, the behavioral contract must include properties for:

- Existing OpenCode Go behavior remains default when no native provider is configured.
- Provider selection is explicit or derived from configuration, not inferred by string-prefix accidents.
- Only models for configured/enabled providers are shown to users.
- Provider identity is visible enough for the user to distinguish identical model IDs across providers.
- Credentials are read from documented env vars or config fields and never written to artifacts.
- Base URLs have provider-specific defaults and overrides.
- A missing credential hides or blocks that provider; it does not expose unusable models.
- OpenAI-compatible endpoints are not treated as GitHub Copilot unless Copilot auth and routing are proven.
- Model list UI, API `/models`, and engine dispatch agree on the same provider/model catalog.
- Existing model IDs and aliases keep working unless an explicit migration path is approved.

## Anti-patterns caught by M0

- Adding `gpt-4o`, `gpt-4o-mini`, and Copilot variants directly into one global `ModelId::ALL` list without provider filtering.
- Treating GitHub Copilot as just another OpenAI-compatible base URL without evidence for auth, headers, and available models.
- Starting implementation after one or two web searches instead of producing `reference-analysis.md`, contract, and plan.
- Skipping the approval gate because the user's initial request sounded specific.
- Calling `cargo test` success a parity proof when provider/model UX behavior was never tested.

## Minimal tests

A provider-adoption implementation is not complete without tests or equivalent executable checks for:

1. No native provider configured → only existing OpenCode Go models are listed and default dispatch is unchanged.
2. OpenAI configured → OpenAI provider appears and only OpenAI models are listed under it.
3. Copilot configured → Copilot provider appears and only Copilot-supported models are listed under it.
4. Same model string in two providers remains disambiguated by provider identity.
5. Missing credential → provider is unavailable with an explicit reason, not silently listed.
6. Engine dispatch receives provider identity plus model identity, not only a flat model string.

## Approval gate wording

Before implementation, ask:

```text
Approve provider/model behavior before implementation?

- Provider catalog shape:
- Model filtering rule:
- Credential/env/config shape:
- Default compatibility behavior:
- UI/API behavior:
- Unknowns/blockers:

Reply approve / revise / abort.
```

Do not implement until this is approved.
