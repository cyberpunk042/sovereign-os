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

## Pre-install hooks (per profile)

Profile `hooks.pre_install` array. Currently for `sain-01`:

- `friction-audit-spec.sh` — validates profile YAML internal consistency

## Build state + resume

State at `~/.sovereign-os/build-state/state.yaml`. Each step records its input hash; re-runs skip when nothing changed. Crash at step 7 of 12 → re-run resumes at step 7.

```sh
scripts/build/orchestrate.sh status     # see state
scripts/build/orchestrate.sh reset      # wipe state (confirms)
scripts/build/orchestrate.sh list       # list step IDs + status
```

## Observability

Logs at `~/.sovereign-os/log/build-<ISO8601>.jsonl` (JSON Lines; machine-readable) + colored stdout for operator.
