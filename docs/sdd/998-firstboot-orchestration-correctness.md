# SDD-998 — first-boot orchestration correctness: the flashed image must actually run its hooks (F-2026-101..104)

> Status: draft
> Owner: operator-directed 2026-07-14 (*"we need to fix everything before I build and flash like I said … the IaC is ready through and through and will be done properly and in proper timing and sequence?"*); agent-authored.
> Closes: **F-2026-101** (CRIT), **F-2026-102** (HIGH), **F-2026-103** (MED), **F-2026-104** (LOW).
> Mandate module: **E11.M998**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## The directive

The operator asked for a real build-and-flash readiness pass, not doc hygiene:

> "lets redo a massive review, what might be missing before I build and flash sovereign-os. lets be real, I dont want to repeat this loop everyday"

> "we need to fix everything before I build and flash like I said. and everything that needs to be in the sudoer are there too? and the IaC is ready through and through and will be done properly and in proper timing and sequence?"

This SDD is the **first-boot IaC correctness** batch — the ordering/timing/sequence half of that directive. A multi-agent readiness review surfaced four defects in the first-boot path; the top one means the flashed box does **nothing** it was configured to do.

## F-2026-101 (CRIT) — the first-boot target pulls in ZERO members

`systemd/system/sovereign-firstboot.target` is the grouping unit for the 10 first-boot
oneshots (network/VLAN, nvidia-driver-bind, vfio-bind, zfs-arc-clamp, tetragon-policy-load,
warp-setup, ups-setup, workstation-shell-setup, friction-audit, and the completion marker).
Every install path enables **only the target** (`systemctl enable sovereign-firstboot.target`
in the bake + preseed). Each member declared `[Install] WantedBy=sovereign-firstboot.target`
and `PartOf=sovereign-firstboot.target` — but **neither pulls the member in**:

- `systemctl enable <target>` processes the *target's* `[Install]` section, never the
  members' `WantedBy=` (that line only takes effect when you `enable` the member itself).
- `PartOf=` propagates **stop/restart only**, never **start**.

So the target had 10 units declaring membership and **0 reachable**. Enabling it on the image
started an empty target; on first boot **no hook ran** — the flashed SAIN-01 came up as bare
Debian: no VLAN/network, no NVIDIA/VFIO bind, no ZFS ARC clamp, no Tetragon policy. The whole
point of the image — a configured AI workstation — was inert, and the existing
`test_preseed_content_verbatim` stayed green because it only checked the *enable string* was
present, not that first boot did anything.

**Fix**: the target now declares `Wants=` for all 10 members (the start-time dependency that
`enable`-ing the target actually honours). Each member still self-gates via
`ConditionFirstBoot=yes` + `ConditionVirtualization=no`, so this is a no-op on every
subsequent boot and on a VM. Ordering between members stays their own `After=`; the completion
marker `sovereign-firstboot.service` is `After=` all of them.

## F-2026-102 (HIGH) — concurrent first-boot initramfs rebuilds can corrupt the image

Once the target correctly starts its members (F-2026-101), **three** of them regenerate the
initramfs on first boot — `nvidia-driver-bind.sh` (nouveau blacklist), `vfio-bind-4090.sh`
(vfio-pci early-load), `zfs-arc-clamp.sh` (ARC-max module option) — and their only ordering is
`After=sovereign-friction-audit.service`, i.e. **none relative to each other**. systemd starts
`Wants=` units in parallel, so up to three `update-initramfs -u` runs (plus `update-grub`) race
on the same `/boot/initrd.img-*` build dir + atomic rename. Parallel `update-initramfs` is not
safe — a lost race leaves a truncated/half-written initramfs, and the box does not boot.

