# Licensing and Provenance Policy

## Rule

Every dependency in the migration must have a recorded license. License-incompatible dependencies must be identified before implementation begins.

## Procedure

1. **During ingestion**: repo-cartographer records each dependency's license in the inventory.
2. **During planning**: migration-planner verifies target-language equivalents have compatible licenses.
3. **During implementation**: Any new dependency added must have its license recorded before the unit is accepted.

## License compatibility matrix

| Source license | Target license | Compatible? |
|---------------|---------------|-------------|
| MIT | MIT/Apache-2.0 | ✅ |
| Apache-2.0 | MIT/Apache-2.0 | ✅ |
| GPL-3.0 | MIT | ❌ (copyleft) |
| GPL-3.0 | GPL-3.0 | ✅ |
| Proprietary | Any | Requires legal review |

## Provenance

- Record the source commit hash for every migrated unit
- Record the target commit hash after implementation
- Record the tool and model used for each unit
- Maintain a bill of materials (BOM) for the target implementation

## Gotchas

- **Transitive dependencies.** A dependency may pull in a GPL'd transitive. Check the full dependency tree, not just direct dependencies.
- **License changes.** A dependency may change its license between versions. Pin versions and verify licenses at the pinned version.
- **Dual-licensed packages.** Record which license is selected and why.
