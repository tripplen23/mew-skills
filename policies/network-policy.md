# Network Policy

## Rule

Migration agents operate in a sandboxed network environment. Network access is granted on a per-task basis, not by default.

## Default: No network

Agents start with no network access. All dependencies must be pre-fetched or vendored.

## When network is granted

- **Dependency resolution**: `cargo add`, `go get`, `pip install` — allowed during setup phase only, with human approval.
- **API testing**: Local test servers only. External API calls require explicit approval per endpoint.
- **Differential testing**: Old and new implementations run locally. No external services.

## Forbidden

- Calling production APIs during testing
- Downloading unverified dependencies (must use locked checksums)
- Sending telemetry or analytics during migration runs
- Accessing secrets stores without explicit per-task approval

## Rationale

Agents execute repository content, build scripts, and tool output. A compromised dependency or instruction hidden in source can influence the run. Network and filesystem isolation, scoped tokens, and immutable CI checks reduce this risk.

## Implementation

- Use ephemeral worktrees, containers, or VMs
- Short-lived credentials with scoped permissions
- Network allowlists per task type
- Audit log of all network calls in evidence.jsonl
