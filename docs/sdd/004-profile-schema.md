# SDD-004 — Profile schema (resolves Q-002 inheritance model at Gate 3)

> Status: **review** (schema specification; locked at Stage Gate 3 alongside PR 6 profile stubs)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-05-16
> Closes findings: none
> Resolves at Gate 3 (paired with PR 6): **Q-002** (profile inheritance model)
> Derived from: Plan-agent macro-arc § PR 5 (info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`); charter (`docs/sdd/000-charter.md`); SAIN-01 milestone (info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md`); SDD-003 substrate survey (parallel — substrate-agnostic schema)

## Problem

`sovereign-os` produces a **multi-profile** OS from day 1. The default
profile is **`sain-01`** (RTX Pro 6000 + Zen 5 AI Workstation per the
SAIN-01 milestone). Alternate from day 1: **`old-workstation`** (11 GB
RAM + 8 GB GPU). Reserved slots: `minimal`, `developer`, `headless`.

Before authoring any profile body, we must lock the **schema** — the
declarative contract that every profile must satisfy. Without a
schema:

- Profiles drift (no shared shape → divergent overrides).
- Validation is ad-hoc (each profile audits itself).
- Inheritance has no formal model (Q-002 stays unresolved).
- The whitelabel mechanism (PR 8) can't bind cleanly.
- The TDD harness (PR 9-10) can't schema-validate.
- Activation hooks per lifecycle phase aren't standardised.

This SDD specifies the schema **before** any profile body exists. PR 6
(profile stubs) validates the schema against real targets (`sain-01`
+ `old-workstation`); Gate 3 locks the schema once instances reveal
gaps.

## Schema design dimensions

Each profile is a **declarative YAML document** with the following
top-level keys (full formal schema at
[`schemas/profile.schema.yaml`](../../schemas/profile.schema.yaml)).

### 1. Identity

```yaml
identity:
  id: sain-01                       # unique slug; matches filename profiles/<id>.yaml
  name: "SAIN-01 AI Workstation"    # human-readable
  version: "1.0.0"                  # semver of the profile body
  parent: null                      # inheritance graph; null = root profile
  status: draft                     # draft | active | deprecated | abandoned
  maintainer: cyberpunk042          # GitHub handle or team
  description: |                    # one-paragraph mission
    Bare-metal AMD Zen 5 + dual-NVIDIA AI orchestration workstation
    with custom Zen-5-tuned kernel, ZFS-stratified storage,
    VFIO-isolated dual GPUs, kernel-level Tetragon perimeter,
    and the SRP Trinity runtime (Pulse / Weaver / Auditor).
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string slug | yes | Matches `profiles/<id>.yaml` filename |
| `name` | string | yes | Human-readable |
| `version` | semver | yes | Bumps on schema-affecting changes |
| `parent` | string slug \| null | yes | See § Inheritance |
| `status` | enum | yes | Lifecycle state |
| `maintainer` | string | yes | Accountability anchor |
| `description` | string | yes | ≥ 30 words |

### 2. Hardware target

```yaml
hardware:
  cpu:
    architecture: x86_64            # x86_64 | aarch64 | ...
    family: amd-zen5                # amd-zen5 | intel-meteorlake | ...
    march: znver5                   # GCC -march= value
    features:
      required:
        - avx512f
        - avx512_vnni
        - avx512_bf16
        - avx512_fp16
      preferred:
        - sha_ni
    cores:
      physical: 12
      threads: 24
      topology: dual-ccd            # single-ccd | dual-ccd | tile-based
      partition:                    # per-CCD/tile responsibility map (optional)
        ccd0_mask: "0xfff"          # cores 0-5 (12 threads) — Pulse
        ccd1_mask: "0xff000"        # cores 6-9 (8 threads)  — Weaver+Auditor
        host_mask: "0xf00000"      # cores 10-11 (4 threads) — kernel/IRQ
  gpu:
    - vendor: nvidia
      model: rtx-pro-6000-blackwell
      pci_id: "10de:????"           # actual ID at procurement
      vram_gb: 96
      role: primary                 # primary | vfio | headless
      driver: nvidia-560-open
    - vendor: nvidia
      model: rtx-3090
      pci_id: "10de:2204"
      vram_gb: 24
      role: vfio
      vfio_companion: "10de:1ad8"   # audio device alongside
  memory:
    minimum_gb: 128
    target_gb: 256
    type: ddr5
    ecc: false                      # ECC unavailable on consumer DDR5
  storage:
    layout: zfs-tiered              # zfs-tiered | btrfs | ext4 | ...
    devices:
      - role: rootfs
        type: nvme-pcie-5
        count: 2
        topology: raid0             # operator-accepted no-redundancy trade-off
    datasets:                       # ZFS-specific; ignored for non-ZFS layouts
      - name: tank/models
        recordsize: 1M
        compression: lz4
        redundant_metadata: most
        purpose: "100GB+ weight files, sequential reads"
      - name: tank/context
        recordsize: 16k
        compression: zstd-9
        copies: 2
        sync: always
        purpose: "state-fabric race-free atomic transitions"
      - name: tank/agents
        recordsize: 128k
        compression: zstd-3
        purpose: "runtime cache + sub-agent scratch"
  network:
    - role: mgmt
      vendor: intel
      model: i226-v
      speed_gbps: 2.5
      vlan: 100
      default_gateway: true
    - role: data
      vendor: marvell
      model: aqc113c
      speed_gbps: 10
      vlan: 200
      mtu: 9000
      default_gateway: false
  motherboard:
    vendor: asus
    model: proart-x870e-creator
    bios_pinned: false              # operator pins post friction-audit pass
    pcie_constraints:
      - description: "M.2_2 must remain empty to preserve x8/x8 GPU bifurcation"
        check: m2_2_empty
        severity: blocker
