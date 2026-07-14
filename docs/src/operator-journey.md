# Operator journey — clone to decommission

> The full lifecycle of a sovereign-os deployment, end-to-end, with
> exact commands, expected outputs, customization points, and what to
> do when something fails.
>
> Pair this with [`sain-01-master-spec.md`](./sain-01-master-spec.md)
> (the WHAT) — this doc is the HOW + WHEN.

---

## The six stages

```
  ┌────────────┐     ┌────────────┐     ┌────────────┐
  │   STAGE 1  │ →   │   STAGE 2  │ →   │   STAGE 3  │
  │ Onboarding │     │   Build    │     │  Install   │
  │  + decide  │     │  + verify  │     │  + boot    │
  └────────────┘     └────────────┘     └────────────┘
       │                  │                  │
       v                  v                  v
   ~10 min            ~30-45 min        ~5 min + reboot
   (one time)         (per kernel)      (per target disk)

  ┌────────────┐     ┌────────────┐     ┌────────────┐
  │   STAGE 4  │ →   │   STAGE 5  │ →   │   STAGE 6  │
  │ First boot │     │  Daily use │     │  Evolve OR │
  │ + assistant│     │  + maintain│     │ decommission│
  └────────────┘     └────────────┘     └────────────┘
       │                  │                  │
       v                  v                  v
   ~2 min             ongoing           when needed
   (per fresh install)
```

Each stage is independent — you can re-enter any stage at any time
(rebuild with new flags · re-run install · re-run first-login assistant ·
swap profile in-place · decommission and reinstall).

---

## STAGE 1 — Onboarding + decide (build host, ~10 min, one time per repo clone)

### 1.1 What this stage is for

You sit at your build host (any sufficient Debian 13 / Ubuntu 24.04
machine — not necessarily SAIN-01 hardware yet). You clone the repo,
walk through the 5 mandatory decisions, validate the dev environment,
and run preflight against your chosen profile.

By the end you have:
- `.sovereign-os/init-state.yaml` with your 5 decisions
- A passing preflight (network, storage, TPM2, profile-spec)
- The exact next command printed for you

### 1.2 What you type

```sh
git clone https://github.com/cyberpunk042/sovereign-os
cd sovereign-os
scripts/onboard.sh
```

That single script runs 3 stages internally:

| Stage | What it does | Customize via |
|---|---|---|
| 1/3 setup | git pre-commit hook · python deps · shellcheck · L1 lint smoke | `SOVEREIGN_OS_SETUP_SKIP_HOOKS=1` to skip git hook install |
| 2/3 init | `sovereign-osctl init` — interactive wizard, 5 decisions | `SOVEREIGN_OS_NONINTERACTIVE=1` to accept all defaults |
| 3/3 preflight | `orchestrate.sh preflight` against the chosen profile | `SOVEREIGN_OS_ONBOARD_SKIP_PREFLIGHT=1` for fast re-runs |

### 1.3 The 5 decisions the wizard walks you through

| # | Decision | Master spec link | Default | When to deviate |
|---|---|---|---|---|
| 1 | **Profile** — which hardware archetype | § 1 (sain-01 is the master spec target) | sain-01 | Pick `minimal` for VM testing; `headless` for bare-metal server; `developer` for polyglot dev box; `old-workstation` for constrained dev |
| 2 | **Substrate** — image-build backend | SDD-003 | mkosi | `live-build` only if you specifically need its workflow |
| 3 | **Secure-boot posture** | SDD-015 / § 14 MOK | profile default (`signed` for sain-01 / headless · `shim` for old-workstation/developer · `none` for minimal) | Pick `none` for fast iteration; `signed` requires operator-owned PK/KEK/db keys (see Stage 2.4) |
| 4 | **Disk encryption** | SDD-022 / § 4.1 | profile default (yes for sain-01/headless/old-workstation/developer; no for minimal) | `no` for clear-text rootfs when you control physical access and want CPU back |
| 5 | **Whitelabel** | SDD-007 | default | `fork` to author your own (see Stage 6.3) |

### 1.4 Expected output

```
sovereign-os fresh-machine onboarding
Walks you from clone → ready-to-build in 3 steps.

[1/3] dev-environment setup
...
[2/3] decision wizard
  sovereign-osctl init — operator setup wizard
  ...
  [1/5] PROFILE — which hardware archetype?
  ...
[3/3] build-host preflight (profile=sain-01)
  ...
  ✓ preflight passed

onboarding complete

  NEXT:
    # 1. Validate the pipeline plan without building (always safe)
    SOVEREIGN_OS_PROFILE=sain-01 scripts/build/orchestrate.sh run --dry-run
    ...
```

