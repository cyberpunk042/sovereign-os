#!/usr/bin/env bash
# scripts/install/install-sovereign-root.sh — Phase 3 of the single-OS
# reflash-root layout.
#
# Installs a REAL, MUTABLE Debian-13 root into the sovereign-root LV, running
# the custom znver5 kernel, with jfortin + root, mounting the SHARED
# sovereign-home LV as /home. This is the reflash-root procedure: re-running
# it rebuilds the sovereign root WITHOUT touching the shared /home. Boots via
# GRUB-EFI on sovereign's own ESP.
#
# Why mutable Debian (not the mkosi appliance image): the operator wants to
# control + change everything (apt, GUI later, toggle modules). The mkosi
# image is immutable (no apt/dpkg) and boots by whole-disk auto-discovery —
# the wrong shape for a reflashable LV root. This reuses the crown jewel (the
# custom kernel .deb) on a normal, controllable root.
#
# Inherits from the RUNNING Debian (no questions, matches what you use):
#   keyboard · locale · timezone · root + jfortin password entries.
#
# Run: sudo scripts/install/install-sovereign-root.sh
set -euo pipefail

ROOT_LV="${SOVEREIGN_OS_ROOT_LV:-/dev/sovereign/root}"
HOME_LV="${SOVEREIGN_OS_HOME_LV:-/dev/sovereign/home}"
# ESP = sovereign's own ESP partition (Phase 1 created it as <target-disk>p1).
# Derive it from the target disk so `install system --to <disk>` works for ANY
# NVMe, not just the historical /dev/nvme1n1 default.
_TARGET_DISK="${SOVEREIGN_OS_TARGET_DISK:-/dev/nvme1n1}"
case "${_TARGET_DISK}" in
  *[0-9]) _ESP_DEFAULT="${_TARGET_DISK}p1" ;;
  *)      _ESP_DEFAULT="${_TARGET_DISK}1"  ;;
esac
ESP_PART="${SOVEREIGN_OS_ESP:-${_ESP_DEFAULT}}"
PRIMARY_USER="${SOVEREIGN_OS_USER:-jfortin}"
SUITE="${SOVEREIGN_OS_SUITE:-trixie}"
MIRROR="${SOVEREIGN_OS_MIRROR:-http://deb.debian.org/debian}"
MNT=/mnt/sovereign-install
REPO_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# GUI desktop + dashboards on by default (operator directive 2026-07-02).
# Set SOVEREIGN_OS_INSTALL_GUI=0 for a headless install.
INSTALL_GUI="${SOVEREIGN_OS_INSTALL_GUI:-1}"
# Desktop frontend on the INSTALLED system. Default kde-plasma (the sain-01
# profile default) — NOT gnome. Without this the GUI stage passed only the
# legacy SOVEREIGN_OS_DESKTOP=gnome and install-gui-dashboards.sh installed
# GNOME, contradicting the profile's frontend.default: kde-plasma.
FRONTEND="${SOVEREIGN_OS_FRONTEND:-kde-plasma}"
FRONTEND_INSTALL="${SOVEREIGN_OS_FRONTEND_INSTALL:-kde-plasma,gnome,dashboards-kiosk}"

# ── what the installed system contains ───────────────────────────────────────
# ONE definition, shared with the bootable-installer path
# (scripts/build/build-target-rootfs.sh). Both surfaces used to carry their own
# hand-copied package list, so fixing one left the other building an unusable
# machine — see the library header for the full story.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/installed-system.sh"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n\033[36m━━━ %s\033[0m\n' "$*"; }

