# Standing directive — sovereign-os is INSTALLED onto the NVMe (installer, not just an image)

**Status**: ACTIVE (operator directive, 2026-07-25, verbatim — logged during the work)
**Audience**: every session touching the build/flash/install path, SDD-013, the
reflash-root scripts (`scripts/install/*`), the build panel, or the flash panel

## Verbatim operator statements (sacrosanct — do not paraphrase)

On discovering the flashed mkosi image was a headless appliance:

> "its as if the build is building a bootable OS... and there is nothing of what I asked on it... no KDE plasma... i thought it was supposed to be a custom Debian 13 install"

> "I just did it, booted on the sovereign-os and it was nothing like expected..."

The core requirement:

> "it needs to be an installer, otherwise how will I install my OS on my nvme?"

The flash-time choice:

> "let me chose between flashing the OS and flashing the installer, I want installer by default"

Design decisions (operator selections, same session):
- What lands on the NVMe: **a mutable Debian in the `sovereign-root` LV** (not the
  whole-disk appliance) — apt works, KDE, toggleable modules, `/home` preserved.
- Delivery form: **both** — a from-host install verb AND a bootable installer USB.

## What this directive establishes

1. **The deployment model is install-onto-the-NVMe, not dd-the-appliance.** The
   primary target is a MUTABLE Debian 13 (+ custom znver5 kernel + KDE) installed
   into the `sovereign-root` LV, keeping `sovereign-home` as `/home` (the 2026-06-10
   reflash-root model). The immutable mkosi whole-disk image is now the SECONDARY
   "appliance" artifact.
2. **Two install surfaces ship:** (a) `sovereign-osctl install system --to <disk>`
   installs from the running host; (b) a bootable **installer USB** (live-build ISO,
   `SOVEREIGN_OS_ARTIFACT=installer`) boots on a machine and installs onto the
   internal NVMe. The reflash-root trio (`scripts/install/{setup-lvm-dualboot,
   migrate-home,install-sovereign-root}.sh`) is the shared engine.
3. **The flash panel defaults to the installer** (🖴 INSTALLER vs 💿 OS image), and
   the build panel has a "build INSTALLER" toggle.
4. **A requested desktop must never silently vanish.** `provision-bake.sh` now FAILS
   the build when `bake.gui=1` and the desktop install fails (was swallowed by a
   `| sed` pipe masking the exit code).

## Supersedes / reconciles

- **SDD-013** ("image-only, no installer UI") is amended by this directive — see the
  2026-07-25 amendment block at the top of `docs/sdd/013-installer-experience.md`.
  Image-only-dd remains a supported path for the appliance; it is no longer the
  ONLY path, and a guided installer (TUI) is now explicitly wanted.

## Cross-references

- Verb + engine: `scripts/sovereign-osctl` (`install system`),
  `scripts/install/{setup-lvm-dualboot,migrate-home,install-sovereign-root,installer-tui}.sh`
- Installer build: `scripts/build/adapters/live-build-emit.sh`,
  `scripts/build/{orchestrate,05-substrate-prepare,07-image-build}.sh`
- Flash/build panels: `scripts/operator/flash-api.py`, `webapp/flash/index.html`,
  `scripts/operator/build-configurator-api.py`, `webapp/build-configurator/index.html`
