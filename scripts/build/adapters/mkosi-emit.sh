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
import os, sys, yaml, pathlib, textwrap, shutil, subprocess

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

# ── prepacking (profiles/<id>.yaml provisioning:) — bake the operator user +
#    repo + selfdef + ghostproxy + dashboards + firstboot INTO the image so a
#    flashed SAIN-01 boots to a ready workstation (operator directive
#    2026-07-08). The profile can DEFAULT the bakes on; env still forces on.
prov = (p.get("provisioning") or {})
prov_bake = (prov.get("bake") or {})
prov_operator = (prov.get("operator") or {})
bake_dev_tools = bake_dev_tools or bool(prov_bake.get("dev_tools"))
bake_selfdef = bake_selfdef or bool(prov_bake.get("selfdef"))
bake_repo = bool(prov_bake.get("repo"))
bake_ghostproxy = bool(prov_bake.get("root_ghostproxy"))
bake_dashboards = bool(prov_bake.get("dashboards"))
bake_firstboot = bool(prov.get("firstboot"))
posture = prov.get("posture", "installed-off")
run_provision = bool(prov) and (bake_repo or bool(prov_operator))

repo_root = pathlib.Path(os.environ["SOVEREIGN_OS_PROFILE_FILE"]).resolve().parents[1]


def _stage_tree(src, dest, excludes):
    """rsync a build-host tree into the image overlay (mkosi.extra), pruning the
    heavy/irrelevant dirs. Best-effort: a missing rsync or source is logged, not
    fatal — an un-prepacked image still boots (root-only base)."""
    src = pathlib.Path(src)
    if not src.is_dir():
        print(f"mkosi-emit: prepack source {src} absent — skipping", file=sys.stderr)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = ["rsync", "-a", "--delete"]
    for e in excludes:
        args += ["--exclude", e]
    args += [f"{src}/", f"{dest}/"]
    try:
        subprocess.run(args, check=True)
        return True
    except (OSError, subprocess.SubprocessError) as e:
        print(f"mkosi-emit: staging {src} → {dest} failed: {e}", file=sys.stderr)
        return False

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
elif os.environ.get("SOVEREIGN_OS_ALLOW_LOCKED_ROOT"):
    # Operator EXPLICITLY opts into a locked-root image (login must then come
    # via SSH keys / autologin / a first-boot flow — NOT the console).
    print("mkosi-emit: SOVEREIGN_OS_ROOT_PASSWORD unset + SOVEREIGN_OS_ALLOW_LOCKED_ROOT "
          "set — shipping a LOCKED-root image (no console login).", file=sys.stderr)
else:
    # HARD FAIL (parity with the secure-boot-keys gate above): a build that
    # locks root produces an image that boots to a login prompt nobody can
    # ever satisfy — it looked "done + preflight-passed" but was unusable on
    # hardware (caught 2026-07-03, sain-01 flash-prep). Never silent again.
    sys.exit(
        "mkosi-emit: SOVEREIGN_OS_ROOT_PASSWORD is unset — mkosi would LOCK root and\n"
        "the image would boot to a login prompt that can NEVER accept anyone\n"
        "(unusable on hardware). Set a bootstrap password (first-login-assistant\n"
        "rotates it on first boot):\n"
        "  SOVEREIGN_OS_ROOT_PASSWORD='<bootstrap-pw>' scripts/build/orchestrate.sh run\n"
        "  # or a hash:  SOVEREIGN_OS_ROOT_PASSWORD=\"hashed:$(openssl passwd -6)\"\n"
        "To INTENTIONALLY ship a locked-root image (SSH-key / autologin only), set:\n"
        "  SOVEREIGN_OS_ALLOW_LOCKED_ROOT=1")

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