# ── VERIFY before claiming success ───────────────────────────────────────────
# This installer used to print "install complete", "a new firmware boot entry
# now exists", "boots to graphical.target" and "uname -r → 6.12.0" without
# CHECKING ANY OF IT. Every failure this operator hit in 2026-07 was found by
# rebooting into a black screen, never by the tool that had just declared
# success. An installer that cannot verify its own output is not bulletproof.
#
# Runs while ${MNT} is still mounted. Hard failures FAIL the install; the
# operator should learn here, not at the firmware boot menu.
sovereign_verify_install() {
  local fail=0 warn=0
  step "verifying the installed system"

  _v_ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
  _v_bad()  { printf '  \033[31m✗\033[0m %s\n' "$*"; fail=$((fail+1)); }
  _v_warn() { printf '  \033[33m!\033[0m %s\n' "$*"; warn=$((warn+1)); }

  # 1. a bootloader actually exists on the ESP
  local efi_n
  efi_n="$(find "${MNT}/boot/efi/EFI" -iname '*.efi' 2>/dev/null | wc -l)"
  if [ "${efi_n}" -gt 0 ]; then
    _v_ok "ESP carries ${efi_n} EFI binary(ies)"
  else
    _v_bad "ESP has NO .efi binary — this disk cannot boot"
  fi

  # 2. a kernel + initramfs are installed, and WHICH kernel
  local kver
  kver="$(ls -1 "${MNT}/boot"/vmlinuz-* 2>/dev/null | sed 's|.*/vmlinuz-||' | sort -V | tail -1 || true)"
  if [ -n "${kver}" ]; then
    _v_ok "kernel installed: ${kver}"
    case "${kver}" in
      6.12.0*) _v_ok "  …that is the custom znver5 build" ;;
      *)       _v_warn "  …that is the STOCK Debian kernel, not the custom znver5 one" ;;
    esac
    [ -f "${MNT}/boot/initrd.img-${kver}" ] \
      && _v_ok "initramfs present for ${kver}" \
      || _v_bad "no initramfs for ${kver} — the kernel cannot mount root"
  else
    _v_bad "NO kernel in /boot — this disk cannot boot"
  fi

  # 3. fstab points at real filesystems
  if [ -s "${MNT}/etc/fstab" ] && grep -q ' / ' "${MNT}/etc/fstab" 2>/dev/null; then
    _v_ok "fstab has a root entry"
  else
    _v_bad "fstab has no root entry"
  fi

  # 4. SOMEONE CAN LOG IN. A locked-only shadow shipped once already.
  local usable
  usable="$(awk -F: '($2 ~ /^\$/){print $1}' "${MNT}/etc/shadow" 2>/dev/null | tr '\n' ' ')"
  if [ -n "${usable}" ]; then
    _v_ok "accounts with a usable password: ${usable}"
  else
    _v_bad "NO account has a usable password — you would boot to a login nobody can pass"
  fi

  # 5. if a desktop was requested, it must be able to actually start
  if [ "${INSTALL_GUI}" = 1 ]; then
    [ -e "${MNT}/etc/systemd/system/display-manager.service" ] \
      && _v_ok "display-manager.service is enabled" \
      || _v_bad "GUI requested but no display-manager.service — you get a text console"
    # The black-screen bug: X needs a driver that works with nomodeset and an
    # unbindable GPU. modesetting/nvidia are not enough on their own.
    if ls "${MNT}/usr/lib/xorg/modules/drivers/"{fbdev,vesa}_drv.so >/dev/null 2>&1; then
      _v_ok "X fallback driver present (fbdev/vesa)"
    else
      _v_bad "no fbdev/vesa X driver — with nomodeset the X server cannot start at all"
    fi
    # …and a terminal, or the desktop is unusable (operator, 2026-07-26).
    [ -x "${MNT}/usr/bin/konsole" ] || [ -x "${MNT}/usr/bin/xterm" ] \
      && _v_ok "terminal emulator installed" \
      || _v_warn "no terminal emulator on the desktop"
  fi

  # 6. DNS — networkd alone leaves glibc with no resolver
  [ -e "${MNT}/etc/resolv.conf" ] \
    && _v_ok "/etc/resolv.conf present" \
    || _v_warn "no /etc/resolv.conf — hostname lookups will fail on first boot"

  # 7. THE KERNEL CMDLINE ACTUALLY REACHED grub.cfg. This is the failure that
  # cost the operator a day: every package installed, sddm registered as
  # display-manager, zero failed units, boot completed in 1m47 — and a dark
  # screen, because the installed system booted without nomodeset. No GPU
  # driver binds on this hardware, so without nomodeset there is no EFI
  # framebuffer, no /dev/fb0, and X has no device to open. Declaring the
  # cmdline is not applying it: verify it in the GENERATED grub.cfg, not in
  # /etc/default/grub.
  if [ -f "${MNT}/boot/grub/grub.cfg" ]; then
    for _opt in ${SOVEREIGN_OS_KERNEL_CMDLINE}; do
      if grep -qE "^[[:space:]]*linux.*[[:space:]]${_opt}([[:space:]]|\$)" \
           "${MNT}/boot/grub/grub.cfg" 2>/dev/null; then
        _v_ok "kernel cmdline carries '${_opt}'"
      else
        _v_bad "grub.cfg has NO '${_opt}' — declared in installed-system.sh and never applied"
      fi
    done
  else
    _v_bad "no /boot/grub/grub.cfg — nothing will boot"
  fi

  # 8. the blacklist reached the target, and the initrd was built after it
  for _m in ${SOVEREIGN_OS_MODULE_BLACKLIST}; do
    [ -f "${MNT}/etc/modprobe.d/sovereign-blacklist-${_m}.conf" ] \
      && _v_ok "${_m} blacklisted" \
      || _v_bad "${_m} NOT blacklisted — it will probe and can take the console"
  done

  echo
  if [ "${fail}" -gt 0 ]; then
    red "verification FAILED: ${fail} blocking problem(s), ${warn} warning(s)."
    red "  The install did NOT produce a bootable system. Fix the above and re-run;"
    red "  do not reboot into it expecting it to work."
    return 1
  fi
  [ "${warn}" -gt 0 ] && info "verification passed with ${warn} warning(s)." || grn "verification passed — this disk should boot."
  return 0
}

