#!/usr/bin/env bash
# scripts/build/adapters/mkosi-emit.sh — emit mkosi config from
# sovereign-os profile YAML.
#
# Usage: mkosi-emit.sh <profile.yaml> <output-dir>
#
# Produces under <output-dir>:
#   mkosi.conf                  — top-level config
#   mkosi.conf.d/<profile>.conf — profile-specific override
#   mkosi.skeleton/             — empty (whitelabel renders into here later)
#   mkosi.extra/                — empty (whitelabel renders into here later)
#   mkosi.repart/               — partition table for ZFS-tiered layout

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
. "${__SCRIPT_DIR}/../lib/common.sh"

profile_yaml="${1:?usage: mkosi-emit.sh <profile.yaml> <out-dir>}"
out_dir="${2:?usage: mkosi-emit.sh <profile.yaml> <out-dir>}"

require_file "${profile_yaml}"
mkdir -p "${out_dir}"/{mkosi.conf.d,mkosi.skeleton,mkosi.extra,mkosi.repart}

# Use python to translate YAML → mkosi .conf (INI-style)
SOVEREIGN_OS_PROFILE_FILE="${profile_yaml}" python3 - "${out_dir}" <<'PY'
import os, sys, yaml, pathlib, textwrap

out_dir = pathlib.Path(sys.argv[1])
with open(os.environ["SOVEREIGN_OS_PROFILE_FILE"]) as f:
    p = yaml.safe_load(f)

profile_id = p["identity"]["id"]

# Reproducibility inputs (SDD-019). When operator pins SOURCE_DATE_EPOCH
# and/or DEBIAN_SNAPSHOT in the environment, propagate them into the
# emitted mkosi.conf. Both are optional — sovereign-os doesn't force them.
source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH", "")
debian_snapshot = os.environ.get("DEBIAN_SNAPSHOT", "")

# Build-time baking knobs (operator "ready after flash"). Off by default —
# a lean image. When set, the postinst bakes the operator's dev tools /
# selfdef INTO the image so a flashed box is self-contained.
bake_dev_tools = bool(os.environ.get("SOVEREIGN_OS_BAKE_DEV_TOOLS"))
bake_selfdef = bool(os.environ.get("SOVEREIGN_OS_BAKE_SELFDEF"))
node_major = os.environ.get("SOVEREIGN_OS_NODE_MAJOR", "22")

# Build distribution repository block. The component list is
# UNCONDITIONAL: main alone strands the GPU/ZFS stack — nvidia-* live in
# non-free, zfs* in contrib (caught by the first real image build
# 2026-06-10, then AGAIN by the first Run-console build 2026-06-12,
# which sets no DEBIAN_SNAPSHOT and so skipped this whole block when it
# was snapshot-conditional). Only the Mirror pin depends on the snapshot.
repos_lines = [
    "[Distribution]",
    "Repositories=main contrib non-free non-free-firmware",
]
if debian_snapshot:
    repos_lines.append(
        f"Mirror=http://snapshot.debian.org/archive/debian/{debian_snapshot}")
repos_block = "\n" + "\n".join(repos_lines) + "\n"

env_block = ""
if source_date_epoch:
    env_block = textwrap.dedent(f"""
        [Build]
        Environment=
            SOURCE_DATE_EPOCH={source_date_epoch}
        """)

# ---- secure boot (SDD-015: operator keys NEVER in the repo) ----
# Posture comes from the profile (kernel.secure_boot); keys come from the
# environment, same contract as 08-image-sign.sh: PK pair preferred,
# MOK pair fallback. mkosi ≥ 24 wants these in [Validation], not [Content]
# (caught by the first real build, 2026-06-10).
# Canonical posture path is kernel.cmdline.secure_boot (schema + SDD-015,
# same read as 08-image-sign.sh's profile_field). 'disabled' is the legacy
# alias for 'none'.
_kernel = p.get("kernel") or {}
secure_boot = (_kernel.get("cmdline") or {}).get("secure_boot") or _kernel.get("secure_boot") or "none"
sb_key = os.environ.get("SOVEREIGN_OS_PK_KEY") or os.environ.get("SOVEREIGN_OS_MOK_KEY") or ""
sb_cert = os.environ.get("SOVEREIGN_OS_PK_CERT") or os.environ.get("SOVEREIGN_OS_MOK_CERT") or ""