### 1.5 What to do if it fails

| Failure | Cause | Recovery |
|---|---|---|
| Setup reports missing python deps | Pre-onboard system not provisioned | `apt install python3-yaml python3-jsonschema python3-pip` |
| Preflight fails network check | Mirror unreachable | Check `SOVEREIGN_OS_PREFLIGHT_MIRROR` (default `deb.debian.org`); set `SOVEREIGN_OS_PREFLIGHT_SKIP_HF=1` for air-gapped hosts |
| Preflight fails TPM2 check | Build host has no TPM | Expected — TPM gate only meaningful at install time; preflight WARN, not FAIL |
| Preflight fails friction-audit-spec | Profile YAML has structural issue | Run `sovereign-osctl profiles validate` for line-level errors |

### 1.6 Customization points at this stage

- `profiles/sain-01.yaml` (or your forked profile) — edit before running onboard if you know what you're changing
- `whitelabel/default.yaml` — edit before build to change os-release/motd/issue/grub
- `.env` (gitignored) — define `SOVEREIGN_OS_*` env vars for repeated builds
- `sovereign-osctl env list` — discover all 80+ tunable env vars

---

## STAGE 2 — Build + verify (build host, ~30-45 min for sain-01 kernel; ~5 min for substrate-default profiles)

### 2.1 What this stage is for

The 9-step build pipeline takes the profile + substrate decisions and
produces a bootable disk image + signed kernel + provenance manifest.

By the end you have:
- `build/<profile>/output/<profile>.raw` — the bootable image
- `build/<profile>/output/build-provenance.json` — in-toto SLSA v1 attestation
- `build/<profile>/output/sha256sums.txt` — hash chain
- `~/.sovereign-os/build-state/state.yaml` — resumable progress tracking

### 2.2 Always-run-first: dry-run

Validates the WHOLE plan without writing a byte. Always safe.

```sh
SOVEREIGN_OS_PROFILE=sain-01 scripts/build/orchestrate.sh run --dry-run
```

Expected output: each of the 9 steps reports "would run" + the exact
commands + file paths. No `apt install`, no kernel compile, no `dd`.

### 2.3 The 9 steps (master spec § 12 Phases I-III)

```
01-bootstrap-forge   — install build toolchain · mount /mnt/kernel_forge (64GB tmpfs)
02-kernel-fetch      — shallow-clone kernel.org-stable into the forge; record SHA
03-kernel-config     — apply profile.kernel.config + master spec ENABLE/DISABLE list
04-kernel-compile    — make -j$(nproc) bindeb-pkg with -march=znver5 -O3 + AVX-512 flags
05-substrate-prepare — emit mkosi.conf (or live-build config/) from profile YAML
06-whitelabel-render — apply 7-strategy whitelabel taxonomy (per SDD-007)
07-image-build       — invoke mkosi (or lb build) → bootable .raw
08-image-sign        — apply secure-boot posture (none/shim/signed) per SDD-015
09-image-verify      — QEMU smoke + emit sha256sums.txt + build-provenance.json
```

Each step:
- honors `--dry-run` (prints intent, writes nothing)
- emits Layer B Prometheus metric (`sovereign_os_build_step_<id>_total`)
- writes a JSONL line to `~/.sovereign-os/log/build-<ts>.jsonl`
- tracks state in `state.yaml` (resumable across crashes)
- inputs-hash aware (re-runs only when its inputs change)

### 2.4 Real build (after dry-run reports clean)

Substrate-default profiles (everything except sain-01 by default):

```sh
SOVEREIGN_OS_PROFILE=minimal scripts/build/orchestrate.sh run
```

SAIN-01 (custom kernel; needs root + 30+ minutes):

```sh
SOURCE_DATE_EPOCH=$(date +%s) \
DEBIAN_SNAPSHOT=20260515T000000Z \
SOVEREIGN_OS_PROFILE=sain-01 \
  sudo scripts/build/orchestrate.sh run
```

For `signed` secure-boot posture you also pass operator-owned keys:

```sh
SOVEREIGN_OS_DB_KEY=/path/to/db.key \
SOVEREIGN_OS_DB_CERT=/path/to/db.crt \
SOVEREIGN_OS_PK_KEY=/path/to/PK.key \
SOVEREIGN_OS_PK_CERT=/path/to/PK.crt \
  sudo scripts/build/orchestrate.sh run
```

Don't have those keys yet? Generate them OUTSIDE the repo:

