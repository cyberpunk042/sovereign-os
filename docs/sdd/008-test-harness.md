# SDD-008 — TDD harness specification (Plan-agent PR 9)

> Status: **review** (specification; harness scaffold ships at PR 10)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-05-16
> Closes findings: none
> Resolves at Gate 5: contributes to **Q-010** (CI infrastructure) + **Q-014** (decommission test scope) + **Q-015** (reproducibility target)
> Derived from: SDD-003 substrate survey; SDD-004 profile schema; SDD-006 surface audit; SDD-007 whitelabel mechanism; Plan-agent macro-arc § PR 9

## Problem

The OS-build pipeline ships scripts that touch kernel config, ZFS
layouts, VFIO bindings, Tetragon policies, network VLAN config,
GPU drivers, and dozens of identity surfaces. **Mistakes are
expensive** — a bad kernel config means reboot-loops; a wrong VFIO
binding hides the wrong GPU from the host; a Tetragon policy typo
SIGKILLs legitimate processes.

The operator's "do not rush, do not minimize, do not hack" bar
demands **specifying tests before scripts** (TDD). This SDD specifies
the harness — what test layers exist, what they verify, what
virtualization stack they use, what their invariants are. **PR 10
implements the scaffold; subsequent Stage-2+ PRs add test bodies
alongside each script.**

## Five test layers (the TDD pyramid for image-build pipelines)

### Layer 1 — **Schema / lint** (fastest; pure CI; no virtualization)

Validates declarative artifacts against schemas:
- Profile YAMLs against `schemas/profile.schema.yaml`
- Whitelabel YAMLs against `schemas/whitelabel.schema.yaml`
- Mixin YAMLs against `schemas/mixin.schema.yaml` (future)
- Markdown lint (SDDs, handoffs, decisions log)
- Decisions-log linter (D-NNN sequence, Q-X cross-refs)
- SDD-index consistency check
- Cross-repo reference guard (SDD-001 Q-A/Q-B/Q-C)
- Hook script reference validation (each `hooks.*.script:` path exists in `scripts/hooks/`)
- Shellcheck for `scripts/**/*.sh`

**Runtime**: < 30 seconds in CI.
**Tooling**: `python3` + `jsonschema` (or `yamale`); `mdformat`; `shellcheck`.
**Trigger**: every PR, on every push.
**Gate**: PR cannot merge with failures.

### Layer 2 — **Unit tests** (fast; CI; component-level)

Tests individual build-step functions in isolation:
- Mock filesystem + mock apt + mock dpkg
- Whitelabel render engine: input YAML → expected file-tree changeset
- Profile mixin merger: input parent + mixins → expected effective profile
- Kernel config generator: input profile → expected `.config` snippet
- friction-audit-spec generator: input profile → expected check list

**Runtime**: < 2 minutes.
**Tooling**: `pytest` (or substrate-decided language equivalent).
**Trigger**: every PR.
**Gate**: PR cannot merge with failures.

### Layer 3 — **Stage acceptance tests** (medium; chroot + systemd-nspawn)

Tests each lifecycle stage's invariants in a controlled environment:

#### Pre-install stage
- Build pipeline reaches a known-good chroot state for a profile
- Custom kernel `.deb` builds successfully (or stubbed for unit)
- `friction-audit-spec` script runs against a sample profile

#### During-install stage
- ZFS pool create + dataset stratification produces expected `zpool status` output
- VFIO GRUB cmdline contains expected `vfio-pci.ids=`
- Network VLAN config produces expected `/etc/systemd/network/` files
- MOK enrollment workflow completes (signed via test CA)

#### Post-install first-boot stage
- Tetragon policy loads cleanly (`tetragon` daemon status active)
- `tank/context/security_audit.log` writable + Tetragon writes a test event
- VFIO binding hides the RTX 4090 from host's `nvidia-smi` output
- First-login assistant script executes without error in a non-interactive harness
- ARC clamp: `arcstat -s c` returns 128GB target

#### Decommission stage (Q-014 scope decision pending)
- ZFS pool destroy completes; secure-wipe overwrites; final disk state clean

**Runtime**: 2–10 minutes per stage.
**Tooling**: `chroot` for filesystem-level; `systemd-nspawn` for service-startup; both run within CI containers.
**Trigger**: every PR that touches `scripts/`, `profiles/`, `whitelabel/`, or `schemas/`.
**Gate**: PR cannot merge with failures.