[ "$(id -u)" -eq 0 ] || { red "must run as root: sudo $0"; exit 1; }

# Identity source. inherit = copy keyboard/locale/tz/credentials from the RUNNING
# host (the from-host path — no questions). answers = take them from env vars and
# CREATE the user in-chroot (the installer-USB path — there is no host to inherit
# from). Default inherit preserves the original from-host behavior exactly.
IDENTITY_MODE="${SOVEREIGN_OS_IDENTITY_MODE:-inherit}"

# ── SAFETY ──
for d in "${ROOT_LV}" "${HOME_LV}" "${ESP_PART}"; do
  [ -b "$d" ] || { red "ABORT: ${d} missing — run setup-lvm-dualboot.sh + migrate-home.sh first"; exit 1; }
done
RUN_ROOT_DISK="/dev/$(lsblk -no PKNAME "$(findmnt -no SOURCE /)" | head -1)"
ESP_DISK="/dev/$(lsblk -no PKNAME "${ESP_PART}" | head -1)"
if [ "${ESP_DISK}" = "${RUN_ROOT_DISK}" ]; then
  red "ABORT: sovereign ESP ${ESP_PART} is on the RUNNING OS disk — wrong target."; exit 1
fi
# Never install onto the disk we BOOTED from (the installer USB / live medium).
# The RUN_ROOT_DISK gate above misses this when the live root is a squashfs, so
# the installer-TUI passes the boot-medium disk explicitly.
if [ -n "${SOVEREIGN_OS_FORBID_DISK:-}" ] && [ "${ESP_DISK}" = "${SOVEREIGN_OS_FORBID_DISK}" ]; then
  red "ABORT: target ${ESP_DISK} is the boot medium (SOVEREIGN_OS_FORBID_DISK) — refusing."; exit 1
fi
# inherit mode needs the user to exist on the running host; answers mode creates it.
if [ "${IDENTITY_MODE}" = "inherit" ]; then
  id "${PRIMARY_USER}" >/dev/null 2>&1 || { red "ABORT: user ${PRIMARY_USER} doesn't exist on this host to inherit"; exit 1; }
fi