```sh
sovereign-osctl secure-boot gen-keys --out ~/.sovereign-os/secure-boot-keys
# follow the printed enrollment + backup instructions
```

### 2.5 Verify reproducibility

```sh
sovereign-osctl audit provenance --deep build/sain-01/output/build-provenance.json
```

`--deep` triggers the in-toto verifier triangle: it recomputes SHA256 of
every subject file on disk and cross-checks with the manifest digests
AND `sha256sums.txt`. All three must agree.

### 2.6 What to do if it fails

```sh
scripts/build/orchestrate.sh recover
```

Reads the current state.yaml, identifies the failed step + its
`fail_reason`, surfaces the last 5 error/warn JSONL events, and presents
4 ranked next-action options:

| Option | When |
|---|---|
| (a) fix underlying issue + `run` | Most common — pipeline resumes from failed step |
| (b) `rewind <step>` + `run` | Transient/environmental retry, no input changes |
| (c) `skip <step>` + `run` | Step doesn't apply to your profile |
| (d) `reset` + `run` | Start over (DESTRUCTIVE — wipes state) |

For deeper investigation:

```sh
sovereign-osctl journal show <run-stem>    # specific run's events
sovereign-osctl journal errors             # warn+error across all runs
sovereign-osctl history list               # all runs with profile/result/duration
```

### 2.7 Customization points at this stage

- `profiles/<id>.yaml § kernel.config.enable / disable` — add/remove kernel options without forking
- `whitelabel/<id>.yaml` — branding surfaces (os-release · motd · issue · grub theme · plymouth)
- `mixins/` — package additions / hook injections shared across profiles
- env vars: `SOVEREIGN_OS_PARALLEL` (kernel-compile -j), `SOVEREIGN_OS_FORGE_SIZE` (tmpfs), `SOVEREIGN_OS_KERNEL_TAG` (which kernel.org tag), `SOURCE_DATE_EPOCH` (reproducibility pin), `DEBIAN_SNAPSHOT` (deb mirror snapshot)

---

## STAGE 3 — Install + boot (target hardware, ~5 min + reboot)

### 3.1 What this stage is for

You write the built image to the target disk on the SAIN-01 (or other
profile-target) hardware. First-boot runs the lifecycle hooks.

By the end you have:
- A bootable sovereign-os install on the target disk
- ZFS pool created + datasets initialized (for zfs-tiered profiles)
- Secure-boot enrollment in progress (if applicable)

### 3.2 Preview before writing (always do this first)

```sh
sovereign-osctl install image --plan build/sain-01/output/sain-01.raw --to /dev/nvme1n1
```

Shows the device fingerprint (model · serial · size · current mounts) +
the dd command that WOULD run. Writes nothing.

### 3.3 Execute the write (six gates protect you)

```sh
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
  sudo sovereign-osctl install image build/sain-01/output/sain-01.raw --to /dev/nvme1n1
```

The 6 hard gates (any failure = abort):
1. Image file exists + non-empty + regular file
2. Target is a block device
3. Target is a WHOLE DISK (not a partition)
4. Target is **NOT** the currently-mounted root or its parent (HARD REFUSAL)
5. `SOVEREIGN_OS_CONFIRM_DESTROY=YES` env var present
6. Interactive typed-device-path confirmation (skip with `SOVEREIGN_OS_NONINTERACTIVE=1`)

### 3.4 First boot

Power off build host, move the disk (or boot the target with the right
disk inserted), power on. UEFI boots the kernel.

If `secure_boot: signed` and the operator's PK is enrolled in firmware,
the kernel boots directly. If `secure_boot: shim`, you'll see the
shim MOK Manager prompt for one-time MOK enrollment.

During-install hooks (run by the live system if applicable):

```
zfs-pool-create.sh       — tank with ashift=12 lz4
zfs-datasets-create.sh   — tank/models (1M/lz4) · tank/context (16k/zstd-9/copies=2/sync=always) · tank/agents (128k/zstd-3)
rootfs-format-ext4.sh    — for ext4 profiles
mok-enroll.sh            — for shim posture
```

### 3.5 What to do if it fails

| Failure | Cause | Recovery |
|---|---|---|
| `HARD REFUSAL — under repo root` from gen-keys | Target dir was inside repo (rejected to prevent committing keys) | Use `~/.sovereign-os/secure-boot-keys/` or another path outside the repo |
| `install image` exits 1 "running root" | Target was the host's root disk | Pick a different `--to` device |
| MOK enrollment prompts at boot but you don't have keys | You picked `shim` posture without generating keys | Reboot, generate keys, re-run install |
| ZFS pool create fails | Devices not seen by the live system | Boot a Debian live USB, verify `lsblk`, check controller mode (RAID vs AHCI vs NVMe-direct) |

