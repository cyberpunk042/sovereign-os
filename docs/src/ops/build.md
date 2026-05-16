# Build pipeline (operator handbook)

Driven by `scripts/build/orchestrate.sh`. See the [install runbook](../install-runbook.md) for the full flow.

## Quick reference

```sh
# Default: sain-01 profile + mkosi substrate
sudo scripts/build/orchestrate.sh run

# Override profile / substrate
SOVEREIGN_OS_PROFILE=old-workstation \
SOVEREIGN_OS_SUBSTRATE=live-build \
  sudo scripts/build/orchestrate.sh run

# CI mode (no QEMU; no actual compile)
SOVEREIGN_OS_DRY_RUN=1 \
SOVEREIGN_OS_SKIP_QEMU=1 \
  sudo scripts/build/orchestrate.sh run

# Status / list / reset
scripts/build/orchestrate.sh status
scripts/build/orchestrate.sh list
scripts/build/orchestrate.sh reset
```

## Env-var overrides (per IaC bar)

| Var | Default | Used by |
|---|---|---|
| `SOVEREIGN_OS_PROFILE` | `sain-01` | every step |
| `SOVEREIGN_OS_SUBSTRATE` | `mkosi` | step 05 + 07 |
| `SOVEREIGN_OS_STATE_DIR` | `~/.sovereign-os/build-state` | state lib |
| `SOVEREIGN_OS_LOG_DIR` | `~/.sovereign-os/log` | logging lib |
| `SOVEREIGN_OS_LOG_LEVEL` | `info` | logging lib |
| `SOVEREIGN_OS_NONINTERACTIVE` | unset | prompts |
| `SOVEREIGN_OS_DRY_RUN` | unset | steps 04 + 07 + 08 + 09 |
| `SOVEREIGN_OS_SKIP_QEMU` | unset | step 09 |
| `SOVEREIGN_OS_FORGE_DIR` | `/mnt/kernel_forge` | step 01 + 02 + 04 |
| `SOVEREIGN_OS_FORGE_SIZE` | `64G` | step 01 |
| `SOVEREIGN_OS_PARALLEL` | `$(nproc)` | step 04 |
| `SOVEREIGN_OS_MOK_KEY` / `_CERT` | (operator-supplied) | step 08 |
| `SOVEREIGN_OS_QEMU_TIMEOUT` | `300` | step 09 |

## Substrate choice

| Substrate | Adapter | Status |
|---|---|---|
| `mkosi` | `scripts/build/adapters/mkosi-emit.sh` | **Primary**; SDD-003 recommendation |
| `live-build` | `scripts/build/adapters/live-build-emit.sh` | ALT-A; available |
| `rpm-ostree` | (not implemented) | ALT-B; Stage 2+ if Q-016 picks Fedora |
| `nixos` | (not implemented) | ALT-C; Stage 2+ if Q-016 picks NixOS |
