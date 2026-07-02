# Install runbook (SAIN-01 default profile)

End-to-end runbook for building + installing sovereign-os on the
SAIN-01 hardware. Covers pre/during/post-install with operator
checkpoints. Substrate-aware: uses mkosi (primary per SDD-003); the
live-build path swaps the `05/07` build steps but the lifecycle is
identical.

## Prerequisites

| Item | How to confirm |
|---|---|
| SAIN-01 hardware assembled | `friction-audit` script (pre-install spec mode) PASS |
| Debian 13 (Trixie) build host | `cat /etc/debian_version` shows 13.x |
| ≥ 80 GB free RAM for tmpfs forge | `free -g` shows ≥ 80 in `available` |
| mkosi installed (or live-build) | `mkosi --version` ≥ 23.0 |
| podman installed | `podman --version` ≥ 4.x |
| `python3-yaml`, `python3-jsonschema` | `python3 -c 'import yaml, jsonschema'` |

If any are missing, `scripts/build/01-bootstrap-forge.sh` installs the
build toolchain (kernel-compilation deps); the rest is operator-supplied.

## 1. PRE-INSTALL — build the image

### 1.1 Profile spec validation

```sh
SOVEREIGN_OS_PROFILE=sain-01 \
  scripts/hooks/pre-install/friction-audit-spec.sh
```

Confirms profile YAML is internally consistent (CPU features, GPU
roles, ZFS sync=always on tank/context, M.2_2 blocker for sain-01, etc.).
Exit 0 = ready to build.

### 1.2 Run the build pipeline

Bare-minimum build (defaults — useful for first-pass / dev iteration):

```sh
# All knobs env-overridable; restart-from-state across crashes
SOVEREIGN_OS_PROFILE=sain-01 \
SOVEREIGN_OS_SUBSTRATE=mkosi \
  sudo scripts/build/orchestrate.sh run
```

Full sovereign build (SDD-019 reproducibility + SDD-015 signed + SDD-022
encrypted; operator-owned chain end-to-end):

```sh
SOVEREIGN_OS_PROFILE=sain-01 \
SOVEREIGN_OS_SUBSTRATE=mkosi \
SOURCE_DATE_EPOCH=$(date +%s) \                             # SDD-019: pinned epoch
DEBIAN_SNAPSHOT=20260515T000000Z \                          # SDD-019: pinned mirror
SOVEREIGN_OS_KERNEL_TAG=v6.12.5 \                           # SDD-018: kernel-org-stable exact tag
SOVEREIGN_OS_PK_KEY=/path/to/PK.priv \                      # SDD-015: Platform Key (preferred)
SOVEREIGN_OS_PK_CERT=/path/to/PK.der \                      # SDD-015
SOVEREIGN_OS_MOK_KEY=/path/to/MOK.priv \                    # SDD-015: MOK fallback
SOVEREIGN_OS_MOK_CERT=/path/to/MOK.der \                    # SDD-015
SOVEREIGN_OS_ENCRYPT=1 \                                    # SDD-022: enable encryption
SOVEREIGN_OS_ENCRYPT_TPM_BIND=1 \                           # SDD-022: PCR-7+11 binding
SOVEREIGN_OS_ENCRYPT_PASSPHRASE_FILE=/run/install/pass \    # SDD-022: passphrase floor
  sudo scripts/build/orchestrate.sh run
```

Dry-run first (validates all step scripts exist + profile loads + no
state mutation):

```sh
SOVEREIGN_OS_PROFILE=sain-01 \
  scripts/build/orchestrate.sh run --dry-run
```

Executes 9 steps:

| Step | What | Time (sain-01) |
|---|---|---|
| 01-bootstrap-forge | apt deps + tmpfs (64 GB) at /mnt/kernel_forge | 5 min |
| 02-kernel-fetch | clone linux-stable v6.12 shallow | 2 min |
| 03-kernel-config | seed + apply znver5 enable/disable + olddefconfig | 1 min |
| 04-kernel-compile | `make -j24 bindeb-pkg` with znver5 KCFLAGS | 30-45 min |
| 05-substrate-prepare | mkosi.conf + skeleton + extra + repart emitted | < 1 min |
| 06-whitelabel-render | render templates + overlays into skeleton/extra | < 1 min |
| 07-image-build | `mkosi build` (apt + sealing) | 10-20 min |
| 08-image-sign | sbsign vmlinuz + EFI binaries with MOK | 1 min |
| 09-image-verify | QEMU smoke boot | 2-5 min |

Status anytime: `scripts/build/orchestrate.sh status`. Crashed mid-step? Re-run `run` — resumes.

### 1.3 Image output

After step 09 passes:

```
build/sain-01/output/
  sain-01                       ← bootable disk image
  vmlinuz-6.12.x-znver5
  initrd.img-...
  sha256sums.txt                ← SDD-019: digest of every artifact
  build-provenance.json         ← SDD-019: SLSA v1 in-toto manifest
  ...
```

### 1.4 Verify the build is reproducible (optional, recommended)

```sh
sovereign-osctl audit provenance build/sain-01/output/build-provenance.json
```

Prints the manifest header (predicateType, subject count), the
reproducibility inputs that drove the build (profile, substrate,
SOURCE_DATE_EPOCH, DEBIAN_SNAPSHOT), and cross-checks every subject
digest against `sha256sums.txt`. Exit 0 = clean; exit 2 = tampered
or non-reproducible.

Independent reproducibility verification — run the build again on
another machine with the SAME env vars and compare:

```sh
diff /machine-A/sha256sums.txt /machine-B/sha256sums.txt
# Expected: identical line for every artifact except signed binaries
# (operator-key-specific signatures by design per SDD-015).
```

## 2. DURING-INSTALL — write to disk

### 2.1 Dump image to first NVMe

**Use the safety-gated verb (Round 134 / SDD-024 friction-audit F-01 closure).**
Raw `dd` is too easy to point at the wrong disk.

```sh
# 1. PREVIEW: shows device fingerprint (model · serial · capacity · mount
#    state) + the command that WOULD execute. Writes nothing.
sovereign-osctl install image --plan build/sain-01/output/sain-01 --to /dev/nvme1n1

# 2. EXECUTE: gates on (a) not-mounted-root, (b) whole-disk-not-partition,
#    (c) SOVEREIGN_OS_CONFIRM_DESTROY=YES, (d) typed-device-path confirm.
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
  sudo sovereign-osctl install image build/sain-01/output/sain-01 --to /dev/nvme1n1
```

The verb HARD REFUSES if the target is the currently-running root or
its parent — no `dd` typo can nuke the host the operator is sitting at.

Legacy raw-`dd` is still possible for operators who explicitly want it
(`sudo dd if=... of=... bs=4M status=progress conv=fsync`) but the
runbook recommends the gated path.

### 2.2 Boot from NVMe + MOK enrollment

First boot: UEFI MOK Manager prompts to enroll the sovereign-os MOK.
Enter password set in `scripts/hooks/during-install/mok-enroll.sh`.

### 2.3 ZFS pool + datasets

```sh
SOVEREIGN_OS_POOL_DEVICES="/dev/nvme0n1p2 /dev/nvme1n1" \
  sudo scripts/hooks/during-install/zfs-pool-create.sh
sudo scripts/hooks/during-install/zfs-datasets-create.sh
```

Creates `tank` (RAID 0) + `tank/models` (1M lz4) + `tank/context`
(16k zstd-9 copies=2 sync=always) + `tank/agents` (128k zstd-3).

## 3. POST-INSTALL — first-boot hooks

These run automatically once at first boot if the live-build hook
wired them as a systemd `oneshot`. Otherwise invoke manually:

```sh
sudo scripts/hooks/post-install/friction-audit-runtime.sh      # validate real hardware
sudo scripts/hooks/post-install/vfio-bind-4090.sh              # bind 4090 to vfio-pci
sudo scripts/hooks/post-install/network-vlan-config.sh         # VLAN 100/200 split
sudo scripts/hooks/post-install/tetragon-policy-load.sh        # load sovereign-kernel-fence
sudo scripts/hooks/post-install/zfs-arc-clamp.sh               # clamp ARC to 128 GB
sudo scripts/hooks/post-install/nvidia-driver-bind.sh          # nouveau blacklist + nvidia check
sudo scripts/hooks/post-install/workstation-shell-setup.sh     # bash-completion + /etc/skel
sudo scripts/hooks/post-install/first-login-assistant.sh       # interactive customization
```

Reboot once after `vfio-bind-4090.sh` so the VFIO module owns the
4090 from initramfs.

## 4. POST-INSTALL — inference stack

### 4.1 Install systemd units

```sh
sudo cp -r systemd/system/*.{service,timer} /etc/systemd/system/
sudo mkdir -p /etc/sovereign-os
sudo cp systemd/env.examples/inference-*.env /etc/sovereign-os/
sudo systemctl daemon-reload
```

### 4.2 Pull a model (sain-01 Oracle Core default = Nemotron)

```sh
sudo sovereign-osctl models pull nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16
sudo sovereign-osctl models pull microsoft/bitnet-b1.58-2B-4T   # Pulse model
```

### 4.3 Enable inference services

```sh
# Per-profile activation; sain-01 enables all four
sudo systemctl enable --now sovereign-pulse sovereign-logic-engine sovereign-oracle-core sovereign-router
sudo systemctl enable --now sovereign-zfs-scrub.timer sovereign-tetragon-verify.timer sovereign-models-sync.timer
```