### 3.6 Customization points

- `config/preseed/<profile>.preseed.example.cfg` — netinst preseed for unattended provisioning
- `config/cloud-init/<profile>.user-data.example.yaml` — cloud-init seed
- `SOVEREIGN_OS_WIPE_DEVICES` — for decommission later

---

## STAGE 4 — First boot + assistant (~2 min after install)

### 4.1 What this stage is for

The target hardware boots. Post-install hooks run in order. The
first-login assistant walks the operator through final customization.

By the end you have:
- VFIO 4090 bound (sain-01)
- Network VLANs configured (target → master spec § 8 values after R158)
- Tetragon perimeter active
- Hardening drop-ins applied (auditd/fail2ban/unattended/sshd/pwquality per SDD-024)
- Profile-appropriate first-login choices recorded

### 4.2 Hook order (sain-01)

```
friction-audit-runtime    — confirms PCIe topology (PRO 6000 + 5090 x8/x8, M.2_2 empty, OcuLink 4090 on chipset M.2, SDD-993) · ZFS health · AVX-512 present
vfio-bind-4090            — opt-in only (role: vfio): binds 4090 to vfio-pci (master spec § 4.3); no-op by default
network-vlan-config       — applies asymmetric VLAN (master spec § 8; opinionated per R158)
tetragon-policy-load      — loads sovereign-kernel-fence (master spec § 6)
arc-clamp-128gb           — clamps ZFS ARC to 128GB (master spec § 4.2)
apply-workstation-hardening — 4 drop-ins for sain-01 (auditd/pwquality/unattended/sshd)
first-login-assistant     — interactive (or unattended via NONINTERACTIVE) operator flow
```

### 4.3 The first-login assistant

Shows the operator-verbatim motd:

```
We want quality over quantity and honesty over cheats and lies.
We do not want hacks, quick fixes, and shortcuts.
```

Then prompts (skippable via `SOVEREIGN_OS_NONINTERACTIVE=1`):
- Hostname (default = profile id)
- NVIDIA driver enable (sain-01: yes)
- Pre-pull a default LLM model (deferred to R156 model catalog)
- Tetragon perimeter verify
- Whitelabel surface check

State persists to `/var/lib/sovereign-os/assistant/state.yaml`. Re-run
with `sovereign-osctl assistant full` (force) or `assistant reset`.

### 4.4 What to do if it fails

| Failure | Recovery |
|---|---|
| Friction-audit FAIL on PCIe topology | Power down · confirm PRO 6000 (PCIEX16_1) + RTX 5090 (PCIEX16_2) seat at x8/x8 · confirm **M.2_2 is empty** · confirm the OcuLink-to-M.2 adapter is on a chipset M.2 slot (not M.2_2) · check BIOS bifurcation (SDD-993) |
| VFIO bind FAIL | Check kernel cmdline has `vfio-pci.ids=10de:2684,10de:22ba` · `dmesg` for IOMMU group issues |
| Tetragon FAIL | `systemctl status tetragon` · `journalctl -u tetragon` |
| Hardening apply FAIL on sshd reload | `sshd -t` first — the hook gates reload behind sshd_config validation |

---

## STAGE 5 — Daily use + maintenance (ongoing)

### 5.1 Operator-facing commands (15 verb groups, 30+ subverbs)

| Want to… | Command |
|---|---|
| See a health overview | `sovereign-osctl status` (or `status --json` for fleet aggregation) |
| Run profile-conditioned sanity checks | `sovereign-osctl doctor` |
| See alerts derived from metrics | `sovereign-osctl alerts` |
| Check deployed hardening hasn't drifted | `sovereign-osctl audit drift` |
| Check customization actually landed | `sovereign-osctl audit customization` |
| Inspect Layer B metrics | `sovereign-osctl metrics list` / `metrics show <name>` |
| Read structured logs | `sovereign-osctl journal list` / `journal show <run>` / `journal errors` |
| See historical runs | `sovereign-osctl history list` / `history show <run-id>` |
| Manage models | `sovereign-osctl models list` / `models pull <hf-id>` / `models verify` |
| Restart Tetragon policy | `sovereign-osctl perimeter reload` |
| Inspect provenance | `sovereign-osctl audit provenance --deep` |
| Discover env vars | `sovereign-osctl env list [--filter <regex>]` |
| Compare two profiles | `sovereign-osctl profiles compare <a> <b>` |
| Preview what decommission does | `sovereign-osctl decommission --plan` |