validation_block = ""
if secure_boot not in ("none", "disabled"):
    if not (sb_key and sb_cert):
        sys.exit(
            f"mkosi-emit: profile posture secure_boot={secure_boot} needs operator\n"
            "keys, but neither SOVEREIGN_OS_PK_KEY/SOVEREIGN_OS_PK_CERT nor\n"
            "SOVEREIGN_OS_MOK_KEY/SOVEREIGN_OS_MOK_CERT is set in the environment.\n"
            "Operator keys are NEVER stored in the repo (SDD-015). Generate once:\n"
            "  sudo mkdir -p /etc/sovereign-os/keys\n"
            "  sudo openssl req -new -x509 -newkey rsa:4096 -nodes -days 3650 \\\n"
            "    -subj '/CN=sovereign-os operator MOK/' \\\n"
            "    -keyout /etc/sovereign-os/keys/mok.key -out /etc/sovereign-os/keys/mok.crt\n"
            "  sudo chmod 600 /etc/sovereign-os/keys/mok.key\n"
            "then add to the build invocation:\n"
            "  SOVEREIGN_OS_MOK_KEY=/etc/sovereign-os/keys/mok.key \\\n"
            "  SOVEREIGN_OS_MOK_CERT=/etc/sovereign-os/keys/mok.crt\n"
            "(or set the profile's kernel.secure_boot to 'disabled').")
    for path, what in ((sb_key, "key"), (sb_cert, "certificate")):
        if not pathlib.Path(path).is_file():
            sys.exit(f"mkosi-emit: secure-boot {what} not found: {path}")
    validation_block = textwrap.dedent(f"""
        [Validation]
        SecureBoot=yes
        SecureBootKey={sb_key}
        SecureBootCertificate={sb_cert}
        """)

# ---- operator login credential ----
# mkosi locks root unless told otherwise — an image without this boots to
# a login prompt that can never accept anyone (proven by VM screenshot,
# first boot validation 2026-06-10). The credential comes from the
# environment, never the repo. first-login-assistant rotates it.
root_password = os.environ.get("SOVEREIGN_OS_ROOT_PASSWORD", "")
root_pw_block = ""
if root_password:
    root_pw_block = f"RootPassword={root_password}\n"
else:
    print("mkosi-emit: WARNING — SOVEREIGN_OS_ROOT_PASSWORD unset: root will be "
          "LOCKED in the image (console login impossible)", file=sys.stderr)

# ---- top-level mkosi.conf (distro-agnostic baseline) ----
top = textwrap.dedent(f"""\
    # auto-generated from profiles/{profile_id}.yaml
    # via scripts/build/adapters/mkosi-emit.sh
    [Distribution]
    Distribution=debian
    Release=trixie

    [Output]
    Format=disk
    OutputDirectory=output
    Output={profile_id}

    [Content]
    Bootable=yes
    Bootloader=systemd-boot
    {root_pw_block}    # Explicit: mkosi must assemble the UKI itself and install it into the
    # ESP (EFI/Linux/). The kernel arrives via postinst with
    # KERNEL_INSTALL_BYPASS=1 (no ESP in the chroot), which also bypasses
    # boot-entry generation — without this the ESP shipped with an EMPTY
    # EFI/Linux and no bootable kernel (caught by 08's verify, 2026-06-10).
    UnifiedKernelImages=yes
    """) + validation_block + repos_block + env_block
(out_dir / "mkosi.conf").write_text(top)

# ---- profile-specific override ----
base_packages = (p.get("packages") or {}).get("base") or []
profile_packages = (p.get("packages") or {}).get("profile") or []
all_packages = base_packages + profile_packages

# Filter out kernel-image package since mkosi handles bootable kernel separately
# (the compiled .debs are staged into mkosi.extra/var/cache/local-debs by
# step 07 and INSTALLED by the mkosi.postinst.chroot emitted below)
all_packages = [pkg for pkg in all_packages if not pkg.startswith("linux-image-") and not pkg.startswith("linux-headers-")]

# Bootloader=systemd-boot needs the EFI binaries INSIDE the image
# (bootctl --install-source=image reads /usr/lib/systemd/boot/efi).
# Debian splits them out of systemd into systemd-boot — without it the
# build dies at 'Failed to open boot loader directory' (first real image
# build, 2026-06-10).
if "systemd-boot" not in all_packages:
    all_packages.append("systemd-boot")
