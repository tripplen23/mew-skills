# Secret Handling Policy

## Rule

No secrets may appear in any migration artifact — evidence, contracts, reports, or commits.

## Procedure

1. **Before capture**: Identify all secrets in the source environment (env vars, config files, key files).
2. **During capture**: Replace secrets with redacted placeholders: `<REDACTED:env_name>`.
3. **In evidence**: Mark evidence entries with `redacted: true` when secrets were removed.
4. **In contracts**: Use schema placeholders, never real credentials.
5. **In differential testing**: Use synthetic or sanitized test data. Never replay real production requests containing PII or credentials.

## Forbidden

- Committing secrets to git
- Writing secrets to evidence.jsonl
- Passing real API keys to test scripts
- Logging secret values in any artifact

## Detection

Before writing any artifact, scan for:
- API keys (regex patterns)
- Database connection strings with credentials
- JWT tokens
- Private keys
- OAuth tokens

Use `scripts/redact_secrets.py` to automatically scan and redact artifacts before they are written.

## Incident response

If a secret is found in a migration artifact:
1. Stop the current run immediately
2. Rotate the compromised secret
3. Remove the secret from git history (`git filter-branch` or BFG)
4. Record the incident in evidence.jsonl with `result: warning`