### 5.2 Timer-driven maintenance (master spec § 18 lifecycle)

Per-profile, declared in `profiles/<id>.yaml § hooks.post_install_recurrent`:

| Timer | Cadence | What |
|---|---|---|
| `sovereign-zfs-scrub.timer` | weekly | ZFS scrub on tank |
| `sovereign-log-rotate.timer` | daily | rotate JSONL logs per profile retention |
| `sovereign-backup-snapshot.timer` | daily | tank/context ZFS snapshot |
| `sovereign-security-update-check.timer` | daily | scan for pending security upgrades |
| `sovereign-model-catalog-sync.timer` | daily | verify resident model catalog |
| `sovereign-tetragon-policy-verify.timer` | daily | re-check perimeter policy integrity |
| `sovereign-alerts-check.timer` | hourly | emit meta-counters; persist alerts.json |

### 5.3 What to do if a maintenance task fails

```sh
sovereign-osctl alerts                          # see the rule-derived alert
sovereign-osctl maintenance <subverb>           # run the underlying hook on demand
sovereign-osctl journal errors                  # see the raw event
```

### 5.4 Observability surface (master spec § 22 verification + SDD-016)

- **Layer A** — JSONL logs at `~/.sovereign-os/log/` (build host) or `/var/log/sovereign-os/` (installed). Surfaces: `journal` verb + history verb.
- **Layer B** — Prometheus textfile collector at `/var/lib/node_exporter/textfile_collector/sovereign-os-*.prom`. 56+ metrics. Operators with Grafana import the 3 dashboard templates from `docs/observability/dashboards/`. Operators WITHOUT Grafana use `sovereign-osctl metrics list`.
- **Layer C** — Operator CLI: `status`, `doctor`, `audit`, `alerts`.

---

## STAGE 6 — Evolve OR decommission (when needed)

### 6.1 Add a service (master spec § 5.2 lifecycle-management evolvability)

```sh
# Drop in a systemd unit
sudo cp my-service.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now my-service

# Or — declare it in the profile YAML so it's reproduced on next build
sovereign-osctl profiles fork sain-01 my-host
# edit profiles/my-host.yaml § hooks.post_install_first_boot
sovereign-osctl hooks add post_install_first_boot scripts/hooks/my-hook.sh \
  --id my-service-install --mandatory --profile my-host
```

### 6.2 Swap profile in place

```sh
sudo sovereign-osctl profiles switch my-host
# WARN — kernel changes require rebuild; package changes via apt
sovereign-osctl audit customization        # confirm what landed
```

### 6.3 Author a whitelabel

```sh
cp whitelabel/default.yaml whitelabel/my-brand.yaml
# edit branding/surfaces — the 7-strategy taxonomy
# (see docs/sdd/007-whitelabel-mechanism.md)
sovereign-osctl whitelabel apply my-brand
```

### 6.4 Pull a new model

```sh
sovereign-osctl models pull <huggingface-id>
sovereign-osctl models verify
sovereign-osctl models list
```

### 6.5 Decommission (preview + 3 phases, all gated)

```sh
# 1. Rehearse — shows every destructive op WITHOUT writing
sovereign-osctl decommission --plan

# 2. Phase 1 — shred state-fabric (interactive confirm)
sudo sovereign-osctl decommission start

# 3. Phase 2 — destroy zpool tank (env-gated)
SOVEREIGN_OS_CONFIRM_DESTROY=YES sudo sovereign-osctl decommission pool

# 4. Phase 3 — wipe block devices (env-gated)
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
SOVEREIGN_OS_WIPE_DEVICES='/dev/nvme0n1 /dev/nvme1n1' \
  sudo sovereign-osctl decommission wipe
```

Each phase requires explicit `SOVEREIGN_OS_CONFIRM_DESTROY=YES` AND
an interactive confirm AND completes the previous phase.

---

## Cross-references

| For… | Read |
|---|---|
| What you're building (the Trinity, SAIN-01 hardware spec) | [`sain-01-master-spec.md`](./sain-01-master-spec.md) |
| Per-profile recipes | [`profiles/`](./profiles/) (R148 lands these) |
| SDDs (every architectural decision) | [`docs/sdd/INDEX.md`](../sdd/INDEX.md) |
| Decisions log (audit trail) | [`decisions.md`](./decisions.md) |
| Bug ledger + 5 Learnings | [`tdd/bugs-caught.md`](./tdd/bugs-caught.md) |
| Friction audit history | [`docs/handoff/004-operator-friction-audit.md`](../handoff/004-operator-friction-audit.md) |