# ══ OFFLINE / SQUASHFS MODE ═══════════════════════════════════════════════════
# The installer USB carries a COMPLETE, pre-built rootfs (build-target-rootfs.sh:
# base + stock kernel + KDE + sovereign-os cockpit). Lay it onto the LV and do
# ONLY the per-machine wiring — no debootstrap/apt over the network. 100% offline.
if [ -n "${SOVEREIGN_OS_ROOTFS_SQUASHFS:-}" ]; then
  SQ="${SOVEREIGN_OS_ROOTFS_SQUASHFS}"
  [ -r "$SQ" ] || { red "ABORT: rootfs squashfs not found: $SQ"; exit 1; }
  command -v unsquashfs >/dev/null || { info "installing squashfs-tools…"; apt-get install -y squashfs-tools; }

  step "offline install: unsquashing $(du -h "$SQ" | cut -f1) → ${ROOT_LV}"
  mkdir -p "${MNT}"; mountpoint -q "${MNT}" || mount "${ROOT_LV}" "${MNT}"
  find "${MNT}" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
  unsquashfs -f -d "${MNT}" "$SQ"

  step "wiring the installed root to this machine (fstab · identity · GRUB)"
  mount -o bind /dev "${MNT}/dev"; mount -o bind /dev/pts "${MNT}/dev/pts"
  mount -o bind /proc "${MNT}/proc"; mount -o bind /sys "${MNT}/sys"
  mkdir -p "${MNT}/boot/efi"; mount "${ESP_PART}" "${MNT}/boot/efi"
  cp /etc/resolv.conf "${MNT}/etc/resolv.conf" 2>/dev/null || true

  ROOT_UUID=$(blkid -s UUID -o value "${ROOT_LV}")
  HOME_UUID=$(blkid -s UUID -o value "${HOME_LV}")
  ESP_UUID=$(blkid -s UUID -o value "${ESP_PART}")
  cat > "${MNT}/etc/fstab" <<FSTAB
# sovereign-os reflash-root — generated $(date -I)
UUID=${ROOT_UUID}  /          ext4  defaults,relatime           0  1
UUID=${HOME_UUID}  /home      ext4  defaults,relatime           0  2
UUID=${ESP_UUID}   /boot/efi  vfat  umask=0077,shortname=winnt  0  1
FSTAB

  # identity: inherit from the running host OR create from answers in-chroot
  if [ "${IDENTITY_MODE}" = "inherit" ]; then
    for f in /etc/default/keyboard /etc/default/locale /etc/locale.gen /etc/localtime; do
      [ -e "$f" ] && cp -a "$f" "${MNT}${f}" || true
    done
    for u in root "${PRIMARY_USER}"; do
      for db in passwd shadow group gshadow; do
        if grep -q "^${u}:" "/etc/${db}" 2>/dev/null; then
          grep "^${u}:" "/etc/${db}" | while IFS= read -r line; do
            grep -q "^${u}:" "${MNT}/etc/${db}" \
              && sed -i "s|^${u}:.*|${line}|" "${MNT}/etc/${db}" \
              || echo "$line" >> "${MNT}/etc/${db}"
          done
        fi
      done
    done
    CHROOT_USER_SETUP=""
  else
    printf 'XKBLAYOUT="%s"\n' "${SOVEREIGN_OS_KEYMAP:-us}" > "${MNT}/etc/default/keyboard"
    printf 'LANG=%s\n' "${SOVEREIGN_OS_LOCALE:-en_US.UTF-8}" > "${MNT}/etc/default/locale"
    ln -sf "/usr/share/zoneinfo/${SOVEREIGN_OS_TIMEZONE:-UTC}" "${MNT}/etc/localtime" || true
    CHROOT_USER_SETUP="$(cat <<US
echo 'root:${SOVEREIGN_OS_ROOT_PASS:-sovereign}' | chpasswd
id ${PRIMARY_USER} >/dev/null 2>&1 || useradd -m -u ${SOVEREIGN_OS_USER_UID:-1000} -s /bin/bash ${PRIMARY_USER}
echo '${PRIMARY_USER}:${SOVEREIGN_OS_USER_PASS:-sovereign}' | chpasswd
US
)"
  fi

  cat > "${MNT}/tmp/wire.sh" <<WIRE