# systemd-boot Depends on 'systemd-boot-efi-signed | systemd-boot-efi' and
# apt picks the FIRST alternative — a package that ships ONLY the
# Debian-presigned systemd-bootx64.efi.signed: no linuxx64.efi.stub (UKI
# build dies with 'systemd-stub not found') and no unsigned binaries for
# mkosi to sign with the OPERATOR key. Pull the real package explicitly;
# the postinst below then strips the Debian-signed shadow copies.
# (Single root cause of two failures on the first signed image, 2026-06-10.)
if "systemd-boot-efi" not in all_packages:
    all_packages.append("systemd-boot-efi")

# DKMS module builds (nvidia/zfs) happen INSIDE the image against the
# custom kernel — they need a real toolchain there. mkosi installs with
# Install-Recommends=false, so nothing pulls it implicitly: without
# build-essential both dkms builds die at 'no acceptable C compiler
# found in $PATH' (first real image build, 2026-06-10). trixie's
# default gcc (14.2) matches the kernel-forge gcc-14 exactly, so
# NVIDIA's CC-version check passes without IGNORE_CC_MISMATCH.
# DEBUG_INFO_BTF_MODULES=y additionally makes every module build invoke
# pahole; bc is the classic kernel-scripts straggler.
if any(pkg.endswith("-dkms") for pkg in all_packages):
    for tool in ("build-essential", "pahole", "bc"):
        if tool not in all_packages:
            all_packages.append(tool)

# Bake-time package prerequisites. selfdef is Rust → needs cargo IN the
# image to build at postinst; dev-tools need curl for the NodeSource setup.
if bake_selfdef:
    for tool in ("cargo", "rustc", "git", "pkg-config", "libssl-dev"):
        if tool not in all_packages:
            all_packages.append(tool)
if bake_dev_tools:
    for tool in ("curl", "ca-certificates"):
        if tool not in all_packages:
            all_packages.append(tool)

cfg = textwrap.dedent(f"""\
    # auto-generated profile-specific config for {profile_id}
    [Distribution]
    Distribution=debian
    Release=trixie

    [Content]
    Packages=
    """)
for pkg in all_packages:
    cfg += f"    {pkg}\n"

# Add kernel command line from profile
cmdline_base = ((p.get("kernel") or {}).get("cmdline") or {}).get("base") or []
cmdline_vfio = ((p.get("kernel") or {}).get("cmdline") or {}).get("vfio") or []
cmdline = " ".join(cmdline_base + cmdline_vfio)
if cmdline:
    cfg += f"\nKernelCommandLine={cmdline}\n"

# Deny list — sovereignty-required (no phone-home / telemetry: snapd, apport,
# whoopsie, popularity-contest, ubuntu-advantage, …). NOT emitted as
# mkosi RemovePackages= — that runs apt purge, which hard-errors on names
# absent from the distro archive (whoopsie/motd-news-config/
# ubuntu-advantage-tools are Ubuntu-only; killed the first real Debian
# image build, 2026-06-10). Enforced instead in mkosi.postinst.chroot as
# purge-if-present via dpkg, which is distro-agnostic and still catches a
# denied daemon pulled in as a transitive dependency.
deny = (p.get("packages") or {}).get("deny") or []

(out_dir / "mkosi.conf.d" / f"{profile_id}.conf").write_text(cfg)

# ---- mkosi.postinst.chroot: install the staged custom-kernel .debs ----
# Step 07 stages the compiled znver5 kernel .debs into
# mkosi.extra/var/cache/local-debs — but copying files into the image
# does NOT install them. Without this postinst the image shipped with
# the custom kernel inert in /var/cache and DKMS skipped every module
# build ('No kernel headers were found') — caught by the first real
# image build, 2026-06-10. Installing headers+image here also triggers
# the dkms autoinstall for nvidia/zfs against the custom kernel.
# deny-list enforcement appended below the kernel install (plain-string
# composition — the bash body is full of ${...} that an f-string would eat)
deny_block = ""
if deny:
    deny_block = textwrap.dedent("""\

        # deny-list enforcement (sovereignty: no phone-home / telemetry).
        # purge-if-present via dpkg: distro-agnostic, tolerates names the
        # archive has never heard of (Ubuntu-only packages on Debian).
        for pkg in %s; do
            if dpkg -s "$pkg" >/dev/null 2>&1; then
                echo "postinst: purging deny-listed package: $pkg" >&2
                dpkg --purge --force-depends "$pkg"
            fi
        done
        """) % " ".join(deny)