### Layer 4 — **Integration tests** (slow; QEMU; full image boot)

Boots the produced image end-to-end in QEMU:
- Build a minimal image for the test profile
- Boot in QEMU with virtualized firmware (UEFI / OVMF)
- Run inside-VM smoke tests:
  - `cat /etc/os-release` → matches whitelabel branding
  - `uname -r` → contains profile's kernel version + LOCALVERSION
  - `zpool status tank` → healthy
  - `systemctl is-active tetragon` → active
  - `lspci -k` → VFIO bindings match profile
- Optional: secure-boot verification (UEFI + signed kernel + MOK)
- Optional: PCIe passthrough emulation for VFIO smoke (limited)

**Runtime**: 10–30 minutes per profile.
**Tooling**: `qemu-system-x86_64` + OVMF; `mkosi qemu` or substrate equivalent.
**Trigger**: merge to `main` + label-trigger (`[test integration]`) on PRs.
**Gate**: blocks releases; warns on `main`.

### Layer 5 — **Hardware-conformance tests** (gated; real hardware only)

Same assertions as Layer 4 but on real SAIN-01 hardware:
- friction-audit script PASS on actual ASUS ProArt + 9900X + dual GPU
- `lspci` shows IOMMU groups + VFIO binding cleanly
- ZFS RAID 0 throughput within expected envelope
- Tetragon SIGKILL on test container's `/bin/sh` exec
- Network split: VLAN 100 reachable from mgmt, VLAN 200 isolated
- Pulse module: bitnet.cpp throughput on Zen 5 ≥ 5 tok/sec
- Weaver atomic-write contention test
- Auditor SIGKILL latency benchmark

**Runtime**: 30 minutes – several hours.
**Tooling**: bare-metal on SAIN-01; manual operator-triggered OR self-hosted runner.
**Trigger**: only when matching hardware is detected + operator opt-in.
**Gate**: blocks SAIN-01 release tags; never blocks `main`.

## Virtualization stack (per layer)

| Layer | Stack | Speed | Faithfulness |
|---|---|---|---|
| 1 schema/lint | none (pure parse) | fastest | n/a |
| 2 unit | none (Python test harness) | fast | low — mocks |
| 3 stage acceptance | chroot + systemd-nspawn | medium | medium — kernel shared with host |
| 4 integration | QEMU + OVMF | slow | high — real boot |
| 5 hardware | bare-metal SAIN-01 | hours | exact |

### chroot — filesystem-level assertions
- Package presence: `chroot $ROOT dpkg -l <package>`
- File presence + content: `[ -f $ROOT/etc/os-release ] && grep -q 'ID=sovereign' $ROOT/etc/os-release`
- Per-strategy whitelabel verification

