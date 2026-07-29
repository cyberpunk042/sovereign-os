#!/bin/sh
# Self-check for a freshly installed sovereign-os, run in-target by the d-i
# late_command and readable afterwards via `sovereign-osctl install logs --from`.
#
# WHY THIS EXISTS. The direct-install path fails loudly (sovereign_verify_install).
# The debian-installer path had no verification at all: it installed every
# package, registered sddm as display-manager, finished with zero failed units
# -- and produced a dark screen, because the kernel booted without nomodeset and
# so had no framebuffer for X to open (2026-07-26). A silent success is what
# cost the operator a day.
#
# This NEVER fails the install. d-i has already partitioned and unpacked by the
# time it runs; aborting here would leave a half-installed disk and tell the
# operator nothing. It writes evidence instead.
set -u
OUT=/var/log/sovereign-os/install-verify.log
# Package names differ per distro; checking a Debian name on Ubuntu reported
# "MISSING firmware-amd-graphics" on a system that had linux-firmware installed
# correctly (2026-07-29).
# Source the runtime distro lib SAFELY. `.` is a POSIX special builtin: when
# the file does not exist the shell EXITS immediately and `|| true` never runs
# (dash exits 2). Test for the file first (2026-07-29 — this exact construct
# made verify-installed-system.sh exit 2 on any host without the lib).
for _l in "$(dirname "$0")/lib/target-distro.sh" \
          /opt/sovereign-os/scripts/install/lib/target-distro.sh; do
  [ -r "${_l}" ] || continue
  . "${_l}"
  break
done
if ! command -v target_firmware_package >/dev/null 2>&1; then
  target_firmware_package() { printf 'firmware-amd-graphics'; }
fi
mkdir -p /var/log/sovereign-os

