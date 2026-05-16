# SDD-018 — Kernel choice + tuning (Q-007 resolution)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Closes findings: Q-007 (kernel: stock vs custom-tuned)
> Derived from: `profiles/*.yaml` § kernel block,
> `scripts/build/02-kernel-fetch.sh`, `03-kernel-config.sh`,
> `04-kernel-compile.sh`, SAIN-01 milestone hardware spec.

## Problem

Q-007 ("Kernel choice — stock · custom-tuned") has been open since
PR 1. The sain-01 profile already declares a custom Zen-5-tuned
kernel build from kernel.org-stable; old-workstation + minimal
declare `source: substrate-default`. But no SDD says when each
applies, what the build pipeline does for each, or why.

## Decision: **dual kernel strategy per profile**

| Profile | kernel.source | What ships | Why |
|---|---|---|---|
| sain-01 | `kernel.org-stable` (≥ 6.12) | custom-tuned `linux-image-<ver>-sovereign.deb` with -march=znver5 + Zen-5 specific AVX-512 codegen | Wrings every cycle out of the 9900X CCD-0 BitNet path; pulls in atypical config (ATLANTIC for Marvell 10 GbE; ZFS; VFIO; SECURITY_BPF_LSM for Tetragon kernel-level perimeter) |
| old-workstation | `substrate-default` | stock Debian linux-image-amd64 | No tuning win on constrained hardware; substrate-managed reduces our maintenance surface |
| minimal | `substrate-default` | stock Debian linux-image-amd64 | VM/headless baseline; whatever the host kernel offers is fine |

Profile decides. Build pipeline conditions on it.

## What `source: kernel.org-stable` triggers in the build pipeline

`scripts/build/02-kernel-fetch.sh`:
- Shallow clone of https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git
- Checks out a stable tag ≥ `profile.kernel.version_minimum`
- Lands in `${SOVEREIGN_OS_FORGE_DIR}/linux/`