# Debian trixie split the shadow suite: /usr/bin/login + /etc/pam.d/login now
# ship in the 'login' package, while 'login.defs' ships ONLY the config file.
# 'login' is Priority: required, but mkosi's minimal Debian bootstrap does NOT
# pull all required-priority packages — it installed login.defs (a transitive
# config dep of passwd/pam) yet left out 'login' itself. Result: the image had
# NO console login binary, so agetty exec'd a nonexistent /bin/login, exited,
# and systemd (Restart=always) respawned the getty forever — an endless
# 'localhost login:' loop, image unloginnable on console. Pull it explicitly.
# (Root-caused via QEMU serial-login emulation, 2026-07-07.)
if "login" not in all_packages:
    all_packages.append("login")

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
    # nodejs from the PINNED SNAPSHOT (trixie ships 20.19.2 — identical to the
    # build host's node), so Claude Code runs OFFLINE. The build has no external
    # network (mirror is snapshot.debian.org only), which is exactly why the old
    # NodeSource/npm-registry bake silently failed. curl/ca-certs kept for the
    # operator's own post-flash use.
    for tool in ("curl", "ca-certificates", "nodejs"):
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

        # ---- dev tools (SOVEREIGN_OS_BAKE_DEV_TOOLS): Claude Code, OFFLINE ----
        # nodejs is a snapshot package (installed above). The claude-code global
        # npm tree + `claude` launcher were STAGED from the build host into
        # /usr/local (no network at postinst — nodesource/registry unreachable).
        # Just verify node + (re)link the launcher.
        if command -v node >/dev/null 2>&1; then
            echo "postinst: node $(node --version 2>/dev/null) present" >&2
            if [ -d /usr/local/lib/node_modules/@anthropic-ai/claude-code ]; then
                ln -sf ../lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe /usr/local/bin/claude
                echo "postinst: Claude Code baked (offline) — /usr/local/bin/claude" >&2
            else
                echo "postinst: claude-code not staged (host lacked it?) — skipped (non-fatal)" >&2
            fi
        else
            echo "postinst: node missing — Claude Code bake skipped (non-fatal)" >&2
        fi
        """)
if bake_selfdef:
    # BUILD selfdef always (so the flashed image ships it ready). Whether its
    # systemd fleet is INSTALLED into /etc/systemd/system is posture-gated.
    bake_block += textwrap.dedent("""\

        # ---- selfdef (SOVEREIGN_OS_BAKE_SELFDEF): build ----
        if [ -d /opt/selfdef ] && command -v cargo >/dev/null 2>&1; then
            echo "postinst: building selfdef in /opt/selfdef" >&2
            ( cd /opt/selfdef && make build ) 2>&1 \\
                || echo "postinst: selfdef build failed (non-fatal)" >&2
        else
            echo "postinst: selfdef not staged or cargo absent — build skipped (non-fatal)" >&2
        fi
        """)
    if posture != "installed-off":
        # 'everything-enabled' posture: install the units so preset-all enables them.
        bake_block += textwrap.dedent("""\
            if [ -d /opt/selfdef/packaging/systemd ]; then
                for u in /opt/selfdef/packaging/systemd/*.service /opt/selfdef/packaging/systemd/*.timer; do
                    [ -f "$u" ] && install -m 644 "$u" /etc/systemd/system/ 2>/dev/null || true
                done
                echo "postinst: selfdef units installed (posture)" >&2
            fi
            """)
    else:
        # 'installed-off' (the default): DO NOT install the units. mkosi's
        # preset-all enables every unit in /etc/systemd/system that carries
        # [Install]; the selfdef fleet (daemon + doctors + guardian + ~30 timers
        # + sovereign-guard) would then be auto-enabled and FAIL on boot (no
        # /etc/selfdef config, no target hardware for the guard). Leaving the
        # units in /opt/selfdef keeps them out of preset-all's reach; the
        # operator installs + enables them with `sovereign-osctl selfdef on`
        # (install-units + on). (Caught by QEMU emulation, 2026-07-08.)
        bake_block += textwrap.dedent("""\
            echo "postinst: selfdef built — units staged in /opt/selfdef (installed-off; turn on with 'sovereign-osctl selfdef on')" >&2
            """)

# ---- prepacking: run provision-bake.sh (operator user + repo wiring +
#      ghostproxy + dashboards + firstboot). Runs LAST in the postinst, after
#      the dev-tools/selfdef bakes, so node/claude + selfdef are already in.
#      The script lives in the STAGED repo (/opt/sovereign-os). ----
provision_block = ""
if run_provision:
    _op = prov_operator
    _groups = ",".join(_op.get("groups", ["sudo", "podman", "render", "video", "adm"]))
    provision_block = textwrap.dedent(f"""\

        # ---- prepack SAIN-01: operator user + repo + ghostproxy + dashboards + firstboot ----
        if [ -x /opt/sovereign-os/scripts/build/provision-bake.sh ]; then
            echo "postinst: prepacking (provision-bake)" >&2
            env \\
              SOVEREIGN_OS_PROFILE="{profile_id}" \\
              SOVEREIGN_OS_IMAGE_REPO="/opt/sovereign-os" \\
              SOVEREIGN_OS_OPERATOR_USER="{_op.get('username', 'operator')}" \\
              SOVEREIGN_OS_OPERATOR_GROUPS="{_groups}" \\
              SOVEREIGN_OS_OPERATOR_SHELL="{_op.get('shell', '/bin/bash')}" \\
              SOVEREIGN_OS_OPERATOR_HOME_REPO="{_op.get('home_repo', 'sovereign-os')}" \\
              SOVEREIGN_OS_OPERATOR_PASSWORD_FROM_ROOT="{'1' if _op.get('password_from_root', True) else '0'}" \\
              SOVEREIGN_OS_POSTURE="{posture}" \\
              SOVEREIGN_OS_BAKE_SELFDEF="{'1' if bake_selfdef else ''}" \\
              SOVEREIGN_OS_BAKE_GHOSTPROXY="{'1' if bake_ghostproxy else ''}" \\
              SOVEREIGN_OS_BAKE_DASHBOARDS="{'1' if bake_dashboards else ''}" \\
              SOVEREIGN_OS_BAKE_FIRSTBOOT="{'1' if bake_firstboot else ''}" \\
              bash /opt/sovereign-os/scripts/build/provision-bake.sh 2>&1 \\
                || echo "postinst: provision-bake returned nonzero (non-fatal)" >&2
        else
            echo "postinst: provision-bake.sh not staged — image stays root-only base" >&2
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

    # ---- neutralize the nvidia driver's own GPU force-loader ----
    # The nvidia package ships /etc/modules-load.d/nvidia.conf (a symlink to
    # /etc/nvidia/current-open/nvidia-load.conf) that force-loads nvidia-drm at
    # boot. On a GPU-less boot that fails ('No such device') and takes the whole
    # systemd-modules-load unit down with it → the system boots `degraded`. Drop
    # it — early KMS is handled device-gated by sovereign-nvidia-kms.service and
    # nvidia autoloads by PCI modalias on real hardware. (QEMU emulation
    # 2026-07-08: this was the failure the operator saw as the build "crashing".)
    rm -f /etc/modules-load.d/nvidia.conf
    """) + deny_block + bake_block + provision_block)
postinst.chmod(0o755)

# ---- kernel.modules.load_at_boot → /etc/modules-load.d/ (mkosi.extra overlay) ----
# The profile declares which modules must load at boot (zfs / vfio_pci), but
# nothing wrote them to systemd's modules-load.d, so it relied entirely on
# implicit load paths (initramfs / udev / softdep). Emit the canonical config so
# the declared policy is actually enforced. ONLY hardware-agnostic modules
# belong here — anything that binds a device (nvidia) HARD-FAILS the whole
# systemd-modules-load unit on a boot where the device is absent (every VM /
# emulator boot → `degraded`). GPU KMS is loaded device-gated instead (below).
load_at_boot = ((p.get("kernel") or {}).get("modules") or {}).get("load_at_boot") or []
if load_at_boot:
    mld = out_dir / "mkosi.extra" / "etc" / "modules-load.d"
    mld.mkdir(parents=True, exist_ok=True)
    (mld / "sovereign-os.conf").write_text(
        f"# kernel.modules.load_at_boot (profile {profile_id})\n"
        + "\n".join(load_at_boot) + "\n"
    )

# ---- GPU-gated KMS loader (mkosi.extra overlay) ----
# nvidia was pulled out of modules-load.d (it can't insert without a GPU →
# systemd-modules-load fails → the box boots `degraded` in every emulator run,
# the "crash" the operator saw). On real hardware nvidia autoloads by PCI
# modalias, but early KMS (nvidia-drm modeset=1, needed for a clean graphical
# boot) still wants an explicit load. Do it DEVICE-GATED: this oneshot loads
# nvidia-drm ONLY when a 10de GPU is present and ALWAYS exits 0 — so the
# workstation gets KMS and a GPU-less VM stays clean. Pure /bin/sh + sysfs, no
# pciutils dependency. (Caught by QEMU emulation, 2026-07-08.)
kms_svc = (out_dir / "mkosi.extra" / "etc" / "systemd" / "system"
           / "sovereign-nvidia-kms.service")
kms_svc.parent.mkdir(parents=True, exist_ok=True)
kms_svc.write_text(textwrap.dedent("""\
    [Unit]
    Description=Sovereign OS — load NVIDIA KMS (nvidia-drm) when a GPU is present
    Documentation=man:modprobe(8)
    After=systemd-modules-load.service
    # Skip entirely on a GPU-less boot (VM/emulator): no 10de vendor in sysfs.
    ConditionPathExistsGlob=/sys/bus/pci/devices/*/vendor

    [Service]
    Type=oneshot
    RemainAfterExit=yes
    # exit 0 no matter what — never fail the boot; the modeset load is best-effort.
    ExecStart=/bin/sh -c 'for v in /sys/bus/pci/devices/*/vendor; do [ "$(cat "$v" 2>/dev/null)" = "0x10de" ] && { modprobe nvidia-drm modeset=1 2>/dev/null; break; }; done; exit 0'

    [Install]
    WantedBy=multi-user.target
    """))
# enable it declaratively (wants-symlink; survives preset-all)
kms_wants = (out_dir / "mkosi.extra" / "etc" / "systemd" / "system"
             / "multi-user.target.wants" / "sovereign-nvidia-kms.service")
kms_wants.parent.mkdir(parents=True, exist_ok=True)
if kms_wants.is_symlink() or kms_wants.exists():
    kms_wants.unlink()
kms_wants.symlink_to("/etc/systemd/system/sovereign-nvidia-kms.service")

# ---- prepacking: stage the source trees into the image (mkosi.extra) ----
# Copied into the image BEFORE the postinst runs, so provision-bake.sh (invoked
# from the postinst) finds them at /opt. The repo INCLUDES .git so the booted
# box is git-connected at the flashed commit; build/ + target/ + caches pruned.
extra_opt = out_dir / "mkosi.extra" / "opt"
if bake_repo:
    # NB: '/build/' is ANCHORED (leading slash) so it prunes only the top-level
    # 2.4 GB build output — an unanchored 'build/' would also eat scripts/build/
    # (orchestrate + provision-bake) and break the on-image repo. target/ +
    # node_modules stay unanchored (they legitimately appear under crates/*, etc.)
    if _stage_tree(repo_root, extra_opt / "sovereign-os",
                   ["/build/", "target/", "node_modules/", ".venv/", "venv/",
                    "__pycache__/", "*.pyc", ".mypy_cache/", ".pytest_cache/"]):
        print(f"mkosi-emit: staged repo → /opt/sovereign-os (incl .git)", file=sys.stderr)
def _find_checkout(env_var, name):
    """Locate a sibling-repo checkout ROBUSTLY. The build usually runs as root
    (step 08 signs), so ~/ = /root — but the checkouts live in the operator's
    home next to sovereign-os. Try, in order: explicit env, sibling-of-repo
    (works no matter who builds), $SUDO_USER's home, then ~/. (Sibling-of-repo
    is why selfdef/ghostproxy were SKIPPED in the first prepacked build —
    ~/selfdef resolved to /root/selfdef, absent.)"""
    cands = []
    if os.environ.get(env_var):
        cands.append(pathlib.Path(os.environ[env_var]))
    cands.append(repo_root.parent / name)                    # /home/<op>/selfdef
    if os.environ.get("SUDO_USER"):
        cands.append(pathlib.Path("/home") / os.environ["SUDO_USER"] / name)
    cands.append(pathlib.Path.home() / name)
    for c in cands:
        if c.is_dir():
            return c
    return cands[0]  # doesn't exist anywhere — _stage_tree logs the skip


if bake_selfdef:
    _stage_tree(_find_checkout("SOVEREIGN_OS_SELFDEF_DIR", "selfdef"),
                extra_opt / "selfdef", ["target/", ".git/", "node_modules/"])
if bake_ghostproxy:
    _stage_tree(_find_checkout("SOVEREIGN_OS_GHOSTPROXY_DIR", "root-ghostproxy"),
                extra_opt / "root-ghostproxy", ["target/", "node_modules/"])
if bake_dev_tools:
    # Offline Claude Code: stage the build host's global npm tree (@anthropic-ai/
    # claude-code — pure JS, no version-sensitive native addons, ~473 MB) so it
    # runs on the snapshot's nodejs at boot. The postinst links /usr/local/bin/
    # claude. (The build has no npm-registry access — this replaces the network
    # bake that silently failed; 2026-07-08.)
    _nm = pathlib.Path("/usr/local/lib/node_modules")
    if (_nm / "@anthropic-ai" / "claude-code").is_dir():
        if _stage_tree(_nm, out_dir / "mkosi.extra" / "usr" / "local" / "lib" / "node_modules", []):
            print("mkosi-emit: staged Claude Code (offline) → /usr/local/lib/node_modules", file=sys.stderr)
    else:
        print("mkosi-emit: build host has no global claude-code — dev-tools claude not baked", file=sys.stderr)


# ---- mask systemd-networkd-wait-online (mkosi.extra overlay) ----
# systemd-networkd is enabled but the image ships NO .network config — the
# actual link/VLAN setup is done by the network-vlan-config first-boot hook.
# With nothing to configure, systemd-networkd-wait-online had no link to bring
# 'online' and blocked boot for its full 120s timeout, then exited FAILED
# (res=failed): a ~2-minute stall on EVERY boot plus a failed unit. Nothing in
# the image pulls network-online.target as a boot ordering barrier, so masking
# the wait is safe and standard for a headless / first-boot-configured box
# (networkd itself still runs; the box still gets network from the hook).
# Masked declaratively (symlink → /dev/null) so it survives systemd preset.
# (Caught by QEMU verbose-boot emulation, 2026-07-07.)
wait_online = (out_dir / "mkosi.extra" / "etc" / "systemd" / "system"
               / "systemd-networkd-wait-online.service")
wait_online.parent.mkdir(parents=True, exist_ok=True)
if wait_online.is_symlink() or wait_online.exists():
    wait_online.unlink()
wait_online.symlink_to("/dev/null")

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
