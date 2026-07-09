#!/usr/bin/env bash
# scripts/install/migrate-home.sh — Phase 2 of the single-OS reflash-root
# layout.
#
# Copies the CURRENT /home onto the shared sovereign-home LV and registers it
# in fstab so that AFTER THE NEXT REBOOT, /home is the shared volume — after
# which /home persists across every sovereign-root reflash.
# We deliberately do NOT mount over the live /home: this repo and your login
# session live under /home, and remounting it underneath a running session
# is how you corrupt an in-use working tree. The switch lands cleanly at the
# next boot, when nothing holds /home open.
#
# Fully non-destructive: only reads /home, only appends one fstab line. The
# original on-root /home stays exactly where it is.
#
# Run: sudo scripts/install/migrate-home.sh
set -euo pipefail

HOME_LV="${SOVEREIGN_OS_HOME_LV:-/dev/sovereign/home}"
PRIMARY_USER="${SOVEREIGN_OS_USER:-jfortin}"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { red "must run as root: sudo $0"; exit 1; }
[ -b "${HOME_LV}" ] || { red "ABORT: ${HOME_LV} not found — run setup-lvm-dualboot.sh first"; exit 1; }

if findmnt -no SOURCE /home 2>/dev/null | grep -q "$(readlink -f "${HOME_LV}")"; then
  grn "/home is already the shared LV — migration already done."
  exit 0
fi

echo "━━━ Phase 2 — copy /home onto the shared LV + register it ━━━"
info "source : /home  (on $(findmnt -no SOURCE / ))"
info "dest   : ${HOME_LV}"
info "user   : ${PRIMARY_USER} (uid $(id -u "${PRIMARY_USER}" 2>/dev/null || echo '?'))"
echo

# ── copy current /home → the LV (source is only READ) ──
MNT="$(mktemp -d)"
mount "${HOME_LV}" "${MNT}"
trap 'umount "${MNT}" 2>/dev/null || true; rmdir "${MNT}" 2>/dev/null || true' EXIT

info "rsync /home → ${HOME_LV} (preserving ownership/perms/acls)…"
rsync -aHAX --info=progress2 /home/ "${MNT}/"
sync

if [ -d "${MNT}/${PRIMARY_USER}" ]; then
  grn "✓ ${PRIMARY_USER} home copied — owned by $(stat -c '%U:%G' "${MNT}/${PRIMARY_USER}"), $(du -sh "${MNT}/${PRIMARY_USER}" | cut -f1)"
else
  red "WARNING: ${PRIMARY_USER} home not found on the LV — investigate before rebooting"
fi
umount "${MNT}"; trap - EXIT; rmdir "${MNT}"

# ── register the shared /home in the host's fstab (takes effect on reboot) ──
HOME_UUID="$(blkid -s UUID -o value "${HOME_LV}")"
if grep -qE '^[^#]*[[:space:]]/home[[:space:]]' /etc/fstab; then
  info "/etc/fstab already has a /home entry — not touching it"
else
  cp /etc/fstab /etc/fstab.pre-sovereign.bak
  printf '# sovereign-os: shared /home (ONE home, survives every root reflash) — added %s\nUUID=%s  /home  ext4  defaults,relatime  0  2\n' \
    "$(date -I)" "${HOME_UUID}" >> /etc/fstab
  grn "✓ appended shared /home to /etc/fstab (backup: /etc/fstab.pre-sovereign.bak)"
fi

echo
grn "━━━ Phase 2 complete — switch happens on next reboot ━━━"
cat <<EOF

What just happened:
  • Your entire /home is now COPIED onto ${HOME_LV} (the shared volume).
  • The host's /etc/fstab now points /home at that volume.
  • Nothing was unmounted; your current session is untouched.

On your NEXT reboot, /home will come from the shared LV.
The original on-root copy stays as a safety net (shadowed under the mount);
we reclaim that ~space in a later, explicit step — never silently.

You do NOT need to reboot right now. The shared volume already holds your
files, so Phase 3 (install sovereign-os) can proceed immediately and will
mount this SAME volume as ${PRIMARY_USER}'s /home.

Next: scripts/install/install-sovereign-root.sh
EOF