```

The hardware block is **descriptive** (what the profile targets), not
**prescriptive** (what to install). Build pipeline reads it to
generate kernel config, fstab, GRUB cmdline, VFIO binding, network
config, etc.

### 3. Kernel

```yaml
kernel:
  source: kernel.org-stable         # kernel.org-stable | xanmod | liquorix | substrate-default
  version_minimum: "6.12"
  packaging: bindeb-pkg             # bindeb-pkg | rpm | nix
  compile_flags:
    KCFLAGS: "-march=znver5 -O3 -pipe -mabm -madx -mavx512f -mavx512dq -mavx512bw -mavx512vl -mavx512bf16 -mavx512fp16"
    KCPPFLAGS: "-march=znver5"
  config:
    enable:
      - ATLANTIC                    # Marvell AQC113C 10GbE (corrects L0 dump's CONFIG_AQC111 typo)
      - ZFS
      - VFIO_PCI
      - INTEL_IOMMU
      - AMD_IOMMU
      - SECURITY_BPF_LSM            # for Tetragon
    disable:
      - DEBUG_KERNEL_DAVE           # example placeholder
    require_microcode: amd
  cmdline:
    base:
      - quiet
      - splash
    vfio:
      - "vfio-pci.ids=10de:2204,10de:1ad8"
      - "amd_iommu=on"
      - "iommu=pt"
    secure_boot: signed              # signed | shim | disabled (Q-006)
  modules:
    blacklist:
      - nouveau                     # nvidia-open replaces
    load_at_boot:
      - zfs
      - nvidia
```

### 4. Package sets (layered)

```yaml
packages:
  base:                             # always-installed, every profile inherits
    - openssh-server
    - sudo
    - tmux
    - curl
    - git
    - python3-minimal
    - python3-pip
    - htop
  role:                             # role-specific (sub-profile)
    workstation:
      - zfsutils-linux
      - zfs-dkms
      - nvidia-open-kernel-dkms
      - nvidia-driver
      - nvidia-smi
      - nvidia-container-toolkit
      - podman
      - tetragon
  profile:                          # this-profile-only additions
    - bitnet-cpp-runtime            # placeholder; actual package name TBD
    - vllm                          # via container or pip; placeholder
  deny:                             # never install (cross-cutting deny-list)
    - popularity-contest            # phone-home; sovereignty-incompatible
    - apport                        # phone-home
    - snapd                         # not in scope
