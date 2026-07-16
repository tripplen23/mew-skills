# SDK Selection Policy

## Rule

Always use official SDKs from the target language's ecosystem. Never hand-roll a client when an official one exists.

## Rationale

Hand-rolled implementations introduce subtle behavioral differences that differential testing may not catch — especially around retry logic, connection pooling, serialization edge cases, and error mapping. The Bun rewrite demonstrated that cross-language semantic mismatches are the primary source of escaped defects.

## Procedure

1. **Identify the dependency**: From the repo inventory, list all external dependencies.
2. **Find the target equivalent**: Search the target language's package registry for an official or well-maintained SDK.
3. **Verify compatibility**: Check that the target SDK supports the same API version, features, and behavior.
4. **Record the substitution**: Document the mapping in the semantic map.
5. **Human approval**: Any SDK substitution that changes behavior (different error codes, different serialization format) requires human approval as an intentional change in the behavioral contract.

## Examples

| Source (Python) | Target (Rust) | Notes |
|----------------|---------------|-------|
| `requests` | `reqwest` | Official HTTP client. Check redirect behavior. |
| `psycopg2` | `sqlx` with `postgres` | Check transaction isolation behavior. |
| `redis-py` | `redis-rs` | Check pub/sub message ordering. |

## Gotchas

- **Error mapping differs.** Python's `requests.exceptions.ConnectionError` maps to `reqwest::Error` but the specific variant may differ. This is a contract property.
- **Async vs sync.** If the source is synchronous and the target SDK is async-only, the behavioral contract must specify whether ordering changes are acceptable.
- **Version skew.** Pin the target SDK version. A minor version bump can change serialization behavior.