# ---- bake blocks (operator "ready after flash", build-time knobs) ----
# Appended to the postinst AFTER the critical kernel install + deny purge.
# FAILURE-TOLERANT by design: the postinst runs `set -uo pipefail` (no -e),
# and every step here ends in `|| echo ...(non-fatal)` so a dev-tool hiccup
# never bricks the image build (unlike the kernel install, which exits 1).
# apt + network are available at postinst (before mkosi's finalize strips
# dpkg), so NodeSource + npm + cargo work here.
bake_block = ""
if bake_dev_tools:
    bake_block += textwrap.dedent("""\

        # ---- dev tools (SOVEREIGN_OS_BAKE_DEV_TOOLS): Claude Code on node >=%(nn)s ----
        echo "postinst: baking dev tools (node %(nn)s + claude-code)" >&2
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL "https://deb.nodesource.com/setup_%(nn)s.x" | bash - \\
                2>&1 || echo "postinst: NodeSource setup failed (non-fatal)" >&2
            apt-get install -y nodejs 2>&1 || echo "postinst: nodejs install failed (non-fatal)" >&2
            command -v npm >/dev/null 2>&1 && { npm install -g @anthropic-ai/claude-code \\
                2>&1 || echo "postinst: claude-code install failed (non-fatal)" >&2; }
        else
            echo "postinst: curl missing — dev-tools bake skipped (non-fatal)" >&2
        fi
        """) % {"nn": node_major}
if bake_selfdef:
    bake_block += textwrap.dedent("""\

        # ---- selfdef (SOVEREIGN_OS_BAKE_SELFDEF): build + install its units ----
        # Source staged into /opt/selfdef by step 07. Build here so the flashed
        # image ships selfdef ready to enable (no manual compile). Non-fatal.
        if [ -d /opt/selfdef ] && command -v cargo >/dev/null 2>&1; then
            echo "postinst: building selfdef in /opt/selfdef" >&2
            ( cd /opt/selfdef && make build ) 2>&1 \\
                || echo "postinst: selfdef build failed (non-fatal)" >&2
            for u in /opt/selfdef/packaging/systemd/*.service /opt/selfdef/packaging/systemd/*.timer; do
                [ -f "$u" ] && install -m 644 "$u" /etc/systemd/system/ 2>/dev/null || true
            done
            echo "postinst: selfdef units installed — enable via 'sovereign-osctl selfdef on'" >&2
        else
            echo "postinst: selfdef not staged or cargo absent — bake skipped (non-fatal)" >&2
        fi
        """)

postinst = out_dir / "mkosi.postinst.chroot"
postinst.write_text(textwrap.dedent("""\
    #!/bin/bash
    # auto-generated by mkosi-emit.sh — runs INSIDE the image after
    # package installation + extra-tree copy, before UKI/bootloader.
    set -uo pipefail
    shopt -s nullglob

    # mkosi assembles the UKI/bootloader itself and the chroot has no
    # ESP — bypass the kernel-install/systemd-boot postinst hooks that
    # otherwise die with 'Couldn't find EFI system partition'.
    export KERNEL_INSTALL_BYPASS=1

    # Operator-only secure-boot chain: drop the DISTRO-presigned
    # systemd-boot binaries ('Debian Secure Boot CA') — bootctl prefers
    # *.efi.signed, but the firmware db enrolls ONLY the operator cert,
    # so Debian's signature would be rejected at boot. With these gone,
    # mkosi signs the unsigned binaries with the operator key instead
    # (caught by 08's sbverify on the first signed image, 2026-06-10).
    rm -f /usr/lib/systemd/boot/efi/*.efi.signed

    debs=()
    for d in /var/cache/local-debs/*.deb; do
        case "$d" in *-dbg_*) continue ;; esac   # 984M debug deb stays out
        debs+=("$d")
    done
    if [ ${#debs[@]} -eq 0 ]; then
        # no early exit — the deny-list purge below must still run
        echo "postinst: no staged local debs (substrate-default kernel)" >&2
    else
        echo "postinst: installing ${#debs[@]} staged kernel .deb(s)" >&2
        # No apt fallback: the image intentionally ships without apt-get at
        # this stage; dpkg -i over the full set resolves inter-deb deps.
        if ! dpkg -i "${debs[@]}"; then
            echo "postinst: dpkg failed — dumping DKMS logs for diagnosis" >&2
            for log in /var/lib/dkms/*/*/build/make.log; do
                echo "───── ${log} (last 60 lines) ─────" >&2
                tail -n 60 "$log" >&2 || true
            done
            exit 1
        fi
    fi
    """) + deny_block + bake_block)