```

### 5. Activation hooks (per lifecycle phase)

```yaml
hooks:
  pre_install:                      # before image is built; substrate-side
    - id: friction-audit-spec
      type: validation
      script: scripts/hooks/pre-install/friction-audit-spec.sh
      mandatory: true
  during_install:                   # at install-time; installer-side
    - id: zfs-pool-create
      type: setup
      script: scripts/hooks/during-install/zfs-pool-create.sh
      mandatory: true
    - id: mok-enroll
      type: secure-boot
      script: scripts/hooks/during-install/mok-enroll.sh
      mandatory: false              # secure-boot posture per Q-006
  post_install_first_boot:          # first-login; assistant-driven if enabled
    - id: tetragon-policy-load
      type: security
      script: scripts/hooks/post-install/tetragon-policy-load.sh
      mandatory: true
    - id: network-vlan-config
      type: network
      script: scripts/hooks/post-install/network-vlan-config.sh
      mandatory: true
    - id: first-login-assistant
      type: interactive
      script: scripts/hooks/post-install/first-login-assistant.sh
      mandatory: false              # Q-018 — operator opt-out path
  post_install_recurrent:           # periodic; cron/timer
    - id: zfs-scrub
      type: maintenance
      schedule: weekly
      script: scripts/hooks/recurrent/zfs-scrub.sh
    - id: model-catalog-sync
      type: maintenance
      schedule: daily
      script: scripts/hooks/recurrent/model-catalog-sync.sh
  decommission:                     # wipe / dispose
    - id: zfs-pool-destroy
      type: cleanup
      script: scripts/hooks/decommission/zfs-pool-destroy.sh
      mandatory: true
    - id: secure-wipe
      type: cleanup
      script: scripts/hooks/decommission/secure-wipe.sh
      mandatory: true
```

Each hook has:
- `id` — unique slug within phase
- `type` — taxonomy tag (validation, setup, security, network, interactive, maintenance, cleanup)
- `script` — relative path to script; substrate-agnostic shell or interpreter
- `mandatory` — true = build fails if hook absent/non-zero exit; false = soft
- `schedule` — for `post_install_recurrent` only (`hourly` / `daily` / `weekly` / `monthly` / cron expr)

### 6. Lifecycle metadata

```yaml
lifecycle:
  evolution_policy: replaceable     # frozen | append-only | replaceable
  supported_substrate:
    - mkosi >= 23.0
    - live-build >= 20240101
  supported_kernel:
    - "6.12.x"
    - "6.13.x"
  deprecation_target: null          # ISO date when this profile retires; null = no plan
  successor_profile: null           # forward-pointer if deprecated
```

Evolution policy:
- `frozen` — schema body never changes; bug fixes only
- `append-only` — additions allowed; removals/changes forbidden
- `replaceable` — full body can change between minor versions

### 7. Whitelabel binding (forward reference to PR 7-8)

```yaml
whitelabel:
  profile: default                  # references whitelabel/<name>.yaml
  surfaces:                         # subset (or "all"); see PR 7 audit
    - all
  legal_compliance: dfsg-only       # dfsg-only (Debian trademark floor) | trademark-cleared | internal-only
```

The actual whitelabel surface catalog + mechanism land in PR 7 + PR 8.
Profile schema reserves the binding key.

### 8. Observability binding

```yaml
observability:
  telemetry_sink: prometheus-local  # prometheus-local | otel | none (Q-013)
  log_retention_days: 30
  audit_hooks:
    tetragon: tank/context/security_audit.log
    install: ~/.sovereign-os/log/install-${EPOCH}.log
    build: .sovereign-os-build/log/build-${EPOCH}.log
  metrics_endpoint: "127.0.0.1:9090"
