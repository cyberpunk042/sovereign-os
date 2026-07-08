# SDD-005 — Initial profile stubs (sain-01 + old-workstation; Stage Gate 3)

> Status: **review** (schema-conformant initial profiles; lock at Gate 3 alongside SDD-004 schema)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-05-16
> Closes findings: none
> Resolves at Gate 3: **Q-002** closure (single-parent + mixins hybrid model validated against real profiles)
> Derived from: SDD-004 profile schema; Plan-agent macro-arc § PR 6; SAIN-01 milestone (info-hub)

## Problem

SDD-004 defines the profile schema in the abstract. **Real instances
validate the schema against real targets** — this is the schema-first
discipline (Q-002 closure path: lock the schema only after at least
two profiles exercise it).

Plan-agent PR 6 ships:

1. `profiles/sain-01.yaml` — default profile, full hardware specified
   per the SAIN-01 milestone in info-hub. Kernel / packages / hooks
   blocks substantively filled in for the parts SDD-001..SDD-004 lock
   down; placeholders for the parts Stage 2+ defines (script bodies
   themselves).
2. `profiles/old-workstation.yaml` — alternate profile validating
   schema pluralism on a constrained-hardware target. Hardware
   specifics intentionally minimal until operator supplies the actual
   machine details.
3. `profiles/mixins/role-workstation.yaml` — cross-cutting workstation-
   role package set + hooks composed into both profiles.
4. `profiles/mixins/whitelabel-default.yaml` — placeholder whitelabel
   binding pending Q-003 (brand identity).
5. `profiles/mixins/observability-tier-1.yaml` — basic observability
   config.
6. `profiles/INDEX.md` — catalog of declared profiles + reserved-slot
   acknowledgment (`minimal` / `developer` / `headless` per Q-012).

## Why these two seed profiles (and not more)