`scripts/build/03-kernel-config.sh`:
- Seeds .config from `/proc/config.gz` (running kernel's defaults)
- Applies `profile.kernel.config.enable[]` (each → `=y` or `=m` depending on the symbol)
- Applies `profile.kernel.config.disable[]` (each → unset)
- Runs `make olddefconfig` to resolve dependencies
- Honors `profile.kernel.config.require_microcode` (amd / intel / none)

`scripts/build/04-kernel-compile.sh`:
- `make -j$(nproc) bindeb-pkg` with `profile.kernel.compile_flags`
  exported (KCFLAGS, KCPPFLAGS, KBUILD_BUILD_USER, KBUILD_BUILD_HOST)
- Output: `linux-image-<ver>-sovereign_*.deb` + headers + libc-dev

The resulting .deb is installed into the rootfs via
`mkosi.extra/var/cache/sovereign-os/kernel/` (or live-build's
`includes.chroot` equivalent) and `dpkg -i`'d during the chroot
finalization.

## What `source: substrate-default` triggers

Steps 02-04 are SKIPPED. The substrate adapter (mkosi / live-build)
pulls `linux-image-amd64` from the Debian archive. No custom .deb.

This is the load-bearing simplification for old-workstation + minimal —
no kernel-forge ramdisk needed; no -j$(nproc) compile minutes; no
maintenance burden tracking kernel releases.

## Why kernel.org-stable for sain-01

1. **Zen 5 codegen** — Debian stable's kernel (as of trixie) targets
   x86-64-v3 by default. The 9900X Zen 5 supports AVX-512 + new VNNI
   + bf16. `-march=znver5` unlocks all of it. Net effect for BitNet
   inference: measurable on the CCD-0 ternary path.
2. **Atypical config** — Tetragon needs SECURITY_BPF_LSM + BPF_LSM
   which are off by default in Debian stable's kernel config. ZFS is
   DKMS in Debian; building into the kernel image skips an initramfs
   step. ATLANTIC for Marvell 10 GbE may or may not be enabled
   depending on the Debian build; we force it on.
3. **Operator-owned chain** — SDD-015 establishes that operator
   signs vmlinuz with their Platform Key. Building the kernel
   ourselves means we own every byte from .config → vmlinuz → sbsign
   → boot.

## Why substrate-default for old-workstation + minimal

1. **No tuning win** — neither profile has hardware that benefits
   from znver5 codegen (one is older/unknown, one is generic VM).
2. **Maintenance economy** — substrate handles security patches,
   ABI compatibility, module signing. Our job is just to integrate.
3. **Faster builds** — skip steps 02-04. CI/dev iterations stay
   sub-minute.

## Kernel version pinning + upgrade cadence

`profile.kernel.version_minimum` = "6.12" on sain-01. The build
script picks the latest stable >= that. Operator-controlled upgrades:
bump `version_minimum`, re-run `orchestrate.sh run`. The state.yaml's
inputs-hash on step 02 changes → 02 re-runs → 03/04 re-run. No image
rebuild needed except for kernel changes.

Stock-substrate profiles inherit the substrate's upgrade pace —
Debian point releases roll forward by default; operator pins via
`/etc/apt/preferences` if needed.

## Schema-level enforcement

`schemas/profile.schema.yaml § kernel.source.enum` already allows the
right set: kernel.org-stable, kernel.org-mainline, longterm,
substrate-default. New options can be added additively.

## Build state + dry-run

`scripts/build/orchestrate.sh run --dry-run` already enumerates all 9
steps. The substrate-default profiles' steps 02-04 will appear in the
dry-run plan but their actual run is a no-op skip — the step scripts
self-check `profile.kernel.source` and exit 0 when it's substrate-default.

(Note: as of this commit, the step scripts proceed regardless of
source. The substrate-default short-circuit lands as a follow-up
when the step scripts get their L3 test coverage; tracked in
sub-question Q18-A.)

## Layer 3 coverage status

- `tests/nspawn/test_orchestrator_dry_run.sh` — enumerates all 9 steps
  including 02-04 across all 3 profiles (21 assertions per profile)
- `tests/schema/test_profile_schema_conformance.py` — gates the
  kernel block schema across all profiles

Per-step L3 (against fake step environments) lands at Stage 2+ when
the build-host setup is more determinate.

## Goals

1. **Profile-conditioned strategy** — operator picks per-profile.
2. **Sovereignty for production** — sain-01 owns every byte of
   its kernel.
3. **Maintenance economy for the rest** — old-workstation + minimal
   ride the substrate's release cadence.
4. **Schema-enforced** — no profile can declare a kernel.source value
   outside the enum.

## Non-goals (this SDD)

- Does NOT pick a specific stable kernel version — that's the
  operator's per-build choice via `version_minimum`.
- Does NOT prescribe a kernel-cmdline policy (separate concern;
  partially in `profile.kernel.cmdline`).
- Does NOT lock the LTS-vs-stable choice — schema supports both;
  operator picks per-profile.
- Does NOT mandate kernel module signing (covered by SDD-015's
  secure-boot posture).

## Open sub-questions (Q18-X)

- **Q18-A** — Should steps 02/03/04 short-circuit-by-source at the
  step-script level (currently they assume custom-build path)?
  Recommend: **YES** — small Stage-2+ patch; each step checks
  `profile.kernel.source` and exits 0 with a "skipping (substrate
  -default)" log if not custom. Until then, the orchestrator simply
  doesn't run steps 02-04 for substrate-default profiles via a
  pre-build conditional (future patch).
- **Q18-B** — Should sain-01 try kernel.org-mainline for the AMD IOMMU
  fixes that don't backport? Recommend: **stay on stable** until a
  concrete fix is needed; mainline is operator's choice if the
  installer surfaces it as a flag.
- **Q18-C** — Should we ship a kernel-config-diff against Debian's
  stable config for transparency? Recommend: **YES**, when the
  custom config stabilizes — generate via `diff` in step 03's output.
  Stage 2+.

## Cross-references

- `profiles/sain-01.yaml` § kernel
- `profiles/old-workstation.yaml` § kernel.source=substrate-default
- `profiles/minimal.yaml` § kernel.source=substrate-default
- `schemas/profile.schema.yaml` § kernel.source enum
- `scripts/build/02-kernel-fetch.sh`
- `scripts/build/03-kernel-config.sh`
- `scripts/build/04-kernel-compile.sh`
- `tests/nspawn/test_orchestrator_dry_run.sh` (enumerates all profiles)
- SDD-015 (secure-boot — vmlinuz signing is independent of build source)
- SDD-017 (ZFS layout — kernel must include ZFS-module support for sain-01)
