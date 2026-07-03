---
name: single-os-pivot
description: "2026-06-10: dual-boot idea DROPPED — test everything on the running Debian 13 GUI host; LVM + shared /home kept; sovereign-root LV idle (potential nspawn/qemu test target)"
metadata: 
  node_type: memory
  type: project
  originSessionId: acc85078-f2fe-4d01-8f1c-ef8d2e8fb04d
---

2026-06-10: Operator dropped the dual-boot plan after trying the install
scripts — reboot showed only the classic Debian GUI entry (the Sovereign-OS
EFI entry never registered in NVRAM; only `Boot0000* debian` exists). Decision:
keep the GUI, develop and test sovereign-os ON the running Debian 13 host
([[first-image-build-status]] — host IS SAIN-01). Reinstall later, maybe.

What stays (live, working):
- LVM on nvme1n1p2 (VG `sovereign`): `sovereign-home` (1.4T) IS the current
  /home, mounted via the fstab line migrate-home.sh appended (backup at
  /etc/fstab.pre-sovereign.bak). Do NOT touch this LV.

Inert leftovers (no host impact, cleanup optional):
- `sovereign-root` LV (100G ext4, full install inside) — unmounted. Candidate
  test target: deploy built images into it and boot via systemd-nspawn or
  qemu instead of dual-booting.
- `SOV-ESP` nvme1n1p1 (1G vfat) — unmounted, nothing boots from it.
- USB key sda (14.4G DataTraveler) still carries the first built image.

Host dev-env state (2026-06-10): pytest installed via pip --user
--break-system-packages (host has no python3-pytest/venv/pip and sudo needs
a password Claude can't enter). Full suite green on the host: L1 4662,
L2 169, L3-fast, validate-profiles 5/5, orchestrator dry-run 9/9. The 8
red L1 tests left after the first build were reconciled: verbatim tests
now pin the revised KCFLAGS (vector-ISA opt-out)/4090/no-fp16 reality,
schema allows gpu audio_fn+tdp_watts, selfdef-sync hook fully registered
(15-hook contract, timer/service units, metrics inventoried + 3 alerts +
runbook). Host lacks cargo/node — rustup per-user install is the no-sudo
path for `make bins`.

2026-06-11/12: FIRST RECURRENT HOOK LIVE ON HOST. sovereign-osctl installed
(/usr/local), /opt/sovereign-os → repo symlink, selfdef-sync + log-rotate
timers enabled; selfdef-sync ran green end-to-end (reported 4 behind,
metrics .prom written, StateDirectory created /var/lib/sovereign-os).
Three first-bring-up bug classes fixed IN-REPO (each was a real layer, fixed
for all future hosts):
1. installed-layout root: common.sh derived repo root 3-up → /usr on
   installed copies; now honors pre-set SOVEREIGN_OS_ROOT + auto-detects.
2. bare ReadWritePaths → 226/NAMESPACE when dir missing; all 15 hook units
   now use StateDirectory=sovereign-os / LogsDirectory + '-' prefixes.
3. root-vs-owner git "dubious ownership" in selfdef-sync; hook exports
   process-scoped GIT_CONFIG safe.directory (proven via
   GIT_TEST_ASSUME_DIFFERENT_OWNER repro).
Host drop-in: sovereign-selfdef-sync.service.d/host.conf points
SOVEREIGN_OS_SELFDEF_DIR at /home/jfortin/selfdef.
Configurator now has host mode (live ✓/✗ badges vs /host.json), Run console
(dry-run/preflight execute; BUILD via pkexec or sudo-started panel),
/panels index (37), design grammar in webapp/_shared/design-grammar.md,
make panel launcher, runbook docs/src/ops/run-on-host.md (⚡ YOU RUN
convention). doctor fixed (was silently dying) — now the honest gap meter:
missing zfs/nvidia/tetragon/podman/networkd/tank = the hardware-layer backlog.
STILL UNCOMMITTED: ~6 sessions of work. Next: commit checkpoint, then
cockpit-API bring-up (flip panels snapshot→live).

2026-06-12 BOOT-PROVEN: with console=ttyS0 the smoke test reached
'localhost login:' — markers PASS, pipeline green. The [FAILED] units in
the smoke boot are EXPECTED (readonly=on artifact protection + no GPU in
qemu). Real finding: image greeted 'Debian GNU/Linux 13' not 'Sovereign
OS' — whitelabel identity files were in mkosi.skeleton (pre-install,
base-files stomps them); fixed → mkosi.extra (post-install), and step 06
hash now covers render.py (same stale-skip class as step 05). Next build
bakes the branding. NEXT: boot for real (nspawn into sovereign-root LV /
USB hardware boot), cockpit D-NN APIs, selfdefd.

2026-06-12 FINAL: FULL 9-STEP PIPELINE GREEN FROM THE BUILD BUTTON
(✓ exit code 0; qemu smoke saw BdsDxe hand off to the disk's boot entry;
deep provenance audit: all 5 artifacts match SLSA manifest digests,
snapshot 20260515T000000Z recorded). audit provenance now accepts the
artifacts dir. Next candidates: console=ttyS0 in profile cmdline_base
(make smoke markers meaningful), boot sain-01.raw for real (nspawn into
idle sovereign-root LV or USB), continue cockpit D-NN APIs, selfdefd.

2026-06-12 (continued): FIRST IMAGE BUILT FROM THE BUILDER PAGE. Run-console
BUILD chain debugged across 5 layers, each fixed in-repo: MOK env injection
→ snapshot pass-through → unconditional non-free/contrib Repositories in
mkosi-emit → step-05 input hash covering adapter+env (stale-config resume
bug) → step-09 OVMF pflash pair + -cpu host/max (split CODE to -bios was
the 2026-06-10 'false negative' note). Artifacts: build/sain-01/output/
sain-01.raw (8.5G, signed UKI debian-6.12.0.efi verified ×3 EFI binaries
against operator MOK by step 08). Step 09 boots 75s+ stable under TCG
(verified by Claude against the real image). Follow-up noted: profile
cmdline lacks console=ttyS0 so qemu marker check warns-only.

2026-07-02: ONE-COMMAND HOST BOOTSTRAP. scripts/install/bootstrap-host.sh
(make bootstrap) — the operator refuses manual steps. Root cause of the
recurring 'zfsutils-linux has no installation candidate': stock Debian
ships apt component 'main' only; zfs userland is in contrib, nvidia in
non-free. bootstrap-host.sh: enables contrib/non-free/non-free-firmware
(format-aware, Debian mirrors only, never touches 3rd-party like the
Microsoft vscode.sources, backs up first) → apt update → installs full
build-host toolchain (kernel forge + mkosi + dosfstools + sbsigntool +
qemu-system-x86 + ovmf + zfsutils-linux) → operator-deps overlay.
Self-sudo, idempotent, --dry-run. Fresh checkout on this host needs ONLY
this + then preflight/build are green (host already had toolchain from
prior builds; only zfsutils-linux + contrib were missing). preflight-
storage remediation now points here (old remediation was itself the
broken bare-apt line).

**Why:** single-OS GUI workflow gives a faster test loop than reboot-cycling.
**How to apply:** target the running host for service/component testing; don't
propose dual-boot or bare-metal-install steps unless the operator re-opens it.