```

Reserved keys; Q-013 (observability bindings) resolves the actual
backends at Stage 2+.

## Inheritance model (Q-002 resolution)

**Recommendation: single-parent inheritance with explicit composition for cross-cutting concerns.**

| Approach | Pro | Con |
|---|---|---|
| **Single-parent inheritance** | Simple to validate; clear lineage; easy to reason about | Cross-cutting reuse (e.g., "all profiles use the same whitelabel") requires duplicate config |
| **Multiple inheritance** | More expressive | Diamond problem; merge-order ambiguity; hard to debug |
| **Pure composition (mixins)** | Maximum reuse; flexible | Complex resolution rules; harder to audit a profile's effective config |
| **Hybrid (single-parent + cross-cutting mixins)** ⭐ | Single-parent for primary lineage; explicit composition for whitelabel + observability + role-package-sets | Slightly more schema surface; benefits outweigh cost |

**Adopted (Q-002 resolution at Gate 3, pending operator approval)**:

- **Primary lineage**: single-parent. Each profile names ≤ 1 parent
  in `identity.parent`. The schema processor merges parent → child
  with child-wins-on-conflict.
- **Cross-cutting mixins**: explicit `mixins:` top-level array
  referencing reusable fragments (`mixins/<name>.yaml`). Examples:
  - `mixins/whitelabel-default.yaml` — common whitelabel binding
  - `mixins/observability-tier-1.yaml` — common observability config
  - `mixins/role-workstation.yaml` — workstation-role package set
- **Merge rules** (deterministic; documented):
  - Scalars: child > parent > mixins (last applied wins)
  - Lists: child appends to parent, with `deny-list` entries removing
    items
  - Maps: deep-merge with child-wins-on-conflict
- **Conflict resolution**: if two mixins set conflicting scalars,
  the build fails (no silent precedence between mixins).

This lets `sain-01` and `old-workstation` share the `role-workstation`
mixin without duplication, while keeping each profile's primary
lineage trivially auditable.

## Schema format choice

Plan-agent surfaces YAML vs TOML vs HCL. Recommendation: **YAML**.

| Format | Pro | Con |
|---|---|---|
| **YAML** ⭐ | Matches selfdef + info-hub conventions; rich type system; comment-friendly; widely tooled | Anchor/merge ambiguity (mitigated by linter); whitespace-sensitive |
| TOML | Stricter; no anchor ambiguity | Less expressive for nested structures; lists-of-maps awkward |
| HCL | Most expressive; first-class object expressions | Foreign toolchain; less library support outside HashiCorp ecosystem |

YAML is the operator's native ecosystem. Anchor/merge ambiguity is
addressed by the formal schema (`schemas/profile.schema.yaml`) +
schema-validation in CI (PR 10 TDD harness).

## Goals

1. **Schema-first** — the schema exists before any profile body. PR 6
   validates the schema against real instances.
2. **Substrate-agnostic** — the schema doesn't bake in `mkosi` /
   `live-build` / `rpm-ostree` semantics. Each substrate has an
   adapter that reads the profile YAML and produces substrate-native
   config.
3. **Multi-profile elegant** — N profiles share a common core via
   single-parent + mixins. No N-fold duplication.
4. **Forward-compatible** — additional schema fields can land without
   breaking existing profiles (additive schema migrations).
5. **Validation-strict** — CI rejects profiles that don't validate
   against the schema; rejects unknown top-level keys to catch typos.
6. **Whitelabel-ready** — schema reserves the binding key (`whitelabel:`)
   for PR 7-8 to fill in the mechanism.
7. **Observability-ready** — schema reserves observability keys for
   Stage 2+ to wire in.

## Non-goals (this SDD)

- Does NOT author profile bodies. PR 6 lands `sain-01.yaml` +
  `old-workstation.yaml` stubs.
- Does NOT pick the substrate. Schema is substrate-agnostic;
  substrate-adapter layer lives elsewhere (Stage 2+ once substrate
  decided at Gate 2).
- Does NOT lock the whitelabel mechanism. The binding key is
  reserved; PR 7 + PR 8 fill in the surface.
- Does NOT decide observability backends. The keys are reserved;
  Q-013 resolves at Stage 2+.
- Does NOT specify the activation-hook script contents. Hooks
  reference scripts in `scripts/hooks/<phase>/<id>.sh`; the scripts
  themselves land at Stage 2+.

## Open sub-questions

- **Q5-A** — Should the schema use JSON Schema Draft 2020-12 or
  use a simpler validator-friendly subset? Plan-agent recommendation:
  start with Draft 2020-12; downgrade if tooling friction emerges.
- **Q5-B** — Versioning: should profile `version` follow semver
  (1.2.3) or date-versioning (2026-05-16)? Plan-agent: semver for
  schema-affecting changes; date-versioning is operator-facing only.
- **Q5-C** — Where do mixins live? `mixins/<name>.yaml` at repo root,
  or `profiles/mixins/<name>.yaml`? Plan-agent: `profiles/mixins/` to
  group with profiles.
- **Q5-D** — Should the schema include a `secrets:` block for
  per-profile secrets (e.g., API tokens for download)? Or are secrets
  strictly env-var + filesystem-detected per IaC bar? Plan-agent:
  env-var-only; no schema slot for secrets.
- **Q5-E** — Hook script language: bash mandated, or per-hook
  declarable (`type: python` / `type: bash`)? Plan-agent: declarable
  via shebang + extension; schema doesn't constrain language.

## Validation flow

1. Operator authors `profiles/sain-01.yaml`.
2. CI runs `tools/validate-profile sain-01.yaml`.
3. Validator:
   - Loads `schemas/profile.schema.yaml`.
   - Resolves inheritance (parent + mixins → effective profile).
   - Schema-validates effective profile against schema.
   - Schema-validates each referenced mixin against mixin schema.
   - Reports: PASS / FAIL with file + line + violation reason.
4. CI gate: PASS required for merge.

Validator implementation: simple Python or Go (TBD at PR 10 TDD
harness PR). Not in this PR's scope.

## Way forward

1. **PR 5 (this PR)** — schema + this SDD; substrate-agnostic.
2. **PR 6** — first profile stubs (`sain-01` + `old-workstation`)
   conforming to this schema. Validates the schema against real
   targets. **Stage Gate 3** locks schema after revision based on
   PR 6 feedback.
3. **PR 7-8** — whitelabel mechanism fills in the binding key.
4. **PR 9-10** — TDD harness ships the validator + CI gate.
5. **Stage 2+** — substrate adapter layer + hook script bodies +
   observability backends.

## Cross-references

- Formal schema: [`schemas/profile.schema.yaml`](../../schemas/profile.schema.yaml)
- Charter: `docs/sdd/000-charter.md` (mission + IaC bar + multi-profile from day 1)
- SDD-001 cross-repo boundaries: `docs/sdd/001-cross-repo-boundaries.md`
- SDD-002 documentation pipeline: `docs/sdd/002-documentation-pipeline.md`
- SDD-003 substrate survey (parallel; substrate-agnostic schema): `docs/sdd/003-substrate-survey.md`
- Decisions log: `docs/decisions.md` Q-002 (resolves at Gate 3 alongside PR 6)
- Plan-agent macro-arc § PR 5: info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`
- SAIN-01 milestone (hardware target this schema must accommodate): info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md`
- 11 epics (operational domains this schema's hook phases cover): info-hub `wiki/backlog/epics/milestone-sain01/e1??-*.md`
- Future `profiles/sain-01.yaml` (PR 6)
- Future `profiles/old-workstation.yaml` (PR 6)
- Future `profiles/mixins/role-workstation.yaml` (PR 6)
- Future `tools/validate-profile` (PR 10)
