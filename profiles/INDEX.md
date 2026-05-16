# Profiles index

Catalog of declared OS profiles. Each profile MUST validate against
[`../schemas/profile.schema.yaml`](../schemas/profile.schema.yaml).
See [`../docs/sdd/004-profile-schema.md`](../docs/sdd/004-profile-schema.md)
for schema design and [`../docs/sdd/005-initial-profiles.md`](../docs/sdd/005-initial-profiles.md)
for the rationale of the seed set.

## Active profiles

| id | name | status | hardware target | maintainer | mixins |
|---|---|---|---|---|---|
| [`sain-01`](sain-01.yaml) | SAIN-01 AI Workstation | draft | Zen 5 + RTX Pro 6000 + RTX 3090 + dual NVMe ZFS + dual NIC | cyberpunk042 | role-workstation, whitelabel-default, observability-tier-1 |
| [`old-workstation`](old-workstation.yaml) | Old Workstation (constrained-hardware alternate) | draft | ~4 cores + ~11 GB DDR4 + 8 GB GPU + SATA SSD | cyberpunk042 | role-workstation, whitelabel-default, observability-tier-1 |

## Reserved slots (substantive body deferred per Q-012)

| id | reserved for | When body lands |
|---|---|---|
| `minimal` | minimal install (server-class; no DE; bare-essentials only) | When a concrete operator need surfaces (Q-012 deferred) |
| `developer` | developer workstation (with DE; full toolchain; debugging tooling) | Same |
| `headless` | headless install (no DE; remote-managed; useful for fleet member nodes) | Same |

Reserving these slots in the index is a Q-012 acknowledgment without
authoring placeholder bodies (which would suggest commitment).

## Mixins (cross-cutting fragments)

| name | purpose |
|---|---|
| [`mixins/role-workstation.yaml`](mixins/role-workstation.yaml) | Shared workstation-role package set (zfsutils, nvidia, podman, etc.) — composed into sain-01 + old-workstation |
| [`mixins/whitelabel-default.yaml`](mixins/whitelabel-default.yaml) | Default whitelabel binding (placeholder until Q-003 brand identity resolves) |
| [`mixins/observability-tier-1.yaml`](mixins/observability-tier-1.yaml) | Tier-1 observability config (prometheus-local + structured logs) |

## Schema-conformance status

Profile bodies above are **draft** (`identity.status: draft`). Schema-
conformance against `schemas/profile.schema.yaml` is verified by:

1. `tools/validate-profile <profile.yaml>` (lands at PR 10 TDD harness)
2. CI `schema/` test layer (lands at PR 10)

Until the validator ships, conformance is best-effort author-checked
against the schema file.