### `sain-01` — default
- It's the operator's procured-hardware target per the SAIN-01
  milestone (info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md`).
- Hardware spec is **fully known** (E100 + L1 syntheses): 9900X +
  RTX Pro 6000 Blackwell 96 GB + RTX 4090 24 GB + 256 GB DDR5 + dual
  PCIe 5 NVMe + Marvell AQC113C 10 GbE + Intel I226-V 2.5 GbE on
  ASUS ProArt X870E-Creator.
- Exercises **every schema block**: identity / hardware (CPU
  topology with CCD partition; dual-GPU multi-role; ZFS-tiered
  storage with 3 datasets; dual-NIC VLAN split; motherboard PCIe
  constraints) / kernel (full Zen 5 KCFLAGS + VFIO + Tetragon config)
  / packages (base + profile + deny) / hooks (all 5 lifecycle phases) /
  lifecycle / whitelabel / observability.

### `old-workstation` — alternate
- Confirms the schema supports a profile structurally distinct from
  the SAIN-01 target.
- Validates that single-parent inheritance + mixins compose cleanly
  across hardware classes.
- The operator's overnight goal directive named this profile
  explicitly: "my 'old' workstation with only a 11GB + 8 GB card …
  Small Language Models (SLMs) and Recursive Language Models (RLMs)".
- Substantive hardware details (CPU model / GPU model / storage)
  intentionally minimal — operator supplies once the actual machine
  is targeted; the stub establishes schema-conformance and the role
  in the profile catalog.

### Why NOT seed `minimal` / `developer` / `headless` now
- **Q-012** explicitly defers these. Authoring placeholder bodies
  suggests commitment without operator-stated use case.
- Reserving the slots in `profiles/INDEX.md` is the right Q-012
  acknowledgment.
- A two-profile seed set is sufficient to validate the schema's
  pluralism contract.

## Schema-conformance verification

Until the validator ships (PR 10 TDD harness), schema-conformance is
**author-checked**:

- ✅ Every required top-level key (`schema_version`, `identity`,
  `hardware`, `kernel`, `packages`, `hooks`, `lifecycle`) present.
- ✅ `identity.id` matches filename (`sain-01.yaml` ↔ `id: sain-01`).
- ✅ `additionalProperties: false` enforced — no typo'd keys.
- ✅ `hardware.cpu.march` set to a real GCC `-march=` value
  (`znver5` for sain-01, `x86-64-v3` placeholder for
  old-workstation).
- ✅ `mixins:` list references files that exist
  (`role-workstation.yaml`, `whitelabel-default.yaml`,
  `observability-tier-1.yaml`).

Once PR 10 ships `tools/validate-profile`, both stubs gate CI on
schema-pass.

## Mixin composition validation (Q-002 working closure)

The hybrid model (single-parent + mixins) is validated by the
authored stubs:

- Both `sain-01` + `old-workstation` set `parent: null` (root
  profiles — no inheritance chain).
- Both compose three mixins (`role-workstation`,
  `whitelabel-default`, `observability-tier-1`).
- Merge produces: identity from profile / hardware from profile /
  kernel from profile / packages.base from profile + mixin appended /
  packages.role.workstation from mixin (deep-merged into profile) /
  packages.deny union'd / hooks appended per phase / whitelabel from
  mixin / observability from mixin (overridable by profile).

The conflict case (two mixins setting conflicting scalars) is **not**
exercised by this seed set — defer to a synthetic test case at PR 10
TDD harness scope.

## Q-002 closure recommendation (at Gate 3)

Adopt **single-parent + cross-cutting mixins** per SDD-004 § Inheritance
model. The seed profiles validate the model is workable; merge rules
are deterministic; conflicts produce clear build errors.

Closes as `D-NNN` in `docs/decisions.md` once operator signs off at
Gate 3.

## Validation harness preview

A `scripts/validate-profiles.sh` placeholder ships in this PR (no-op
body; documented to land at PR 10). The PR-10 implementation:

```sh
#!/usr/bin/env bash
set -euo pipefail
# Validates every profiles/*.yaml against schemas/profile.schema.yaml
# + every profiles/mixins/*.yaml against schemas/mixin.schema.yaml.
# Uses python3 jsonschema or yamale; substrate-decided at PR 10.
```

## Goals

1. **Two real profiles** validate the schema against distinct
   hardware classes (high-end AI workstation + constrained-resource
   alternate).
2. **Mixin composition** validates the hybrid Q-002 model.
3. **Reserved slots acknowledged** in `profiles/INDEX.md` for
   `minimal` / `developer` / `headless` per Q-012.
4. **No build-script content** — hooks reference scripts that don't
   yet exist; bodies land at Stage 2+. Schema-conformance is the only
   goal here.
5. **Operator-authoring template** — these stubs serve as authoring
   reference for future profile authors.

## Non-goals (this SDD)

- Does NOT author hook script bodies. References-only.
- Does NOT lock kernel config exhaustively for sain-01 (E101's
  responsibility at Stage 2 to fill in `CONFIG_*` enable/disable
  comprehensively).
- Does NOT pick the substrate. The profile YAML is substrate-agnostic;
  substrate adapter (Stage 2+) reads the YAML and emits
  substrate-native config.
- Does NOT commit `old-workstation` hardware specifics — operator
  supplies these once the actual machine is targeted.
- Does NOT pick brand identity (Q-003). `whitelabel-default` mixin is
  a placeholder.

## Open sub-questions

- **Q6-A** — Should `profiles/sain-01.yaml` pin the Blackwell PCI ID
  exactly (currently `10de:????`)? Resolves once operator procures
  the card and lspci-confirms. Stage 2+.
- **Q6-B** — Should the `old-workstation` profile body get filled in
  speculatively (operator-best-guess CPU / GPU / storage), or wait
  for actual machine spec? Recommend wait; speculative spec invites
  fabrication.
- **Q6-C** — Should the mixin merge order be `mixins → parent →
  profile` (mixins first, profile last) or `parent → mixins → profile`
  (parent first)? SDD-004 says child > parent > mixins; this implies
  mixins applied first, then parent, then child. Lock at Gate 3.
- **Q6-D** — Should there be a `profiles/_template.yaml` skeleton for
  new-profile authors to copy? Recommend yes; PR 6 may include it as
  a follow-up commit if not blocking.

## Way forward

1. **PR 6 (this PR)** — profile stubs + mixins + SDD + INDEX +
   placeholder validation harness.
2. **Stage Gate 3 (after PR 6 + PR 5 schema merge)** — operator
   reviews schema + two real profile bodies + mixin composition;
   locks the schema; Q-002 closes as D-NNN.
3. **PR 7-8** (parallel; already authored) — whitelabel mechanism
   binding fills in.
4. **PR 9-10** — TDD harness ships `tools/validate-profile` + CI
   gate.
5. **Stage 2+** — hook script bodies; substrate adapter; operator
   procurement triggers `old-workstation` body fill-in + Blackwell
   PCI ID lock.

## Cross-references

- Schema: [`../../schemas/profile.schema.yaml`](../../schemas/profile.schema.yaml)
- SDD-004 schema design: [`004-profile-schema.md`](004-profile-schema.md)
- Profile bodies: [`../../profiles/sain-01.yaml`](../../profiles/sain-01.yaml), [`../../profiles/old-workstation.yaml`](../../profiles/old-workstation.yaml)
- Mixins: [`../../profiles/mixins/`](../../profiles/mixins/)
- Profile index: [`../../profiles/INDEX.md`](../../profiles/INDEX.md)
- Decisions log: `docs/decisions.md` Q-002 + Q-012 (deferred reserved slots)
- Plan-agent macro-arc § PR 6: info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`
- SAIN-01 milestone (sain-01 profile target): info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md`
- E101 sovereign OS build (kernel compile flags + packaging): info-hub `wiki/backlog/epics/milestone-sain01/e101-sovereign-os-build.md`
