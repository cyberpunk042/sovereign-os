# SDD-010 — Stage 2 stub (post-Gate-5 build/feature work)

> Status: **scoping — Stage 2 in flight; substantive work landing as commits on main**

## What Stage 2 covers

Per the Plan-agent macro-arc, Stage 2 (post-Gate-5) is where actual
build scripts + lifecycle tools land. Per the operator's directive
("WHEN ITS IN THE GOAL YOU PROCEED"), Stage 2 work began landing
directly on main alongside the Foundation tier closure, rather than
gated on a discrete Gate-5 ceremony.

## What's already on main (Stage 2 first round)

### Build pipeline (scripts/build/)
- `orchestrate.sh` — state-aware multi-step driver with subcommands
  (run/status/reset/rewind/skip/list/help)
- `lib/state.sh` — IaC-bar restart-from-state library
- `lib/logging.sh` — structured observable logging (plain + JSONL)
- `lib/common.sh` — strict-mode + ERR trap + profile loader + helpers
- `01-bootstrap-forge.sh` — tmpfs + Debian build toolchain
- `02-kernel-fetch.sh` — clone kernel.org-stable @ profile version
- `03-kernel-config.sh` — apply profile enable/disable + olddefconfig
- `04-kernel-compile.sh` — make -j bindeb-pkg with profile KCFLAGS
- `05-substrate-prepare.sh` — dispatches to mkosi/live-build adapter
- `06-whitelabel-render.sh` — invokes render.py
- `07-image-build.sh` — mkosi build (or substrate-equivalent)
- `08-image-sign.sh` — sbsign with MOK when secure_boot=signed
- `09-image-verify.sh` — QEMU smoke boot
- `adapters/mkosi-emit.sh` — profile YAML → mkosi.conf/skeleton/extra/repart

### Hook scripts (scripts/hooks/)
- 4 during-install (zfs-pool, zfs-datasets, mok-enroll, rootfs-format-ext4)
- 8 post-install (friction-audit-runtime, vfio-bind, network-vlan, tetragon-policy-load, zfs-arc-clamp, first-login-assistant, workstation-shell-setup, nvidia-driver-bind)
- 3 recurrent (zfs-scrub, tetragon-policy-verify, model-catalog-sync)
- 3 decommission (secure-wipe-context, zfs-pool-destroy, secure-wipe)

### Whitelabel
- `scripts/whitelabel/render.py` — substrate-agnostic Layer-1 render engine implementing all 7 SDD-007 strategies + legal-floor enforcement
- `scripts/whitelabel/first-boot-greeting.sh` — first-boot-script strategy

### Lifecycle CLI (Q-019)
- `scripts/sovereign-osctl` — 10-command lifecycle management:
  status / doctor / assistant / profiles / whitelabel / perimeter /
  models / audit / maintenance / decommission

## What's deferred (Stage 2 next rounds)

- Render engine Layer 2 substrate adapters for live-build / rpm-ostree / NixOS (only mkosi shipped)
- Full Layer 2 unit-test coverage for render engine / mixin merger / kernel config
- Q-017 inference-backend stack decision + integration (LocalAI vs vLLM vs llama.cpp vs custom)
- Q-018 first-login assistant TUI elaboration (current is CLI; TUI optional)
- Q-019 whitelabel-apply-on-running-system (currently renders to /tmp; live-apply for non-rebuild surfaces is Stage 2+ next round)
- Template / overlay bodies in whitelabel/default/templates/* and overlays/*
- Calamares branding assets (Q7-A + Q-008 dependent)
- Layer 5 hardware-conformance tests (gated on SAIN-01 procurement per Q-009)

## Cross-references

- Plan-agent macro-arc § "STAGE 2 onwards": info-hub raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md
- SDD-008 harness spec (specifies what tests Stage 2 owes alongside each script): docs/sdd/008-test-harness.md
- SDD-009 harness bootstrap (what tests already shipped): docs/sdd/009-test-harness-bootstrap.md
