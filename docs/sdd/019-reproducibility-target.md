# SDD-019 — Reproducibility target (Q-015 resolution)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Closes findings: Q-015 (reproducibility target)
> Derived from: SDD-003 (substrate — mkosi primary), SDD-017 (ZFS),
> SDD-018 (kernel choice), SDD-015 (secure-boot), the build pipeline
> state machine in `scripts/build/orchestrate.sh` + `state.sh`.

## Problem

Q-015 ("Reproducibility target") has been open since PR 1. The
substrate (mkosi) supports reproducible builds; the kernel build is
operator-controlled; the state machine uses inputs-hash to skip
unchanged steps. But no SDD says what "reproducible" means for
sovereign-os specifically, what level of reproducibility we commit
to, and what we explicitly DON'T attempt.

## Decision: **strong build-reproducibility for the image, NOT
bit-identical operator-keys**

| Surface | Reproducibility target | Why this level |
|---|---|---|
| **mkosi-built image content** | bit-identical given same: profile YAML, substrate version, kernel source SHA, package versions | mkosi supports `Environment=SOURCE_DATE_EPOCH=...` + apt's Snapshots; operator can pin all inputs |
| **kernel .deb** | bit-identical given same: kernel source SHA, .config, KBUILD_BUILD_USER/HOST, SOURCE_DATE_EPOCH, compiler version | already declared in profile via `compile_flags`; only the operator-supplied build host varies |
| **whitelabel render** | bit-identical given same: profile YAML + whitelabel YAML | template rendering is deterministic (Python string substitution + file copy); no randomness; gated by `test_whitelabel_render_*.sh` |
| **substrate adapter emit** | bit-identical given same: profile YAML | mkosi-emit.sh + live-build-emit.sh both deterministic; gated by L3 |
| **signed artifacts (vmlinuz / EFI binaries)** | NOT bit-identical across operator keys | by design — signing key is operator-supplied per SDD-015; each operator's signed artifact has a different signature |
| **install-time-rendered files** (e.g. user-data from cloud-init) | NOT a build concern — operator-controlled | cloud-init applies per-machine state (hostname, SSH keys); not part of image-reproducibility scope |

## What must hold

1. **Same inputs → same image bytes** for the mkosi-built rootfs +
   kernel + whitelabel layer, given:
   - `SOURCE_DATE_EPOCH` pinned in env or `mkosi.conf`
   - Apt snapshot or local mirror pinning (`http://snapshot.debian.org/`)
   - Kernel source tag pinned via `profile.kernel.version_minimum`
     plus a stable-tag SHA recorded in `~/.sovereign-os/build-state/state.yaml`
     under each step's `inputs_hash`
   - Compiler version pinned (gcc-14 in current profile, per
     `01-bootstrap-forge.sh`)
2. **Drift detection**: re-running `orchestrate.sh run` against the
   same pinned inputs MUST produce the same outputs. The state
   machine's `inputs_hash` per step catches drift at the step level.
3. **Hash everything that can be hashed**: the build emits a
   `sha256sums.txt` for the final image (lives in step 09).

## What we explicitly don't commit to

- **Cross-operator bit-identicality** for signed artifacts (different
  keys = different signatures).
- **Cross-machine bit-identicality of the build host's filesystem
  state during build** — only the OUTPUT image is committed.
- **Reproducibility under non-mkosi substrates with future versions
  changing default behavior** — pinned mkosi version is part of the
  reproducibility contract.
- **First-boot final state** — cloud-init + first-login-assistant
  apply operator-specific config; the running system is not the
  build's output.

## How operators verify reproducibility

```sh
# Pin all inputs
export SOURCE_DATE_EPOCH=1700000000
export DEBIAN_SNAPSHOT="20260515T000000Z"
export SOVEREIGN_OS_KERNEL_TAG="v6.12.5"  # exact tag, not a "minimum"

# Build A
scripts/build/orchestrate.sh reset
scripts/build/orchestrate.sh run
sha256sum mkosi.<profile>.raw > /tmp/build-a.sha

# Build B — fresh state, same env
scripts/build/orchestrate.sh reset
scripts/build/orchestrate.sh run
sha256sum mkosi.<profile>.raw > /tmp/build-b.sha

# Compare
diff /tmp/build-a.sha /tmp/build-b.sha
# Expected: identical
```

The 09-image-verify.sh step (Stage 2+ expansion) will gain a
build-reproducibility self-test mode that runs this automatically
against a pinned-input fixture.

## Implementation gaps vs the contract (tracked)

- **Apt-snapshot pinning** — not yet enforced in build pipeline.
  Operator must set `DEBIAN_SNAPSHOT` env; mkosi.conf doesn't yet read
  it. Lands at Stage 2+.
- **`SOURCE_DATE_EPOCH` propagation** — read by mkosi natively; the
  step 04 kernel-compile.sh needs to also `export SOURCE_DATE_EPOCH`
  before `make bindeb-pkg`. Verify in next code pass.
- **Final-image sha256sums.txt** — step 09 emits the image hash but
  doesn't yet manifest per-file checksums into a Build Provenance
  record (in-toto layout). Stage 2+.
- **CI reproducibility self-test** — `tests/qemu/scaffold.sh` is
  scaffolded but doesn't yet build twice + compare. Stage 2+.

## Goals

1. **Same inputs → same image** for the parts within our control.
2. **Operator-verifiable** without specialized tooling (sha256sum
   is enough).
3. **Drift surfaces fast** via the state.yaml inputs_hash per step.
4. **Operator-controlled pinning** — `SOURCE_DATE_EPOCH`,
   `DEBIAN_SNAPSHOT`, `SOVEREIGN_OS_KERNEL_TAG` are the explicit
   knobs.

## Non-goals

- Does NOT promise cross-architecture reproducibility (x86_64 only
  in current profiles; arm64 future).
- Does NOT integrate with reproducible-builds.org's full toolchain
  (rebuilderd, etc.) — operator can post-build verify externally.
- Does NOT make signed artifacts cross-operator bit-identical.
- Does NOT make the first-boot system bit-identical — that's
  operator-state, not build-state.

## Cross-references

- SDD-003 § mkosi reproducible-build support
- SDD-015 § operator-supplied keys
- SDD-017 § ZFS pool created install-time (not build-time)
- SDD-018 § kernel build inputs
- `scripts/build/04-kernel-compile.sh` (KBUILD_BUILD_USER/HOST already pinned)
- `scripts/build/09-image-verify.sh` (will gain reproducibility self-test)
- `scripts/build/lib/state.sh` § state_inputs_hash (drift-detection primitive)