### systemd-nspawn — service-startup assertions
- `systemd-nspawn -D $ROOT systemctl is-active tetragon`
- Inter-service ordering invariants (Tetragon before podman; ZFS before tank/* mounts)
- Tetragon TracingPolicy load + a test syscall

### QEMU — full boot
- `qemu-system-x86_64 -m 8G -enable-kvm -drive file=image.img,format=raw …`
- UEFI + secure-boot variant via OVMF (`OVMF_CODE.fd` + `OVMF_VARS.fd`)
- Snapshot before test runs; revert after

### qemu-user — cross-arch validation (future; non-blocking)
- Only relevant if profiles target non-x86_64 (e.g., a future aarch64 profile)
- Out of scope for sain-01 + old-workstation (both x86_64)

## Per-stage invariants (declarative)

Each lifecycle stage has a list of named invariants. The harness
asserts each invariant; a stage is "done" when all its invariants
pass.

### Pre-install invariants
- **PRE-INV-1** — Kernel `.deb` builds successfully for the profile's `kernel.compile_flags`
- **PRE-INV-2** — All `packages.profile:` packages resolve from configured apt sources
- **PRE-INV-3** — Whitelabel render engine produces a file-tree changeset with no legal-floor violations
- **PRE-INV-4** — Substrate adapter (per Q-001 Gate 2) produces substrate-native config from the profile

### During-install invariants
- **INST-INV-1** — friction-audit returns 0 (or gated on hardware-class)
- **INST-INV-2** — ZFS pool create completes; `zpool status` healthy
- **INST-INV-3** — All `tank/<dataset>` datasets exist with correct properties
- **INST-INV-4** — MOK enrollment workflow completes (if secure-boot: signed)
- **INST-INV-5** — Boot loader (GRUB or systemd-boot) installed; entries point at custom kernel

### Post-install first-boot invariants
- **FB-INV-1** — Hostname matches profile (or operator-supplied)
- **FB-INV-2** — Whitelabel surfaces match: `cat /etc/os-release` matches whitelabel branding
- **FB-INV-3** — ZFS datasets mounted; ARC clamped per profile
- **FB-INV-4** — Tetragon TracingPolicy loaded; daemon active
- **FB-INV-5** — VFIO binding active; host's `nvidia-smi` reports primary GPU only
- **FB-INV-6** — Network VLAN config applied; mgmt + data NICs distinct routing
- **FB-INV-7** — First-login assistant script idempotent (re-runnable safely)

### Post-install recurrent invariants
- **REC-INV-1** — ZFS scrub completes weekly without errors
- **REC-INV-2** — Tetragon policy verification passes daily
- **REC-INV-3** — Model catalog sync runs without errors

### Decommission invariants (Q-014 scope)
- **DEC-INV-1** — `zpool destroy` succeeds; pools fully removed
- **DEC-INV-2** — secure-wipe overwrites; disk state shows no residual sovereign-os data
- **DEC-INV-3** — `/var/lib/sovereign-os/` cleared

## Test discovery + naming convention

```
tests/
├── schema/
│   ├── test_profile_schema_conformance.py
│   ├── test_whitelabel_schema_conformance.py
│   └── test_mixin_schema_conformance.py
├── lint/
│   ├── test_decisions_log_sequence.py
│   ├── test_sdd_index_consistency.py
│   ├── test_cross_repo_references.py
│   └── test_hook_script_paths.py
├── unit/
│   ├── test_whitelabel_render.py
│   ├── test_profile_merger.py
│   └── test_kernel_config_gen.py
├── chroot/
│   ├── stage_pre_install/
│   ├── stage_during_install/
│   └── stage_post_install/
├── nspawn/
│   ├── stage_post_install/
│   └── service_ordering/
├── qemu/
│   ├── sain-01_boot.sh
│   ├── old-workstation_boot.sh
│   └── secure-boot_variant.sh
├── hardware/
│   ├── sain-01_friction.sh    # gated; only runs on real SAIN-01
│   ├── sain-01_throughput.sh
│   └── sain-01_perimeter.sh
├── INDEX.md
└── README.md
```

Naming: `test_<area>_<subject>.py` for Python; `<stage>_<subject>.sh`
for shell.

Test discovery:
- `pytest tests/schema tests/lint tests/unit` — Layers 1+2
- `bash tests/chroot/run.sh <profile>` — Layer 3 chroot
- `bash tests/nspawn/run.sh <profile>` — Layer 3 nspawn
- `bash tests/qemu/<profile>_boot.sh` — Layer 4
- `bash tests/hardware/<profile>_*.sh` — Layer 5 (gated)

## CI execution model

`.github/workflows/test.yml`:

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
  schedule:
    - cron: "0 4 * * *"   # nightly Layer 4 against latest main

jobs:
  schema-lint:
    # Layer 1 — every PR, blocking
    runs-on: ubuntu-latest
    timeout-minutes: 5

  unit:
    # Layer 2 — every PR, blocking
    runs-on: ubuntu-latest
    timeout-minutes: 10

  chroot-stage:
    # Layer 3 chroot — PRs touching scripts/profiles/whitelabel
    runs-on: ubuntu-latest
    timeout-minutes: 20
    if: contains(github.event.pull_request.labels.*.name, 'stage-test') ||
        contains(github.event.head_commit.message, '[test stage]') ||
        github.event_name == 'push' && github.ref == 'refs/heads/main'

  nspawn-stage:
    # Layer 3 nspawn — same trigger
    runs-on: ubuntu-latest
    timeout-minutes: 20

  qemu-integration:
    # Layer 4 — main + label-trigger + nightly
    runs-on: ubuntu-latest        # KVM-capable runner; verify Q-010
    timeout-minutes: 45
    if: github.event_name == 'push' && github.ref == 'refs/heads/main' ||
        contains(github.event.pull_request.labels.*.name, 'integration-test') ||
        github.event_name == 'schedule'

  # Layer 5 (hardware) — operator-side; not in CI
```

## Flake policy

Q-014-adjacent. Operator's "do this clean and right and professional"
bar implies zero tolerance for flaky tests. Policy:

- A test failing intermittently MUST be marked `@flake` AND the
  underlying race / network / timing issue logged as an issue.
- Flake tests block release tags but warn (not fail) on `main`.
- If a flake persists > 30 days unfixed, it's removed from CI (not
  rewritten as `@xfail`); the underlying bug becomes blocking.
- No retries on failure (operator's "do not hack" bar). If a test
  fails, it failed.

## Goals

1. **Schema-first validation** — every YAML in the repo is schema-
   gated; typos catch at PR time.
2. **Lifecycle-stage invariants** — each stage's correctness is
   asserted independently; pre-install correctness doesn't depend on
   first-boot tests running.
3. **Hardware-free coverage ≥ 70%** — Layers 1-4 cover most of the
   pipeline without real hardware.
4. **Hardware-gated tests honest** — Layer 5 NEVER mocks; tests that
   require hardware skip cleanly when hardware is absent.
5. **CI sub-30-min for Layers 1-3** — fast PR feedback for the common
   case.
6. **Reproducibility-aware** — test outputs deterministic; Layer 4
   re-runnable with bit-identical results (Q-015 contribution).
7. **Per-substrate adapter coverage** — Layer 2 unit tests cover each
   adapter's input→output mapping independently of the substrate
   binary.

## Non-goals (this SDD)

- Does NOT author test bodies. PR 10 ships the scaffold; subsequent
  Stage-2+ PRs add tests alongside scripts.
- Does NOT pick a Python-vs-Go-vs-other test framework decisively
  (PR 10 makes this concrete).
- Does NOT decide CI runner type (KVM-enabled vs not) — Q-010 covers.
- Does NOT decide reproducibility level (bit-for-bit vs content-equiv)
  — Q-015 closes at PR 4 substrate decision + here as a follow-up.

## Open sub-questions

- **Q9-A** — Python `pytest` vs Go `testing` for Layer 2 unit tests?
  Recommend Python (faster iteration, smaller surface).
- **Q9-B** — `jsonschema` vs `yamale` for Layer 1 schema validation?
  Recommend `jsonschema` (Draft 2020-12 compliance).
- **Q9-C** — Should Layer 3 chroot tests use `proot` (no root needed)
  vs `unshare` (lighter than full chroot, no root if user-namespaces
  enabled)? Recommend `unshare` for CI portability.
- **Q9-D** — Layer 5 hardware tests: should there be a self-hosted
  GitHub Actions runner on the SAIN-01 itself (post-procurement), or
  operator manually triggers via SSH? Recommend manual SSH initially;
  self-hosted runner is Q-010 long-tail.
- **Q9-E** — Test report aggregation: just pytest output, or full
  Allure / JUnit XML / Stagger-style dashboard? Recommend pytest
  output + JUnit XML for CI integration; no dashboard.

## Way forward

1. **PR 9 (this PR)** — harness specification.
2. **PR 10** — scaffold implementation: `tests/schema/` + `tests/lint/`
   + Layer 3 scaffolds + `.github/workflows/test.yml` + first passing
   tests for SDD-001..SDD-007 already-merged content. **Stage Gate 5
   fires after merge — Foundation tier COMPLETE.**
3. **Gate 5** — operator reviews 10-PR foundation arc holistically;
   authorizes Stage 2 (actual build scripts).
4. **Stage 2+** — each new script PR adds test bodies alongside;
   harness now has real content to gate on.

## Cross-references

- SDD-003 substrate survey: `docs/sdd/003-substrate-survey.md` (Layer 4 QEMU smoke-test parallels mkosi qemu)
- SDD-004 profile schema: `docs/sdd/004-profile-schema.md` (Layer 1 schema validates)
- SDD-005 initial profile stubs: `docs/sdd/005-initial-profiles.md` (Layer 1 tests these stubs)
- SDD-006 surface audit + SDD-007 whitelabel mechanism (Layer 1 + Layer 4 verify legal-floor preservation)
- Plan-agent macro-arc § PR 9 + § PR 10
