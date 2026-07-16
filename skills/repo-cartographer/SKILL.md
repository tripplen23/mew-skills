---
name: repo-cartographer
description: "Inventories a source repository to prepare for a behavior-preserving migration. Maps public APIs, CLI commands, file formats, database effects, environment variables, telemetry, supported platforms, and performance characteristics. Locks the source commit and produces a run manifest. Use when starting a Mew migration run, when analyzing a codebase before rewriting, or when the user says \"map this repo\" or \"inventory this project for migration\"."
license: MIT
metadata:
  author: tripplen23
  version: "0.1.0"
  mew-phase: INGEST+REPRODUCE
---

# Repo Cartographer

## Purpose

Create a complete, machine-readable inventory of a source repository before any migration work begins. This inventory becomes the foundation for behavioral contract extraction and migration planning.

## Steps

### Step 1: Lock the source

```bash
cd <repo-path>
git rev-parse HEAD  # record exact commit
git status --porcelain  # verify clean working tree
```

If the tree is dirty, ask the user to commit or stash before proceeding. Record the commit hash in the run manifest.

### Step 2: Create run directory

```
.mew/runs/<run-id>/
├── manifest.json
├── source-lock.json
├── evidence.jsonl
├── repo-inventory.yaml
└── ...
```

Generate a run ID from timestamp + short hash: `YYYYMMDD-HHMMSS-<7chars>`.

### Step 3: Inventory the repository

Scan the repository and catalog every observable surface:

1. **Public APIs**: HTTP endpoints, RPC methods, GraphQL resolvers, WebSocket handlers. Record path, method, auth, request/response schemas.
2. **CLI commands**: subcommands, flags, exit codes, output formats.
3. **File formats**: config files, data files, export formats. Record schema or structure.
4. **Database effects**: tables, migrations, ORM models, stored procedures, triggers.
5. **Environment variables**: name, type, default, description, required/optional.
6. **Telemetry**: logs, metrics, traces, events. Record format and destination.
7. **Dependencies**: list all external packages with versions and licenses.
8. **Supported platforms**: OS, architecture, runtime versions.
9. **Performance characteristics**: any existing benchmarks, known perf budgets, latency expectations.
10. **Error surfaces**: error codes, error messages users depend on, exception hierarchies.

### Step 4: Record dependency graph

Map import/dependency relationships between modules. Identify:
- Leaf modules (no internal dependencies) — good pilot candidates
- Hub modules (many dependents) — high-risk migration targets
- Circular dependencies — integration risk

### Step 5: Produce artifacts

Write `repo-inventory.yaml` with all findings. Write `source-lock.json` with commit, tree status, and dependency versions. Write `manifest.json` with run identity.

Append each finding to `evidence.jsonl` as an evidence entry (see schemas/evidence.schema.json).

## Gotchas

- **Don't skip the dependency license column.** License incompatibility between source and target ecosystems can block the migration later.
- **Record error messages verbatim, not paraphrased.** Users and downstream systems may depend on exact error strings.
- **Environment variables are often undocumented.** Search `.env.example`, docker-compose files, CI configs, and shell scripts — not just source code.
- **Don't trust README alone.** The actual behavior may differ from documentation. Note discrepancies as evidence entries.
- **The inventory is a snapshot.** If the source repo changes after locking, the run is invalidated.

## Output format

`repo-inventory.yaml` structure:

```yaml
run_id: <run-id>
source_commit: <sha>
locked_at: <ISO timestamp>

public_apis:
  - path: /api/v1/users
    method: GET
    auth: bearer
    request_schema: { ... }
    response_schema: { ... }

cli_commands:
  - name: deploy
    flags: [--env, --force]
    exit_codes: { 0: success, 1: config_error }

database:
  tables: [users, orders, ...]
  migrations_dir: migrations/

environment:
  - name: DATABASE_URL
    type: string
    required: true

dependencies:
  - name: fastapi
    version: 0.104.1
    license: MIT

platforms: [linux-amd64, linux-arm64, darwin-arm64]

dependency_graph:
  leaves: [utils/, types/]
  hubs: [models/, api/]
  cycles: []
```