### 4.4 Verify

```sh
sovereign-osctl status
sovereign-osctl doctor
sovereign-osctl inference status
sovereign-osctl audit friction
sovereign-osctl audit perimeter
sovereign-osctl audit storage
```

All should PASS. Logs: `journalctl -u sovereign-* -f`.

### 4.5 First inference

```sh
# Through the router (auto-routes by request shape)
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "microsoft/bitnet-b1.58-2B-4T", "messages": [{"role": "user", "content": "hello"}]}'
# → routed to Pulse (port 8081, bitnet.cpp)

curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "auto", "messages": [{"role": "user", "content": "```python def f(): pass ```"}]}'
# → routed to Oracle Core (port 8083, vLLM + DFlash)
```

## 5. ONGOING MANAGEMENT

| Task | Command |
|---|---|
| Profile switch | `sovereign-osctl profiles switch <id>` |
| Re-render whitelabel | `sovereign-osctl whitelabel apply <id>` |
| Re-run first-login assistant | `sovereign-osctl assistant` |
| Tetragon reload | `sovereign-osctl perimeter reload` |
| Manual scrub | `sovereign-osctl maintenance scrub` |
| Inference logs | `sovereign-osctl inference logs <tier>` |
| Decommission | `sovereign-osctl decommission start` (3-phase; gated by env var) |

## 5b. OBSERVABILITY (SDD-016 Layer A / B / C)

Sovereign-os ships **three observability layers**, all local-default
and operator-pullable — no phone-home, no required external service.

### Layer A — structured JSONL logs

Every script in the pipeline emits structured JSONL events.

| Source | Path |
|---|---|
| Build host (per-operator) | `~/.sovereign-os/log/build-<ts>.jsonl` |
| Installed system | `/var/log/sovereign-os/*.jsonl` |

Surface them through sovereign-osctl (no jq required):

```sh
sovereign-osctl journal list             # tabular index with event counts + ts range
sovereign-osctl journal show <file>      # pretty-printed table (TS / LEVEL / STEP / MSG)
sovereign-osctl journal tail 3           # 3 most-recently-updated files
sovereign-osctl journal errors           # all warn/error entries across all files
```

Auto-rotation: `sovereign-log-rotate.timer` rotates daily per profile
(`observability.log_retention_days`; default 14d for sain-01,
30d for headless, 7d for minimal).

### Layer B — Prometheus textfile metrics

51 metric names emitted into `/var/lib/node_exporter/textfile_collector/sovereign-os-*.prom`,
covering: build pipeline (9 steps) · pre-install (4 hooks) ·
during-install (4 hooks) · post-install (8 hooks) · recurrent
maintenance (7 hooks) · inference router · Tetragon perimeter. See
`docs/observability/dashboards/README.md` for the full inventory.

Three surfaces:

```sh
# A) raw inspection (no Grafana needed)
sovereign-osctl metrics list             # which .prom files exist + when last updated
sovereign-osctl metrics show <name>      # pretty-print one .prom file
sovereign-osctl metrics tail 5           # 5 most-recently-updated
sovereign-osctl metrics health           # stale / malformed detection

# B) derived alerts (no Alertmanager needed)
sovereign-osctl alerts                   # rule engine; ALERT/WARN with remediation
sovereign-osctl alerts --json            # machine-readable for fleet tooling

# C) continuous self-monitoring (hourly timer)
sovereign-osctl maintenance alerts-check # on-demand; cached at /var/lib/sovereign-os/alerts.json
```

Operators running Grafana import the three JSON dashboards at
`docs/observability/dashboards/`:
`sovereign-os-overview.json` · `sovereign-os-inference.json` ·
`sovereign-os-install.json`.

CI enforces a three-way contract via Layer 1 lint:
  - every metric the code emits is in the README inventory
  - every metric the README inventory lists is emitted by a script
  - every lifecycle hook calls `emit_metric` (or carries an explicit waiver)

### Layer C — operator CLI overview

```sh
sovereign-osctl status            # human-readable: profile / kernel / ZFS / Tetragon / GPUs / whitelabel
sovereign-osctl status --json     # machine-readable for fleet aggregation (8-key contract)
sovereign-osctl doctor            # profile-conditioned sanity check; emits remediation hints
sovereign-osctl audit provenance  # verify build-provenance.json + sha256sums.txt (SDD-019)
```

### Sovereignty posture

All Layer A/B/C surfaces are **local-default**. Operators decide whether
to scrape, ship logs off-host, or run Grafana — sovereign-os never
phones home and never dictates the observability stack downstream.

## 5c. RECOVERY — when a build step fails mid-pipeline

(Round 135 / F-13 closure.) The 9-step pipeline is resumable + tracks
state in `~/.sovereign-os/build-state/state.yaml`. When a step fails:

```sh
# 1. Diagnose: shows the failed step, its recorded fail_reason, and
#    the last 5 error/warn events from the JSONL log, then surfaces
#    4 recommended next actions with their tradeoffs.
scripts/build/orchestrate.sh recover
```

The four options the `recover` verb presents:

| Option | When to choose |
|---|---|
| (a) Fix underlying issue + `orchestrate.sh run` | Most common — pipeline resumes from the failed step (inputs_hash gates skip already-completed steps) |
| (b) `rewind <step>` + `run` | Failure was transient / environmental; want a clean retry without changing inputs |
| (c) `skip <step>` + `run` | Step genuinely doesn't apply to your profile (e.g. 02-kernel-fetch on a substrate-default profile) |
| (d) `reset` + `run` | Want to start over (DESTRUCTIVE — wipes all build state) |

Full event log inspection:

```sh
sovereign-osctl journal show <jsonl-stem>    # specific run
sovereign-osctl journal errors               # warn+error across all runs
```

## 6. Troubleshooting

| Symptom | Diagnostic |
|---|---|
| Build crashes mid-kernel-compile | `scripts/build/orchestrate.sh status` → re-run; resumes |
| friction-audit fails M.2_2 check | Power down; remove anything in M.2_2 slot; reboot |
| `nvidia-smi` shows both GPUs (4090 should be hidden) | VFIO didn't load early enough; check `/proc/cmdline` for `vfio-pci.ids=`; rebuild initramfs |
| Tetragon SIGKILLing legitimate process | `sudo journalctl -u tetragon -f`; add allowlist entry to `sovereign-kernel-fence.yaml`; reload |
| Oracle Core OOM | `ORACLE_KV_CACHE_DTYPE=fp8` (default for sain-01); reduce `gpu_memory_utilization` in vLLM start script |
| Router 502 for tier X | `sovereign-osctl inference logs <tier>`; tier daemon likely crashed/not started |

## 7. Other profile installs (cross-profile differences)

Sovereign-os ships 5 profiles. SAIN-01 is the default reference;
others differ in concrete ways:

### 7.1 `old-workstation` (constrained AI dev box)

- `kernel.source: substrate-default` — steps 02/03/04 short-circuit (Q18-A)
- `storage.layout: ext4` — rootfs-format-ext4 handles disk
- `kernel.cmdline.secure_boot: shim` — operator enrolls MOK post-install
- Inference: `SOVEREIGN_OS_LOGIC_BACKEND=llama_cpp` (4090 only); no
  Pulse + no Oracle Core + no DFlash. Tetragon optional.

```sh
SOVEREIGN_OS_PROFILE=old-workstation \
SOVEREIGN_OS_LOGIC_BACKEND=llama_cpp \
SOVEREIGN_OS_MOK_KEY=/path/MOK.priv \
SOVEREIGN_OS_MOK_CERT=/path/MOK.der \
  sudo scripts/build/orchestrate.sh run
```

### 7.2 `minimal` (VM baseline)

- generic x86-64-v3, no GPU, virtio-blk root + ext4
- `kernel.source: substrate-default`; `secure_boot: signed` (useful for
  VM-testing the signing chain without real hardware)
- No first-login-assistant (boots to a quiet ready state)
- Useful for: pre-hardware QEMU smoke, substrate-adapter validation
  against a 3rd profile shape

### 7.3 `developer` (polyglot dev workstation)

- generic x86-64-v3, 16 GB RAM, single nvme-pcie-4, ext4
- `kernel.source: substrate-default`; `secure_boot: shim`
- role-developer mixin: full polyglot toolchain (gcc/clang/rust/go/
  python/node + gdb/lldb/strace/valgrind + cmake/meson/ninja +
  podman/buildah/skopeo + vim/neovim/emacs-nox)
- first-login-assistant left interactive (operator picks setup)

### 7.4 `headless` (bare-metal server)

- 8c/16t, 32 GB ECC, nvme rootfs + dual sata-ssd raid1 data
- `secure_boot: signed` (server-class operator-owned PK chain)
- role-server mixin: auditd + fail2ban + chrony + unattended-upgrades
  + hardened SSH (PermitRootLogin no, PasswordAuth no, X11Forwarding no)
- All 4 preflight hooks MANDATORY (preflight-tpm required since
  secure_boot != none)
- 30-day log retention; no GUI; no first-login-assistant

### 7.5 Build all 5 profiles in dry-run

```sh
for p in sain-01 old-workstation minimal developer headless; do
  SOVEREIGN_OS_PROFILE="$p" scripts/build/orchestrate.sh run --dry-run
done
```

CI gates this via `tests/nspawn/test_e2e_dry_run_smoke.sh` — 26
assertions across all 5 profiles + cross-profile invariants.