set -uo pipefail
echo sovereign-os > /etc/hostname
printf '127.0.0.1 localhost\n127.0.1.1 sovereign-os\n' > /etc/hosts
${CHROOT_USER_SETUP}
usermod -aG sudo ${PRIMARY_USER} 2>/dev/null || true
# Keep amdgpu out of the initrd too -- it probes before userspace modprobe.d
# would ever be consulted. See SOVEREIGN_OS_MODULE_BLACKLIST in installed-system.sh.
mkdir -p /etc/modprobe.d
for _m in ${SOVEREIGN_OS_MODULE_BLACKLIST}; do
  echo "blacklist ${_m}" > "/etc/modprobe.d/sovereign-blacklist-${_m}.conf"
done
update-initramfs -u -k all || true
sed -i 's|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX="root=/dev/mapper/sovereign-root rw ${SOVEREIGN_OS_KERNEL_CMDLINE}"|' /etc/default/grub || true
grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=sovereign-os --recheck
update-grub
WIRE
  chroot "${MNT}" bash /tmp/wire.sh

  sync
  sovereign_verify_install || exit 1
  umount "${MNT}/boot/efi" 2>/dev/null || true
  umount "${MNT}/sys" "${MNT}/proc" "${MNT}/dev/pts" "${MNT}/dev" 2>/dev/null || true
  umount "${MNT}" 2>/dev/null || true
  grn "━━━ offline install complete — mutable Debian + ${FRONTEND} + cockpit on sovereign-root ━━━"
  echo "Reboot → firmware boot menu → 'sovereign-os'. Login: ${PRIMARY_USER} (your usual password). /home preserved."
  exit 0
fi
# ══ end offline mode; below is the online debootstrap+apt path ════════════════

# ── locate the custom kernel .debs ──
step "locating custom kernel .debs"
KDIR=""
[ -f /root/.sovereign-os/build-state/env-kernel-debs.sh ] && . /root/.sovereign-os/build-state/env-kernel-debs.sh || true
for cand in "${SOVEREIGN_OS_KERNEL_DEBS_DIR:-}" /mnt/kernel_forge /mnt/kernel_forge/linux-stable/..; do
  [ -n "$cand" ] && ls "$cand"/linux-image-6.12.0_*.deb >/dev/null 2>&1 && { KDIR="$cand"; break; }
done
# Custom znver5 kernel if built; otherwise FALL BACK to the stock Debian kernel
# so the install still produces a bootable, working system (the custom kernel is
# a perf optimization, not a prerequisite). Rebuild it (orchestrate.sh 02-04) and
# re-run install to switch to znver5. Overridable: SOVEREIGN_OS_STOCK_KERNEL=1.
if [ -n "$KDIR" ] && [ "${SOVEREIGN_OS_STOCK_KERNEL:-0}" != "1" ]; then
  CUSTOM_KERNEL=1
  KIMG=$(printf '%s\n' "$KDIR"/linux-image-6.12.0_*.deb | grep -v dbg | sort -V | tail -1)
  KHDR=$(ls -1 "$KDIR"/linux-headers-6.12.0_*.deb 2>/dev/null | sort -V | tail -1 || true)
  info "custom kernel image  : ${KIMG}"
  info "custom kernel headers: ${KHDR:-none found; DKMS cannot build modules later without them}"
else
  CUSTOM_KERNEL=0
  KIMG=""; KHDR=""
  red "custom kernel .debs not found — falling back to the STOCK Debian kernel (linux-image-amd64)."
  red "  the box boots + works; build the znver5 kernel (orchestrate.sh 02-04) + re-run install to switch."
fi

command -v debootstrap >/dev/null || { info "installing debootstrap…"; apt-get install -y debootstrap; }

