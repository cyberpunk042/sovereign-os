#!/bin/sh
# Hand the physical NIC(s) from ifupdown to NetworkManager on a desktop install.
#
# WHY. d-i's netcfg writes /etc/network/interfaces with a stanza like
#     allow-hotplug enp11s0
#     iface enp11s0 inet dhcp
# and that CLAIMS the interface for ifupdown. NetworkManager then shows it as
# "unmanaged": the box has working networking, but the KDE applet cannot switch
# networks, join Wi-Fi, or edit a connection — on a machine whose whole point is
# to be an operator workstation. The 2026-07-28 install self-check caught this
# and said so; nothing acted on it (verify-installed-system.sh, "who owns the
# interface?").
#
# WHAT. Comment out the physical-interface stanzas, leave loopback alone, and
# only when NetworkManager is actually present to take over. Idempotent.
#
# SAFETY. Refuses when NetworkManager is absent or disabled — stripping the
# ifupdown config there would leave the machine with NO network at all, which is
# far worse than an unmanaged one. The original file is backed up.
set -eu

IFACES=/etc/network/interfaces
[ "$(id -u)" -eq 0 ] || { echo "must run as root" >&2; exit 1; }
[ -f "${IFACES}" ] || { echo "no ${IFACES} — nothing to hand over"; exit 0; }

# NetworkManager must exist AND be enabled, or we are about to remove the only
# thing configuring the network.
if ! command -v nmcli >/dev/null 2>&1 && [ ! -x /usr/sbin/NetworkManager ]; then
  echo "NetworkManager not installed — leaving ifupdown in charge"; exit 0
fi
if command -v systemctl >/dev/null 2>&1; then
  if ! systemctl is-enabled NetworkManager.service >/dev/null 2>&1; then
    echo "NetworkManager not enabled — leaving ifupdown in charge"; exit 0
  fi
fi

# Physical stanzas only: never touch `lo`, never touch an interface the operator
# configured by hand under interfaces.d/.
claimed="$(awk '/^[[:space:]]*(auto|allow-hotplug)[[:space:]]+/ {for(i=2;i<=NF;i++) if($i!="lo") print $i}
                /^[[:space:]]*iface[[:space:]]+/ {if($2!="lo") print $2}' \
           "${IFACES}" 2>/dev/null | sort -u)"
if [ -z "${claimed}" ]; then
  echo "no physical interface claimed by ifupdown — nothing to do"; exit 0
fi

cp -a "${IFACES}" "${IFACES}.sovereign-bak"
for _if in ${claimed}; do
  # Comment the stanza head and its indented continuation lines.
  awk -v IF="${_if}" '
    BEGIN { inblk = 0 }
    /^[[:space:]]*(auto|allow-hotplug)[[:space:]]/ {
      if ($0 ~ "(^|[[:space:]])" IF "([[:space:]]|$)") { print "# sovereign: handed to NetworkManager -- " $0; next }
    }
    /^[[:space:]]*iface[[:space:]]/ {
      if ($2 == IF) { inblk = 1; print "# sovereign: handed to NetworkManager -- " $0; next }
      inblk = 0
    }
    { if (inblk && $0 ~ /^[[:space:]]+/) { print "# " $0; next } ; inblk = 0; print }
  ' "${IFACES}" > "${IFACES}.new"
  mv "${IFACES}.new" "${IFACES}"
  echo "handed ${_if} to NetworkManager"
done

echo "done — backup at ${IFACES}.sovereign-bak"
echo "  verify after boot:  nmcli device status   (should NOT say 'unmanaged')"
