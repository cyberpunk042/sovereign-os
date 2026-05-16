# Pre-install lifecycle stage

What runs **before** the OS image exists on disk. All on the build host (your dev machine).

## Pipeline (driven by `scripts/build/orchestrate.sh run`)

| Step | Script | Purpose |
|---|---|---|
| 01 | `01-bootstrap-forge.sh` | Install Debian dev toolchain + mount 64 GB tmpfs at `/mnt/kernel_forge` |
| 02 | `02-kernel-fetch.sh` | Clone kernel.org-stable @ `v6.12` (shallow) into the forge |
| 03 | `03-kernel-config.sh` | Seed `.config` from running kernel → apply profile `kernel.config.enable/disable` → `olddefconfig` |
| 04 | `04-kernel-compile.sh` | `make -j$(nproc) bindeb-pkg` with `KCFLAGS="-march=znver5 ..."` |
| 05 | `05-substrate-prepare.sh` | mkosi (or live-build) adapter emits substrate-native config |
| 06 | `06-whitelabel-render.sh` | Render templates + overlays into substrate's skeleton/extra |
| 07 | `07-image-build.sh` | Invoke `mkosi build` → produces bootable disk image |
| 08 | `08-image-sign.sh` | `sbsign` vmlinuz + EFI binaries (if `secure_boot=signed`) |
| 09 | `09-image-verify.sh` | QEMU boot smoke test |

## Pre-install hooks

Live under `scripts/hooks/pre-install/`. Run as a batch via
`scripts/build/orchestrate.sh preflight`. Profile-aware; each hook
loads the active profile and either runs its checks, SKIPs (when the
profile doesn't require this gate), or FAILs (with a remediation hint).

| Hook | Purpose | Profile-conditioned |
|---|---|---|
| `friction-audit-spec.sh` | Validates profile YAML internal consistency (CPU march/features, GPU role coherence, storage roles, vfio_companion, motherboard PCIe constraints) | always runs |
| `preflight-network.sh` | DNS resolves the Debian mirror + huggingface.co; HTTP 200 from `<mirror>/debian/dists/<release>/Release`; default route present | always runs; can skip HF via `SOVEREIGN_OS_PREFLIGHT_SKIP_HF=1` |
| `preflight-tpm.sh` | TPM2 device node + tpm2-tools + UEFI vars + MOK key/cert coherence | SKIPs unless `kernel.cmdline.secure_boot=true` |
| `preflight-storage.sh` | Each declared storage device size-class matches lsblk reality; zpool/zfs tooling present for zfs-tiered layouts; >10GB writable disk available | always runs; size-mismatches WARN (not FAIL) |

Run the full preflight against the active profile:

```sh
scripts/build/orchestrate.sh preflight
# or against a specific profile
scripts/build/orchestrate.sh preflight --profile old-workstation
# or in plan-only / observability mode
SOVEREIGN_OS_DRY_RUN=1 scripts/build/orchestrate.sh preflight
```

Preflight never mutates build state. It is safe to run repeatedly + at
any time (before `run`, after a `reset`, between aborted builds).

Adding a new pre-install hook is "drop a `*.sh` script into
`scripts/hooks/pre-install/`, make it executable, source
`scripts/build/lib/common.sh`, emit `PASS`/`FAIL`, exit appropriately."
The orchestrator's `preflight` command auto-discovers it. Layer 3 test
`tests/nspawn/test_orchestrator_preflight.sh` gates the count + names.

## Build state + resume

State at `~/.sovereign-os/build-state/state.yaml`. Each step records its input hash; re-runs skip when nothing changed. Crash at step 7 of 12 → re-run resumes at step 7.

```sh
scripts/build/orchestrate.sh status     # see state
scripts/build/orchestrate.sh reset      # wipe state (confirms)
scripts/build/orchestrate.sh list       # list step IDs + status
```

## Observability

Logs at `~/.sovereign-os/log/build-<ISO8601>.jsonl` (JSON Lines; machine-readable) + colored stdout for operator.
