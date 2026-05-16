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
| [`minimal`](minimal.yaml) | Minimal (headless / VM baseline) | draft | generic x86-64-v3 · 2c/4t · 4 GB RAM · no GPU · virtio-blk root · ext4 | cyberpunk042 | role-headless, whitelabel-default |
| [`developer`](developer.yaml) | Developer Workstation | draft | generic x86-64-v3 · 4c/8t · 16 GB RAM · optional GPU · nvme-pcie-4 single · ext4 | cyberpunk042 | role-developer, whitelabel-default, observability-tier-1 |
| [`headless`](headless.yaml) | Headless Server | draft | server-class x86-64-v3 · 8c/16t · 32 GB ECC · nvme rootfs + dual sata-ssd raid1 data · auditd+fail2ban+chrony+unattended-upgrades | cyberpunk042 | role-server, whitelabel-default, observability-tier-1 |

## Reserved slots (substantive body deferred per Q-012)

All Q-012 reserved slots have been promoted out (closure 3/3):
  - `minimal` (Q-012 slot 1/3 — VM/headless baseline)
  - `developer` (Q-012 slot 2/3 — polyglot dev toolchain)
  - `headless` (Q-012 slot 3/3 — bare-metal server)

## Mixins (cross-cutting fragments)

| name | purpose |
|---|---|
| [`mixins/role-workstation.yaml`](mixins/role-workstation.yaml) | Shared workstation-role package set (zfsutils, nvidia, podman, etc.) — composed into sain-01 + old-workstation |
| [`mixins/role-headless.yaml`](mixins/role-headless.yaml) | Headless / VM-class role: minimal base, no GUI bits, no first-login-assistant, more aggressive deny-list — composed into minimal |
| [`mixins/role-developer.yaml`](mixins/role-developer.yaml) | Developer-workstation role: gcc/clang/rust/go/python/node toolchains, debuggers, containers, multiple editors — composed into developer |
| [`mixins/role-server.yaml`](mixins/role-server.yaml) | Bare-metal headless-server role: auditd + fail2ban + chrony + unattended-upgrades + hardened SSH — composed into headless |
| [`mixins/whitelabel-default.yaml`](mixins/whitelabel-default.yaml) | Default whitelabel binding (placeholder until Q-003 brand identity resolves) |
| [`mixins/observability-tier-1.yaml`](mixins/observability-tier-1.yaml) | Tier-1 observability config (prometheus-local + structured logs) |

## Schema-conformance status

Profile bodies above are **draft** (`identity.status: draft`). Schema-
conformance against `schemas/profile.schema.yaml` is verified by:

1. `tools/validate-profile <profile.yaml>` (lands at PR 10 TDD harness)
2. CI `schema/` test layer (lands at PR 10)

Until the validator ships, conformance is best-effort author-checked
against the schema file.