postinst.chmod(0o755)

# ---- kernel.modules.load_at_boot → /etc/modules-load.d/ (mkosi.extra overlay) ----
# The profile declares which modules must load at boot (zfs / nvidia / vfio_pci),
# but nothing wrote them to systemd's modules-load.d, so it relied entirely on
# implicit load paths (initramfs / udev / softdep). Emit the canonical config so
# the declared policy is actually enforced.
load_at_boot = ((p.get("kernel") or {}).get("modules") or {}).get("load_at_boot") or []
if load_at_boot:
    mld = out_dir / "mkosi.extra" / "etc" / "modules-load.d"
    mld.mkdir(parents=True, exist_ok=True)
    (mld / "sovereign-os.conf").write_text(
        f"# kernel.modules.load_at_boot (profile {profile_id})\n"
        + "\n".join(load_at_boot) + "\n"
    )

# ---- mkosi.repart for ZFS-tiered storage ----
# mkosi handles partitioning declaratively via mkosi.repart/*.conf files.
# For zfs-tiered, we lay out: ESP (FAT32) + root pool partition (zfs).
storage_layout = ((p.get("hardware") or {}).get("storage") or {}).get("layout")
if storage_layout == "zfs-tiered":
    (out_dir / "mkosi.repart" / "00-esp.conf").write_text(textwrap.dedent("""\
        [Partition]
        Type=esp
        Format=vfat
        # The ESP must CARRY the boot trees — without CopyFiles= repart
        # formats an EMPTY vfat and the signed systemd-boot + UKI end up
        # unreachable inside the root partition ('no EFI binaries found
        # inside the image ESP', first real image build 2026-06-10).
        CopyFiles=/efi:/
        CopyFiles=/boot:/
        SizeMinBytes=512M
        SizeMaxBytes=1G
        """))
    (out_dir / "mkosi.repart" / "10-root-zfs.conf").write_text(textwrap.dedent("""\
        [Partition]
        Type=root
        # Root is ext4 BY DESIGN, not a placeholder: systemd-repart cannot
        # create ZFS (there is no mkfs.zfs — pools come from zpool create),
        # and Format=none produced an unbootable image with an empty root
        # ('mkfs binary for none is not available', first real image build
        # 2026-06-10). The zfs-tiered layout lives in the TANK DATA POOL
        # (tank/models, tank/context, tank/agents), created on the target
        # at install time by scripts/hooks/during-install/zfs-pool-create.sh
        # — not inside this image.
        Format=ext4
        # Populate the partition from the built rootfs — without CopyFiles
        # the root would be formatted but EMPTY. /boot and /efi CONTENTS are
        # excluded (trailing slash = keep the dirs as mountpoints): they
        # belong to the ESP partition above, and CopyFiles=/ would otherwise
        # duplicate them into the root.
        CopyFiles=/
        ExcludeFiles=/boot/
        ExcludeFiles=/efi/
        # 8G floor (content is ~2G): a '16GB' USB key is only ~14.9 GiB, so a
        # 16G root made the image unwritable to the operator's install media.
        # On the target NVMe the partition grows at install time.
        SizeMinBytes=8G
        """))
else:
    # Default: single root partition (ext4)
    (out_dir / "mkosi.repart" / "00-esp.conf").write_text(textwrap.dedent("""\
        [Partition]
        Type=esp
        Format=vfat
        # The ESP must CARRY the boot trees — without CopyFiles= repart
        # formats an EMPTY vfat and the signed systemd-boot + UKI end up
        # unreachable inside the root partition ('no EFI binaries found
        # inside the image ESP', first real image build 2026-06-10).
        CopyFiles=/efi:/
        CopyFiles=/boot:/
        SizeMinBytes=512M
        SizeMaxBytes=1G
        """))
    (out_dir / "mkosi.repart" / "10-root.conf").write_text(textwrap.dedent("""\
        [Partition]
        Type=root
        Format=ext4
        SizeMinBytes=16G
        """))

print(f"mkosi config emitted to {out_dir}")
PY

log_info "mkosi config emitted to ${out_dir}"
log_info "  files:"
find "${out_dir}" -maxdepth 3 -type f | while read -r f; do
  log_info "    ${f}"
done