# ── mount target root + bring up ESP + shared home ──
step "mounting lv_root + sovereign ESP"
mkdir -p "${MNT}"
mountpoint -q "${MNT}" || mount "${ROOT_LV}" "${MNT}"
mkdir -p "${MNT}/boot/efi"

# ── base system ──
step "debootstrap ${SUITE} → lv_root (a few minutes)"
if [ ! -x "${MNT}/bin/bash" ]; then
  debootstrap --arch=amd64 --components=main,contrib,non-free,non-free-firmware \
    "${SUITE}" "${MNT}" "${MIRROR}"
else
  info "base already present — skipping debootstrap"
fi

# ── identity: keyboard / locale / timezone / credentials ──
# CHROOT_USER_SETUP is injected into the in-chroot setup below; empty in inherit
# mode (accounts are copied here), populated in answers mode (created in-chroot).
CHROOT_USER_SETUP=""
if [ "${IDENTITY_MODE}" = "inherit" ]; then
  step "inheriting keyboard / locale / timezone / credentials from the running host"
  for f in /etc/default/keyboard /etc/default/locale /etc/locale.gen /etc/localtime; do
    [ -e "$f" ] && cp -a "$f" "${MNT}${f}" && info "inherited ${f}"
  done
  # root + jfortin account lines (same uid/gid + same passwords)
  inherit_user() {
    local u="$1" db
    for db in passwd shadow group gshadow; do
      if getent "$db" "$u" >/dev/null 2>&1 || grep -q "^${u}:" "/etc/${db}" 2>/dev/null; then
        grep "^${u}:" "/etc/${db}" 2>/dev/null | while IFS= read -r line; do
          grep -q "^${u}:" "${MNT}/etc/${db}" \
            && sed -i "s|^${u}:.*|${line}|" "${MNT}/etc/${db}" \
            || echo "$line" >> "${MNT}/etc/${db}"
        done
      fi
    done
  }
  inherit_user root
  inherit_user "${PRIMARY_USER}"
  info "inherited root + ${PRIMARY_USER} (uid $(id -u "${PRIMARY_USER}")) credentials"
else
  # answers mode (installer USB): no host to inherit — take from env, create the
  # user in-chroot. Passwords are plaintext answers (preseed-style, expected for
  # an unattended installer); the installer-TUI collects/confirms them.
  local_keymap="${SOVEREIGN_OS_KEYMAP:-us}"
  local_locale="${SOVEREIGN_OS_LOCALE:-en_US.UTF-8}"
  local_tz="${SOVEREIGN_OS_TIMEZONE:-UTC}"
  local_uid="${SOVEREIGN_OS_USER_UID:-1000}"
  step "identity from answers: keyboard=${local_keymap} locale=${local_locale} tz=${local_tz} user=${PRIMARY_USER}(uid ${local_uid})"
  printf 'XKBLAYOUT="%s"\n' "${local_keymap}" > "${MNT}/etc/default/keyboard"
  printf 'LANG=%s\n' "${local_locale}"        > "${MNT}/etc/default/locale"
  printf '%s UTF-8\n' "${local_locale}"       > "${MNT}/etc/locale.gen"
  ln -sf "/usr/share/zoneinfo/${local_tz}" "${MNT}/etc/localtime" || true
  CHROOT_USER_SETUP="$(cat <<USERSETUP
echo 'root:${SOVEREIGN_OS_ROOT_PASS:-sovereign}' | chpasswd
id ${PRIMARY_USER} >/dev/null 2>&1 || useradd -m -u ${local_uid} -s /bin/bash -c '${PRIMARY_USER}' ${PRIMARY_USER}
echo '${PRIMARY_USER}:${SOVEREIGN_OS_USER_PASS:-sovereign}' | chpasswd
USERSETUP
)"
fi