**Fix**: a shared `boot_regen` helper in `scripts/build/lib/common.sh` funnels every
boot-config regeneration (`update-initramfs`, `update-grub`) through one `flock` on
`/run/lock/sovereign-os-boot-regen.lock`, so they run strictly one-at-a-time regardless of how
systemd schedules the hooks. `flock -w 300` keeps a wedged holder from hanging first boot
forever (it fails the wait, and the caller's existing `|| log_warn` records it); if `flock` is
absent (minimal image), the command runs directly — a missing lock never means a skipped
regeneration. All three hooks now call `boot_regen update-initramfs -u` / `boot_regen
update-grub`.

## F-2026-103 (MED) — the NVIDIA bind emits no reboot signal; the operator gets no console notice

`vfio-bind-4090.sh`'s unit writes `/var/lib/sovereign-os/.vfio-bind-needs-reboot` and the
completion service prints a `/dev/console` notice when it's present. `nvidia-driver-bind.sh`
does the equivalent boot-affecting work (nouveau blacklist + initramfs rebuild — only effective
after a reboot, and nouveau may already be bound this boot so `nvidia-smi` legitimately fails)
but emitted the "may need reboot" warning **only to the journal**, never to the console. On a
headless-ish first boot the operator would see the VFIO notice and reasonably assume NVIDIA was
fully live, then hit a driver that isn't bound until the next reboot.

**Fix**: mirror the VFIO flag — the nvidia unit gains
`ExecStartPost=/bin/touch /var/lib/sovereign-os/.nvidia-bind-needs-reboot`, and the completion
service (`sovereign-firstboot.service`) prints one console notice covering **both** GPU-binding
hooks (iterates `.vfio-bind-needs-reboot` + `.nvidia-bind-needs-reboot`). One reboot after
first boot brings up both GPUs; the operator is told so on the console.

## F-2026-104 (LOW) — guardian-core lacks vault-mount ordering → 226/NAMESPACE if enabled early

`sovereign-guardian-core.service` (the opt-in eBPF supervisor, installed post-deploy via
`scripts/auditor/install.sh` — NOT part of the flashed image, so not a build blocker) runs
`ProtectSystem=strict` with `ReadWritePaths=/mnt/vault/context …` but ordered only
`After=tetragon.service`. `/mnt/vault` is a ZFS dataset; if the daemon starts before the pool
mounts, systemd cannot build the mount namespace for that ReadWritePaths entry → `226/NAMESPACE`,
and with `Restart=always` it crash-loops until the pool appears.

**Fix** (correctness hardening for when the operator enables it): add `After=zfs.target` +
`RequiresMountsFor=/mnt/vault/context` (order after + require the vault mount) and `-`-prefix the
two ReadWritePaths entries so a not-yet-created context/textfile-collector dir is tolerated at
namespace-setup time instead of being a hard failure. `ExecStart=/usr/local/bin/guardian-core`
is **correct and unchanged** — `scripts/auditor/install.sh:59` installs
`scripts/auditor/guardian-core.py` to that path with `install -m 0755`.

## The lint

`tests/lint/test_firstboot_target_membership.py` (4 cases) makes F-2026-101 un-regressable:
the target's `Wants=`/`Upholds=` set must **equal** the set of units declaring
`WantedBy=sovereign-firstboot.target`, in **both** directions (a new hook not wired into the
target, or a target that drops a member, fails CI), plus a floor guard that the
hardware/network/security hooks (network-vlan, nvidia-driver-bind, vfio-bind, zfs-arc-clamp,
tetragon-policy-load) can never quietly fall out of the target.

## Verification (real, observed)

- `python3 -m pytest tests/lint/test_firstboot_target_membership.py` → **4 passed**.
- `python3 -m pytest tests/lint/ -k "systemd or firstboot or hook or unit or defense or shell"`
  → **1008 passed, 1 skipped** (the per-unit systemd coverage + defense-in-depth + hook-hygiene
  + shell-safety lints all green with the edited units + the new `boot_regen` helper).

## Scope / safety

`systemd/system/sovereign-firstboot.target` (+`Wants=`),
`sovereign-nvidia-driver-bind.service` (+ reboot-marker `ExecStartPost`),
`sovereign-firstboot.service` (two-marker console notice),
`sovereign-guardian-core.service` (mount ordering + `-`-prefixed RWP);
`scripts/build/lib/common.sh` (new `boot_regen` helper) + the three first-boot hooks routed
through it; new `tests/lint/test_firstboot_target_membership.py`; this SDD + registries. No
Rust crate, no gatewayd/cockpit/webapp change; no new dependency; the guardian ExecStart is
untouched. Every change is idempotent + `ConditionFirstBoot`-gated where it runs on the box.
Collision-safe. MS003 `unsigned-pending-MS003`.

## Non-goals

- The rest of the build-and-flash readiness batches (GPU driver install ≥570/CUDA, GPU
  power-limit apply-at-boot, inference runtime + model provisioning, sudoers OPS-bucket
  coverage lint, daemon auth/TLS) — tracked as their own SDDs; this SDD is the first-boot
  ordering/sequence correctness the operator asked about first.
- Wiring the opt-in guardian/tetragon stack into the flashed image (it stays a deliberate
  post-deploy install).
- Reworking `PartOf=`/`After=` graph beyond what's needed to make the members start.

## Cross-references

- `systemd/system/sovereign-firstboot.target` — the `Wants=` that makes members start
- `tests/lint/test_firstboot_target_membership.py` — the membership ⇔ WantedBy lint
- `scripts/build/lib/common.sh` — `boot_regen` (flock-serialized initramfs/grub regen)
- `systemd/system/sovereign-firstboot.service` — two-marker reboot console notice
- `systemd/system/sovereign-guardian-core.service` — vault-mount ordering hardening
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-101..104 (closed here)
