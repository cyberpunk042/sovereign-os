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
    SecureBoot=yes
    """)
(out_dir / "mkosi.conf").write_text(top)

# ---- profile-specific override ----
base_packages = (p.get("packages") or {}).get("base") or []
profile_packages = (p.get("packages") or {}).get("profile") or []
all_packages = base_packages + profile_packages

# Filter out kernel-image package since mkosi handles bootable kernel separately
# (CONFIG_LOCALVERSION variant flows in via mkosi.extra/ copy of compiled .deb)
all_packages = [pkg for pkg in all_packages if not pkg.startswith("linux-image-") and not pkg.startswith("linux-headers-")]

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

# Deny list — mkosi has its own deny mechanism via 'RemoveFiles=' or
# we just don't include them in Packages=. For phone-home daemons,
# explicit deny via package mask:
deny = (p.get("packages") or {}).get("deny") or []
if deny:
    cfg += "\n# deny-list (sovereignty-required; never installed)\n"
    for pkg in deny:
        cfg += f"# explicitly NOT installed: {pkg}\n"

(out_dir / "mkosi.conf.d" / f"{profile_id}.conf").write_text(cfg)

# ---- mkosi.repart for ZFS-tiered storage ----
# mkosi handles partitioning declaratively via mkosi.repart/*.conf files.
# For zfs-tiered, we lay out: ESP (FAT32) + root pool partition (zfs).
storage_layout = ((p.get("hardware") or {}).get("storage") or {}).get("layout")
if storage_layout == "zfs-tiered":
    (out_dir / "mkosi.repart" / "00-esp.conf").write_text(textwrap.dedent("""\
        [Partition]
        Type=esp
        Format=vfat
        SizeMinBytes=512M
        SizeMaxBytes=512M
        """))
    (out_dir / "mkosi.repart" / "10-root-zfs.conf").write_text(textwrap.dedent("""\
        [Partition]
        Type=root
        # ZFS pool created post-install by hook scripts; mkosi just
        # reserves the partition. Actual pool creation lives in
        # scripts/hooks/during-install/zfs-pool-create.sh.
        Format=none
        SizeMinBytes=64G
        """))
else:
    # Default: single root partition (ext4)
    (out_dir / "mkosi.repart" / "00-esp.conf").write_text(textwrap.dedent("""\
        [Partition]
        Type=esp
        Format=vfat
        SizeMinBytes=512M
        SizeMaxBytes=512M
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