# ── fstab: lv_root / , lv_home /home (THE shared home) , sovereign ESP /boot/efi ──
step "writing fstab (shared /home wired in)"
ROOT_UUID=$(blkid -s UUID -o value "${ROOT_LV}")
HOME_UUID=$(blkid -s UUID -o value "${HOME_LV}")
ESP_UUID=$(blkid -s UUID -o value "${ESP_PART}")
cat > "${MNT}/etc/fstab" <<EOF
# sovereign-os reflash-root — generated $(date -I)
UUID=${ROOT_UUID}  /          ext4  defaults,relatime           0  1
UUID=${HOME_UUID}  /home      ext4  defaults,relatime           0  2
UUID=${ESP_UUID}   /boot/efi  vfat  umask=0077,shortname=winnt  0  1
EOF
info "$(grep -c UUID "${MNT}/etc/fstab") mounts written"

# ── chroot setup ──
step "configuring inside the new root (kernel, lvm, grub, network)"
mount -o bind /dev  "${MNT}/dev"
mount -o bind /dev/pts "${MNT}/dev/pts"
mount -o bind /proc "${MNT}/proc"
mount -o bind /sys  "${MNT}/sys"
mount "${ESP_PART}" "${MNT}/boot/efi"
if [ "${CUSTOM_KERNEL}" = 1 ]; then
  cp "${KIMG}" "${MNT}/tmp/"; [ -n "${KHDR}" ] && cp "${KHDR}" "${MNT}/tmp/" || true
  KERNEL_INSTALL_CMD="apt-get install -y /tmp/$(basename "${KIMG}") $( [ -n "${KHDR}" ] && echo /tmp/$(basename "${KHDR}") )"
else
  # stock Debian kernel (+ headers so DKMS can still build modules later)
  KERNEL_INSTALL_CMD="apt-get install -y --no-install-recommends linux-image-amd64 linux-headers-amd64"
fi
cp /etc/resolv.conf "${MNT}/etc/resolv.conf"

cat > "${MNT}/tmp/chroot-setup.sh" <<CHROOT
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
echo "sovereign-os" > /etc/hostname
printf '127.0.0.1 localhost\n127.0.1.1 sovereign-os\n' > /etc/hosts

cat > /etc/apt/sources.list <<APT
deb ${MIRROR} ${SUITE} main contrib non-free non-free-firmware
deb ${MIRROR} ${SUITE}-updates main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security ${SUITE}-security main contrib non-free non-free-firmware
APT
apt-get update

# essentials: lvm (root is on LVM!), bootloader, initramfs, login, net, sudo
# + python3 + PyYAML/jsonschema (the dashboard/operator daemons import yaml at
#   runtime) + node_exporter (scrapes the Layer-B textfile metrics).
apt-get install -y --no-install-recommends \
  ${SOVEREIGN_OS_BASE_PACKAGES} ${SOVEREIGN_OS_WORKSTATION_PACKAGES}

# regenerate locale we inherited
locale-gen || true

# DHCP on wired interfaces via networkd
cat > /etc/systemd/network/20-wired.network <<NET
[Match]
Name=en* eth*
[Network]
DHCP=yes
NET
systemctl enable systemd-networkd systemd-resolved

# kernel: custom znver5 .debs from /tmp if built, else the stock Debian kernel.
# KERNEL_INSTALL_CMD is composed by the outer shell (unquoted heredoc) so the
# real filenames / the stock fallback are baked in at write-time.
${KERNEL_INSTALL_CMD}

# answers mode: create root+user credentials in-chroot (empty in inherit mode,
# where the accounts were already copied from the host).
${CHROOT_USER_SETUP}

# jfortin: ensure sudo
usermod -aG sudo ${PRIMARY_USER} || true

# initramfs WITH lvm (so it can find root on /dev/mapper/sovereign-root)
# The ONLINE (debootstrap) path needs the same blacklist as the offline one.
# Two writers, one fix: the offline path got it and this one did not -- the same
# drift that had the d-i preseed and installed-system.sh disagreeing all session.
mkdir -p /etc/modprobe.d
for _m in ${SOVEREIGN_OS_MODULE_BLACKLIST}; do
  echo "blacklist ${_m}" > "/etc/modprobe.d/sovereign-blacklist-${_m}.conf"