{
  echo "== sovereign-os install self-check =="
  echo

  echo "-- kernel cmdline that GRUB will use --"
  grep -m2 -E "^[[:space:]]*linux[[:space:]]" /boot/grub/grub.cfg 2>/dev/null \
    || echo "  NO grub.cfg -- nothing will boot"
  # THE ROUTE TO A GRAPHICAL SEAT IS PER-DISTRO, and the wrong one is a silent
  # total failure in BOTH directions (2026-07-29). Debian wants nomodeset;
  # Ubuntu's Wayland-only Plasma is killed by it and wants a real DRM device
  # instead. Ask the shared definition rather than assuming Debian.
  _route="$(target_seat_route 2>/dev/null || echo nomodeset)"
  _want="$(target_seat_cmdline_option 2>/dev/null || echo nomodeset)"

  # GRUB's RECOVERY entry always carries `nomodeset` (Ubuntu) or `single`
  # (Debian) — that is what recovery mode IS, on every Debian-family grub.cfg
  # ever generated. Grepping all `linux` lines therefore finds nomodeset on a
  # PERFECTLY CORRECT Ubuntu install and reports it FATAL.
  #
  # Caught 2026-07-29 by the first full Ubuntu install: the normal entry read
  #   ro nvidia-drm.modeset=1 quiet splash
  # and the recovery entry read
  #   ro recovery nomodeset dis_ucode_ldr nvidia-drm.modeset=1
  # Only the entry the machine actually boots counts.
  _primary_linux() {
    grep -E "^[[:space:]]*linux[[:space:]]" /boot/grub/grub.cfg 2>/dev/null \
      | grep -vE "[[:space:]](recovery|single)([[:space:]]|$)"
  }
  _has_nomodeset=no
  _primary_linux | grep -qE "[[:space:]]nomodeset([[:space:]]|$)" && _has_nomodeset=yes
  _has_want=no
  _wantre="$(printf '%s' "${_want}" | sed 's/[.[\*^$]/\\&/g')"
  _primary_linux | grep -qE "[[:space:]]${_wantre}([[:space:]]|$)" && _has_want=yes

  if [ "${_has_want}" = yes ]; then
    echo "  OK: ${_want} present (the ${_route} route for this distro)"
  else
    # CORRECTED 2026-07-28. This used to say "no EFI framebuffer, X cannot
    # start". That is wrong: efifb attaches fine without nomodeset, and the
    # failed install's journal shows `fb0: EFI VGA frame buffer device` on all
    # three boots. The wrong explanation cost an hour of the investigation.
    echo "  PROBLEM: ${_want} ABSENT from the kernel command line"
    if [ "${_route}" = nomodeset ]; then
      echo "           udev will not tag fb0 master-of-seat (71-seat.rules"
      echo "           rules 23/28 require IMPORT{cmdline}=nomodeset), so logind"
      echo "           reports CanGraphical=no and sddm never starts X"
    else
      echo "           no DRM device will be registered (71-seat.rules rule 35"
      echo "           needs a bound KMS driver), and this distro's Plasma is"
      echo "           WAYLAND-ONLY, so there is no session to fall back to"
    fi
  fi

  # The inverse, which matters only on the DRM route: nomodeset on Ubuntu is
  # not a degradation, it is fatal. Proven on a real disk — stripping it took
  # the same install from a blinking cursor to the Kubuntu greeter.
  if [ "${_route}" = drm ] && [ "${_has_nomodeset}" = yes ]; then
    echo "  PROBLEM: nomodeset is present, and on this distro it is FATAL."
    echo "           Plasma here is Wayland-only (/usr/share/xsessions is empty)"
    echo "           and Wayland needs the DRM device nomodeset removes."
    echo "           It also blocks the GPU driver, so the card is unusable for"
    echo "           inference as well. Remove it:"
    echo "             sudo sed -i 's/ *nomodeset//' /etc/default/grub && sudo update-grub"
  fi
  echo

  # THE INVARIANT THAT ACTUALLY MATTERS (2026-07-28).
  #
  # A seat only goes graphical if SOMETHING is tagged master-of-seat. On this
  # hardware /usr/lib/udev/rules.d/71-seat.rules offers exactly two routes:
  #     rules 23/28  fb[0-9]        only when nomodeset is on the cmdline
  #     rule 35      drm card[0-9]* needs a KMS driver actually bound
  # Checking nomodeset ALONE misses the case that shipped: no nomodeset AND
  # every KMS driver blacklisted, which closes both routes at once. The install
  # then boots perfectly, reports zero failed units, and shows nothing, because
  # sddm sits at "Logind interface found" forever waiting for a graphical seat.
  #
  # Either route alone is fine. Neither is fatal, and it is invisible without
  # this check.
  _blacklisted=""
  for _m in nouveau amdgpu i915 radeon nvidia; do
    if grep -rqE "^[[:space:]]*blacklist[[:space:]]+${_m}([[:space:]]|$)" \
         /etc/modprobe.d/ 2>/dev/null; then
      _blacklisted="${_blacklisted} ${_m}"
    fi
  done
  echo "-- graphical seat (can anything be tagged master-of-seat?) --"
  [ -n "${_blacklisted}" ] && echo "  KMS drivers blacklisted:${_blacklisted}"
  # A DRM node existing right now is only meaningful on a booted system; during
  # d-i this reflects the INSTALLER's kernel, not the target's. Report it, but
  # let the cmdline+blacklist pair drive the verdict.
  if [ -e /dev/dri ]; then
    echo "  /dev/dri present in this environment: $(ls /dev/dri 2>/dev/null | tr '\n' ' ')"
  else
    echo "  /dev/dri absent in this environment"
  fi
  # On the DRM route the GPU driver IS the seat, so a blacklist that stops it
  # binding is the whole failure — and nouveau being blacklisted is EXPECTED
  # there (the NVIDIA driver does it deliberately), so it must not be counted
  # against us. What matters is whether the nvidia module can load.
  if [ "${_route}" = drm ]; then
    _nvidia_blocked=no
    case " ${_blacklisted} " in *" nvidia "*) _nvidia_blocked=yes ;; esac
    if [ "${_has_want}" = no ] || [ "${_nvidia_blocked}" = yes ]; then
      echo "  PROBLEM: no route to a graphical seat."
      [ "${_has_want}" = no ] && \
        echo "           ${_want} is absent, so no DRM device is registered"
      [ "${_nvidia_blocked}" = yes ] && \
        echo "           the nvidia module is BLACKLISTED, so it cannot bind"
      echo "           => no master-of-seat device => logind CanGraphical=no"
      echo "           => Wayland-only Plasma has NO session it can start."
      echo "           Fix: put ${_want} on the cmdline and make sure the"
      echo "           NVIDIA driver is installed and not blacklisted."
    else
      echo "  OK: ${_want} set and nvidia is free to bind (udev rule 35)"
      echo "      note: nouveau being blacklisted here is expected and correct"
    fi
  elif [ "${_has_nomodeset}" = no ] && [ -n "${_blacklisted}" ]; then
    echo "  PROBLEM: no route to a graphical seat."
    echo "           nomodeset is absent AND these KMS drivers are blacklisted:${_blacklisted}"
    echo "           => no master-of-seat device => logind CanGraphical=no"
    echo "           => sddm waits forever, no error, no Xorg.0.log, DARK SCREEN."
    echo "           This is the 2026-07-28 failure exactly. Fix either side:"
    echo "             sudo sh /opt/sovereign-os/scripts/install/persist-kernel-cmdline.sh"
    echo "           or un-blacklist the GPU driver in /etc/modprobe.d/."
  else
    echo "  OK: at least one route to a graphical seat exists"
  fi
  echo
  echo "  verify on the booted system with:"
  echo "    loginctl show-seat seat0 -p CanGraphical    # must be yes"
  echo

  echo "-- display manager --"
  dm=$(readlink /etc/systemd/system/display-manager.service 2>/dev/null || true)
  [ -n "${dm}" ] && echo "  ${dm}" || echo "  PROBLEM: none registered -- nothing starts a session"
  # WHICH display manager, not just whether one exists.
  #
  # A full Ubuntu install passed every other check here and still booted to a
  # blinking cursor on black, because display-manager.service pointed at gdm3:
  # the image is built from the Ubuntu DESKTOP ISO (GNOME base), and
  # `systemctl enable sddm` cannot take that alias from a package that already
  # owns it. gdm3 wants a DRM device for its Wayland greeter and nomodeset is
  # exactly what removes one, so it never starts (2026-07-29).
  #
  # sddm on X11/fbdev is the configuration PROVEN on this hardware.
  case "${dm}" in
    *gdm*)
      if grep -qE "^[[:space:]]*linux.*[[:space:]]nomodeset([[:space:]]|$)" \
           /boot/grub/grub.cfg 2>/dev/null; then
        echo "  PROBLEM: gdm3 is the display manager AND nomodeset is set."
        echo "           gdm3 needs a DRM device for its Wayland greeter; nomodeset"
        echo "           removes it, so gdm3 never starts -> cursor on a black screen."
        echo "           fix: sudo sh /opt/sovereign-os/scripts/install/select-display-manager.sh sddm"
      else
        echo "  NOTE: gdm3 is the display manager (sddm is the proven config here)"
      fi ;;
    *sddm*) echo "  OK: sddm -- the display manager proven on this hardware" ;;
  esac
  echo

  # Session type vs nomodeset. KWin's WAYLAND session needs a DRM device;
  # nomodeset removes exactly that, so a Wayland login cannot start and loops
  # back to the greeter, while X11-on-fbdev works. The operator's proven machine
  # carries NO sddm config at all and lands on X11 — so nothing here pins the
  # session, deliberately. Record what is available, so a login loop is
  # diagnosable in one look instead of another day (2026-07-27).
  # nomodeset and the NVIDIA DRM driver are mutually exclusive. If BOTH appear
  # the machine will not use the driver it just installed, and the symptom
  # (framebuffer graphics, no acceleration) looks like the driver failed rather
  # than like a cmdline conflict (2026-07-27).
  # Same recovery-entry trap as above: GRUB's recovery menuentry carries
  # nomodeset by construction, so comparing raw greps flags a CONFLICT on a
  # correct Ubuntu install (2026-07-29).
  if [ "${_has_want}" = yes ] && [ "${_route}" = drm ] && [ "${_has_nomodeset}" = yes ]; then
    echo "-- CONFLICT --"
    echo "  both nomodeset AND nvidia-drm.modeset=1 are on the kernel line."
    echo "  They are mutually exclusive: nomodeset wins and the NVIDIA driver"
    echo "  will not drive the display. Remove nomodeset:"
    echo "    sudo sed -i 's/\\bnomodeset\\b//g' /etc/default/grub && sudo update-grub"
    echo
  fi

  echo "-- desktop sessions --"
  echo "  X11     : $(ls /usr/share/xsessions/ 2>/dev/null | tr '\n' ' ')"
  echo "  Wayland : $(ls /usr/share/wayland-sessions/ 2>/dev/null | tr '\n' ' ')"
  if [ -n "$(ls /usr/share/wayland-sessions/ 2>/dev/null)" ] \
     && grep -qE "^[[:space:]]*linux.*nomodeset" /boot/grub/grub.cfg 2>/dev/null; then
    echo "  NOTE: a Wayland session is offered but nomodeset is on. KWin/Wayland"
    echo "        needs a DRM device that nomodeset prevents — if the greeter"
    echo "        loops back after entering a password, pick the X11 session."
  fi
  echo "  sddm config: $(ls /etc/sddm.conf.d/*.conf /etc/sddm.conf 2>/dev/null | tr '\n' ' ')"
  echo "  sddm last  : $(grep -hE "^Session=" /var/lib/sddm/state.conf 2>/dev/null || echo "(none recorded)")"
  echo

  echo "-- module blacklists --"
  ls /etc/modprobe.d/sovereign-blacklist-* 2>/dev/null || echo "  none"
  echo

  echo "-- packages --"
  for p in sddm plasma-desktop xserver-xorg-core xserver-xorg-video-fbdev \
           xserver-xorg-video-vesa "$(target_firmware_package)" sovereign-os-cockpit; do
    if dpkg -s "${p}" >/dev/null 2>&1; then
      echo "  ok      ${p}"
    else
      echo "  MISSING ${p}"
    fi
  done
  echo

  echo "-- kernels --"
  ls /boot/vmlinuz-* 2>/dev/null || echo "  none"
  # WHICH one boots. A desktop install pulls in Debian's stock kernel
  # (6.12.96+deb13) alongside the custom znver5 build (6.12.0), and GRUB sorts
  # 6.12.96 ABOVE 6.12.0 -- so without a working pin the whole custom-kernel
  # build is unused. set-grub-default-kernel.sh writes saved_entry into grubenv;
  # listing the kernels present says nothing about which one is chosen.
  echo "  GRUB_DEFAULT : $(grep -m1 "^GRUB_DEFAULT=" /etc/default/grub 2>/dev/null || echo "unset")"
  if [ -f /boot/grub/grubenv ]; then
    echo "  saved_entry  : $(grep -m1 "^saved_entry=" /boot/grub/grubenv 2>/dev/null || echo "none -- GRUB boots the FIRST menu entry")"
  else
    echo "  saved_entry  : no grubenv"
  fi
  echo

  # Does sovereign-os itself exist on this machine, or is it just Debian+KDE?
  # The cockpit postinst runs install-gui-dashboards.sh behind `|| true`, so a
  # total failure there is invisible: the install still "succeeds" and the
  # operator gets a desktop with no sovereign-os in it (2026-07-26).
  # Sources are useless without a network, and the two managers can fight.
  # d-i's netcfg writes an interface stanza into /etc/network/interfaces when it
  # configured a link; NetworkManager then marks that device UNMANAGED, so the
  # desktop cannot change networks and Wi-Fi is unreachable. The operator's
  # working Debian 13 has only `lo` there and lets NM own the rest. Report the
  # truth rather than guess at it (2026-07-27).
  # Secure Boot vs an unsigned custom kernel. The profile declares
  # secure_boot=signed, but step 08 skips MOK signing for the ISO artifact (the
  # disc rides Debian's signed shim/grub chain) and the znver5 kernel .deb
  # carries no signature table at all. That is fine while SB is off -- it is off
  # on this hardware, in Setup Mode -- and becomes an unbootable machine the day
  # somebody turns it on, with nothing to explain why (2026-07-27).
  echo "-- secure boot --"
  if [ -d /sys/firmware/efi ]; then
    _sb=$(mokutil --sb-state 2>/dev/null | head -1)
    if [ -z "${_sb}" ]; then
      # No mokutil: read the EFI variable directly. Its last byte is 1 when
      # Secure Boot is enabled. A diagnostic must not go blind because a
      # convenience tool is missing.
      _sbvar=$(od -An -t u1 /sys/firmware/efi/efivars/SecureBoot-* 2>/dev/null \
                 | tr -s " " | tail -1 | awk "{print \$NF}")
      case "${_sbvar}" in
        1) _sb="SecureBoot enabled (read from efivars)" ;;
        0) _sb="SecureBoot disabled (read from efivars)" ;;
        *) _sb="unknown (no mokutil, efivars unreadable)" ;;
      esac
    fi
    echo "  state: ${_sb}"
    case "${_sb}" in
      *enabled*)
        echo "  NOTE: the custom znver5 kernel is UNSIGNED. With Secure Boot on it"
        echo "        will not load; enroll a MOK or boot the stock Debian kernel."
        ;;
    esac
  else
    echo "  legacy/BIOS boot -- Secure Boot does not apply"
  fi
  echo

  # These workarounds were chosen for ONE machine. On different hardware they
  # are not neutral: nomodeset disables KMS, and blacklisting amdgpu/nouveau
  # turns off a GPU driver that might work perfectly well there. The system
  # still boots -- on the EFI framebuffer -- but with no acceleration and no
  # external-display switching. Say so, rather than let it look like a fault
  # (2026-07-27, operator testing on a second machine).
  echo "-- hardware workarounds active (tuned for the sain-01 box) --"
  _bl="$(ls /etc/modprobe.d/sovereign-blacklist-*.conf 2>/dev/null | wc -l)"
  echo "  blacklisted GPU modules: ${_bl}"
  if grep -qE "^[[:space:]]*linux.*nomodeset" /boot/grub/grub.cfg 2>/dev/null; then
    echo "  nomodeset: ON (KMS disabled -- framebuffer graphics only)"
  fi
  if [ "${_bl}" -gt 0 ] || grep -qE "^[[:space:]]*linux.*nomodeset" /boot/grub/grub.cfg 2>/dev/null; then
    echo "  NOTE: on hardware whose GPU driver DOES bind, these cost you"
    echo "        acceleration for no benefit. To undo on this machine:"
    echo "          rm /etc/modprobe.d/sovereign-blacklist-*.conf"
    echo "          edit GRUB_CMDLINE_LINUX_DEFAULT in /etc/default/grub, update-grub"
  fi
  echo

  echo "-- networking (who owns the interface?) --"
  echo "  /etc/network/interfaces (non-comment):"
  grep -vE "^\s*#|^\s*$" /etc/network/interfaces 2>/dev/null | sed 's/^/    /' \
    || echo "    (file absent)"
  if [ -e /etc/systemd/system/multi-user.target.wants/NetworkManager.service ]; then
    echo "  NetworkManager: enabled"
  else
    echo "  NetworkManager: NOT enabled"
  fi
  if grep -qE "^\s*(auto|iface)\s+(en|wl)" /etc/network/interfaces 2>/dev/null; then
    echo "  NOTE: an interface is claimed by ifupdown. Networking will work, but"
    echo "        NetworkManager will show it as unmanaged and the desktop cannot"
    echo "        switch networks or join Wi-Fi."
  fi
  echo

  echo "-- apt sources (can this system install anything, ever?) --"
  # Look for BOTH formats, on BOTH distros.
  #
  # This grepped only /etc/apt/sources.list for deb.debian.org, and so reported
  # "no network apt sources" on a perfectly healthy Ubuntu install: Ubuntu 26.04
  # ships deb822 (/etc/apt/sources.list.d/ubuntu.sources) and leaves
  # sources.list a 70-byte stub. A false alarm in the operator's motd is not
  # free — it trains them to ignore the report that matters (2026-07-29).
  # Grep only files that EXIST. `grep -q a_file a_missing_glob` returns 2 even
  # when a_file matched, so passing an unmatched glob makes the whole check
  # report failure — which on Debian (no sources.list.d/*.list) would have
  # turned a fix for one false positive into another (2026-07-29).
  _apt_ok=no
  for _f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list; do
    [ -f "${_f}" ] || continue
    if grep -qE "^deb .*(deb\.debian\.org|security\.debian\.org|archive\.ubuntu\.com|security\.ubuntu\.com|ports\.ubuntu\.com)" \
         "${_f}" 2>/dev/null; then
      _apt_ok=yes; break
    fi
  done
  # deb822: `URIs: http://…` inside a *.sources stanza (Ubuntu 26.04's default).
  if [ "${_apt_ok}" = no ]; then
    for _f in /etc/apt/sources.list.d/*.sources; do
      [ -f "${_f}" ] || continue
      if grep -qE "^URIs:.*(debian\.org|ubuntu\.com)" "${_f}" 2>/dev/null; then
        _apt_ok=yes; break
      fi
    done
  fi
  if [ "${_apt_ok}" = yes ]; then
    echo "  OK: network sources present"
  else
    echo "  PROBLEM: no network apt sources -- apt install will fail and no"
    echo "           security update will ever arrive"
    echo "           fix: sudo sh /opt/sovereign-os/scripts/install/write-apt-sources.sh"
  fi
  echo

  echo "-- sovereign-os itself --"
  # The dashboards deploy is the difference between "Debian + KDE" and a
  # sovereign-os. It cannot abort the install, so its outcome is recorded
  # instead — say so plainly here rather than let a silent no-op look like
  # success (2026-07-27).
  _dstat="$(cat /var/lib/sovereign-os/dashboards-install.status 2>/dev/null || echo "not recorded")"
  case "${_dstat}" in
    ok) echo "  dashboards deploy: ok" ;;
    *)  echo "  dashboards deploy: ${_dstat}  <-- PROBLEM"
        echo "    log: /var/log/sovereign-os/dashboards-install.log"
        echo "    fix: sudo SOVEREIGN_OS_SRC=/opt/sovereign-os \\"
        echo "           SOVEREIGN_OS_FRONTEND=kde-plasma \\"
        echo "           bash /opt/sovereign-os/scripts/install/install-gui-dashboards.sh"
        ;;
  esac
  if [ -L /usr/local/lib/sovereign-os ]; then
    echo "  app tree: SYMLINK -> $(readlink /usr/local/lib/sovereign-os)"
    echo "    (the dashboards deploy did not run; units resolve via the fallback)"
  elif [ -d /usr/local/lib/sovereign-os ]; then
    echo "  app tree: deployed at /usr/local/lib/sovereign-os"
  else
    echo "  app tree: MISSING -- every unit ExecStarting from there will fail"
  fi
  # 68 units exec from that path and 67 carry Restart=; a missing path means
  # dozens of services failing and restarting forever.
  echo "  units present : $(ls /lib/systemd/system/sovereign-*.service 2>/dev/null | wc -l)"
  echo "  units enabled : $(ls /etc/systemd/system/*.wants/sovereign-*.service 2>/dev/null | wc -l)"
  echo "  dashboards hub:"
  for u in sovereign-dashboards.service sovereign-master-dashboard-api.service; do
    if [ -e "/etc/systemd/system/multi-user.target.wants/${u}" ]; then
      echo "    enabled  ${u}"
    else
      echo "    off      ${u}"
    fi
  done
} > "${OUT}" 2>&1

# SURFACE IT. The report is only useful if the operator learns it exists. A
# first install that went wrong otherwise presents as a symptom — a dark screen,
# a missing cockpit — with the explanation sitting unread in /var/log. Put the
# problems (and only the problems) where any login sees them (2026-07-27).
_problems="$(grep -cE "PROBLEM|MISSING|FAILED|CONFLICT" "${OUT}" 2>/dev/null || echo 0)"
_motd=/etc/motd.d/50-sovereign-install
mkdir -p /etc/motd.d 2>/dev/null || true
if [ "${_problems}" -gt 0 ] 2>/dev/null; then
  {
    echo
    echo "  sovereign-os: the install self-check found ${_problems} problem(s)."
    echo "  Full report:  ${OUT}"
    echo "  Or run:       sovereign-osctl install logs"
    echo
    grep -E "PROBLEM|MISSING|FAILED|CONFLICT" "${OUT}" 2>/dev/null | head -8 | sed 's/^/    /'
    echo
  } > "${_motd}" 2>/dev/null || true
else
  # A clean install must not leave a stale warning from a previous one.
  rm -f "${_motd}" 2>/dev/null || true
fi

exit 0