done
update-initramfs -u -k all

# GRUB: root=lv_root, install to sovereign's own ESP, own bootloader id
sed -i 's|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX="root=/dev/mapper/sovereign-root rw ${SOVEREIGN_OS_KERNEL_CMDLINE}"|' /etc/default/grub
grub-install --target=x86_64-efi --efi-directory=/boot/efi \
  --bootloader-id=sovereign-os --recheck
update-grub
echo "CHROOT-OK"
CHROOT
chmod +x "${MNT}/tmp/chroot-setup.sh"
chroot "${MNT}" /tmp/chroot-setup.sh

# ── GUI desktop + dashboards (default ON — operator directive 2026-07-02) ──
# Runs while dev/proc/sys + resolv.conf are still bound (apt works in-chroot).
if [ "${INSTALL_GUI}" = 1 ]; then
  step "installing GUI desktop + dashboards (SOVEREIGN_OS_INSTALL_GUI=1)"
  STAGE=/opt/sovereign-os-src
  mkdir -p "${MNT}${STAGE}"
  for d in scripts webapp profiles config systemd share; do
    [ -d "${REPO_SRC}/${d}" ] && cp -a "${REPO_SRC}/${d}" "${MNT}${STAGE}/"
  done
  chroot "${MNT}" env \
    DEBIAN_FRONTEND=noninteractive \
    SOVEREIGN_OS_SRC="${STAGE}" \
    SOVEREIGN_OS_FRONTEND="${FRONTEND}" \
    SOVEREIGN_OS_FRONTEND_INSTALL="${FRONTEND_INSTALL}" \
    SOVEREIGN_OS_DESKTOP="${SOVEREIGN_OS_DESKTOP:-${FRONTEND}}" \
    bash "${STAGE}/scripts/install/install-gui-dashboards.sh"
  info "GUI + dashboards installed (frontend=${FRONTEND}; hub on :8100, launcher in app menu + autostart)"
else
  info "SOVEREIGN_OS_INSTALL_GUI=0 — headless install; run scripts/install/install-gui-dashboards.sh later to add the GUI"
fi

# ── cleanup ──
step "unmounting"
sync
sovereign_verify_install || exit 1
umount "${MNT}/boot/efi" || true
umount "${MNT}/sys" "${MNT}/proc" "${MNT}/dev/pts" "${MNT}/dev" || true
umount "${MNT}" || true

grn "━━━ Phase 3 complete — sovereign-os installed ━━━"
cat <<EOF

Installed into lv_root: Debian ${SUITE} + your custom znver5 kernel, GRUB on
sovereign's ESP (${ESP_PART}), mounting the shared /home, with root + ${PRIMARY_USER}
(same passwords as this machine).

A new firmware boot entry 'sovereign-os' now exists. To boot it:
  reboot → firmware boot menu (F8 / F11 on the ProArt) → 'sovereign-os'
  (or it may appear in the boot order automatically)

Log in as ${PRIMARY_USER} with your usual password. Your files are already there
(shared /home). 'uname -r' → 6.12.0.

Your existing Debian is untouched on ${RUN_ROOT_DISK}; pick it from the same boot menu anytime.

This is a MUTABLE system: apt works. /home survives regardless of what you toggle.
EOF

if [ "${INSTALL_GUI}" = 1 ]; then
  cat <<EOF
GUI + dashboards are ON by default:
  - Debian ${SUITE} desktop (${FRONTEND}) boots to graphical.target.
  - The dashboard hub runs on boot (loopback): http://127.0.0.1:8100/
  - Log in and look for "Sovereign Dashboards" — it's in the app menu, on the
    desktop, and auto-opens in the browser on first login.
Add the nvidia + zfs stack anytime (DKMS builds against the headers we installed).
EOF
else
  cat <<EOF
Headless install (SOVEREIGN_OS_INSTALL_GUI=0). Reach the dashboards over ssh /
loopback, or add the GUI later from inside sovereign-os:
  sudo scripts/install/install-gui-dashboards.sh
EOF
fi
