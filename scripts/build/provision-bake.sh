#!/bin/bash
# scripts/build/provision-bake.sh — BUILD-TIME provisioner. Runs INSIDE the
# image during the mkosi postinst (chroot, root, network available), AFTER the
# repo / selfdef / root-ghostproxy trees have been staged into the image and
# the dev-tools / selfdef bake blocks have run. Turns the lean root-only base
# OS into a prepacked SAIN-01: an operator account, the sovereign-os repo in
# place + connected to git, the scoped operator sudoers, the root-ghostproxy
# endpoint envelope, the dashboards hub, and the first-boot hardware automation.
#
# Driven by profiles/<id>.yaml `provisioning:` (mkosi-emit exports the values as
# env). Posture 'installed-off' (default) installs the security daemons but does
# NOT start them — the operator flips them on (SDD CONFIRM gates preserved).
#
# NON-FATAL BY DESIGN: `set -uo pipefail` (no -e) and every step ends in
# `|| log ...` — a provisioning hiccup must never brick the image build (the
# kernel install already exited 1 earlier if it truly failed).
set -uo pipefail
shopt -s nullglob
# useradd/getent/chpasswd live in /usr/sbin — guarantee they're on PATH
# regardless of what the postinst inherited.
export PATH="/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
log() { echo "provision-bake: $*" >&2; }

REPO="${SOVEREIGN_OS_IMAGE_REPO:-/opt/sovereign-os}"
OPERATOR="${SOVEREIGN_OS_OPERATOR_USER:-operator}"
OPERATOR_GROUPS="${SOVEREIGN_OS_OPERATOR_GROUPS:-sudo,podman,render,video,adm}"
OPERATOR_SHELL="${SOVEREIGN_OS_OPERATOR_SHELL:-/bin/bash}"
HOME_REPO="${SOVEREIGN_OS_OPERATOR_HOME_REPO:-sovereign-os}"
POSTURE="${SOVEREIGN_OS_POSTURE:-installed-off}"
ORIGIN_URL="${SOVEREIGN_OS_GIT_ORIGIN:-https://github.com/cyberpunk042/sovereign-os}"

log "starting — operator=${OPERATOR} posture=${POSTURE} repo=${REPO}"

# ── 0. state/config dirs the first-boot units + hooks need ────────────────
# Their ReadWritePaths= reference these; a missing dir makes systemd fail the
# unit at mount-namespace setup (status=226/NAMESPACE) BEFORE the hook runs —
# that was the "8 FAILED first-boot units" the operator saw. Create the ones we
# own so the sandbox can be built. (Hardware units additionally skip on VMs via
# ConditionVirtualization=no; these dirs make the generic ones — firstboot
# completion marker, workstation-shell — succeed everywhere.)
mkdir -p /var/lib/sovereign-os /var/log/sovereign-os /etc/bash.bashrc.d 2>/dev/null \
  && log "state dirs ensured (/var/lib/sovereign-os · /var/log/sovereign-os · /etc/bash.bashrc.d)" \
  || log "state-dir creation hiccup (non-fatal)"

# ── 1. operator user ─────────────────────────────────────────────────────
if id "${OPERATOR}" >/dev/null 2>&1; then
  log "operator '${OPERATOR}' already exists"
else
  # only request groups that actually exist in the image
  grps=""
  IFS=',' read -ra _G <<< "${OPERATOR_GROUPS}"
  for g in "${_G[@]}"; do getent group "${g}" >/dev/null 2>&1 && grps="${grps:+${grps},}${g}"; done
  # -N (no user-private group): Debian reserves an 'operator' GROUP (gid 37),
  # so the default useradd (which creates a same-named group) aborts RC=9. -N
  # uses the default group ('users') instead. Verified in the emulator.
  if useradd -m -N -s "${OPERATOR_SHELL}" ${grps:+-G "${grps}"} "${OPERATOR}"; then
    log "created operator '${OPERATOR}' (uid $(id -u "${OPERATOR}" 2>/dev/null), groups: ${grps:-none})"
  else
    log "useradd '${OPERATOR}' failed (non-fatal)"
  fi
fi
# password = root's (copy the hash — no plaintext needed) unless opted out
if [ "${SOVEREIGN_OS_OPERATOR_PASSWORD_FROM_ROOT:-1}" = "1" ] && id "${OPERATOR}" >/dev/null 2>&1; then
  rh="$(getent shadow root | cut -d: -f2)"
  if [ -n "${rh}" ] && [ "${rh}" != "!" ] && [ "${rh}" != "*" ]; then
    echo "${OPERATOR}:${rh}" | chpasswd -e 2>/dev/null \
      && log "operator password set (= root's)" || log "chpasswd failed (non-fatal)"
  else
    log "root has no usable password hash — operator left password-less (SSH/console per your keys)"
  fi
fi
OPHOME="$(getent passwd "${OPERATOR}" 2>/dev/null | cut -d: -f6)"; OPHOME="${OPHOME:-/home/${OPERATOR}}"

# ── 2. repo in place + connected to git ──────────────────────────────────
if [ -d "${REPO}" ]; then
  ln -sfn "${REPO}" "${OPHOME}/${HOME_REPO}" 2>/dev/null || true
  chown -h "${OPERATOR}:${OPERATOR}" "${OPHOME}/${HOME_REPO}" 2>/dev/null || true
  ln -sfn "${REPO}" /usr/local/lib/sovereign-os 2>/dev/null || true   # dashboards resolve REPO here
  if [ -d "${REPO}/.git" ] && command -v git >/dev/null 2>&1; then
    git config --global --add safe.directory "${REPO}" 2>/dev/null || true
    git -C "${REPO}" remote set-url origin "${ORIGIN_URL}" 2>/dev/null \
      || git -C "${REPO}" remote add origin "${ORIGIN_URL}" 2>/dev/null || true
    runuser -u "${OPERATOR}" -- git config --global --add safe.directory "${REPO}" 2>/dev/null || true
    log "repo → ${OPHOME}/${HOME_REPO} · origin ${ORIGIN_URL} · $(git -C "${REPO}" rev-parse --short HEAD 2>/dev/null || echo '?')"
  else
    log "repo present at ${REPO} (no .git — not git-connected)"
  fi
else
  log "repo NOT staged at ${REPO} — skipping repo/dashboards/firstboot wiring that depends on it"
fi

# ── 2b. make ~/selfdef + ~/root-ghostproxy resolve to the /opt trees ──────
# `sovereign-osctl selfdef {install-units,on}` defaults SOVEREIGN_OS_SELFDEF_DIR
# to $HOME/selfdef; the ghostproxy verify/sync hooks look under $HOME too. The
# staged trees live in /opt, so symlink them into both the operator's and
# root's home — then turning selfdef on (as either user) just works.
for _u in "${OPERATOR}" root; do
  _h="$(getent passwd "${_u}" 2>/dev/null | cut -d: -f6)"; _h="${_h:-/root}"
  [ -d /opt/selfdef ] && { ln -sfn /opt/selfdef "${_h}/selfdef" 2>/dev/null; chown -h "${_u}:" "${_h}/selfdef" 2>/dev/null || true; }
  [ -d /opt/root-ghostproxy ] && { ln -sfn /opt/root-ghostproxy "${_h}/root-ghostproxy" 2>/dev/null; chown -h "${_u}:" "${_h}/root-ghostproxy" 2>/dev/null || true; }
done
[ -d /opt/selfdef ] && log "selfdef linked into ~${OPERATOR} + ~root (turn on: sovereign-osctl selfdef install-units && selfdef on)"

# ── 3. scoped operator sudoers (NOPASSWD for the diagnostic/ops allow-list) ─
if [ -x "${REPO}/scripts/operator/operator-sudoers.sh" ]; then
  SOVEREIGN_OS_OPERATOR_USER="${OPERATOR}" "${REPO}/scripts/operator/operator-sudoers.sh" --install 2>&1 \
    | sed 's/^/provision-bake:   /' >&2 || log "operator-sudoers install failed (non-fatal)"
fi

# ── 4. root-ghostproxy endpoint envelope (installed, NOT started) ─────────
if [ "${SOVEREIGN_OS_BAKE_GHOSTPROXY:-}" = "1" ] && [ -d /opt/root-ghostproxy ]; then
  chown -R "${OPERATOR}:${OPERATOR}" /opt/root-ghostproxy 2>/dev/null || true
  if [ -x /opt/root-ghostproxy/install.sh ]; then
    log "installing root-ghostproxy (endpoint mode, no bridge/wifi) as ${OPERATOR}"
    runuser -u "${OPERATOR}" -- /opt/root-ghostproxy/install.sh --mode endpoint --no-bridge --no-wifi 2>&1 \
      | sed 's/^/provision-bake:   /' >&2 || log "root-ghostproxy install failed (non-fatal — provision post-flash)"
  else
    log "/opt/root-ghostproxy/install.sh absent — skipping"
  fi
fi

# ── 5. dashboards hub (enable so the panels are up on boot) ───────────────
if [ "${SOVEREIGN_OS_BAKE_DASHBOARDS:-}" = "1" ] && [ -d "${REPO}/systemd/system" ]; then
  for unit in sovereign-dashboards.service sovereign-master-dashboard-api.service; do
    if [ -f "${REPO}/systemd/system/${unit}" ]; then
      install -m 644 "${REPO}/systemd/system/${unit}" /etc/systemd/system/ 2>/dev/null || true
      systemctl enable "${unit}" 2>/dev/null && log "enabled ${unit}" || log "enable ${unit} failed (non-fatal)"
    fi
  done
fi

# ── 6. first-boot hardware automation (installs + enables the target) ─────
# The wired first-boot units (ConditionFirstBoot=yes) run the hardware-specific
# setup on the real machine's first boot: vfio-bind, network-vlan, tetragon
# policy, zfs ARC clamp, driver bind, workstation shell. Install the explicit
# set (never the -api / sync / kms / this-run units) + enable the target.
if [ "${SOVEREIGN_OS_BAKE_FIRSTBOOT:-}" = "1" ] && [ -d "${REPO}/systemd/system" ]; then
  mkdir -p /etc/sovereign-os
  printf 'SOVEREIGN_OS_PROFILE=%s\nSOVEREIGN_OS_REPO=%s\n' \
    "${SOVEREIGN_OS_PROFILE:-sain-01}" "${REPO}" > /etc/sovereign-os/active-profile.env
  FB_UNITS=(sovereign-firstboot.target sovereign-firstboot.service
            sovereign-friction-audit.service sovereign-vfio-bind.service
            sovereign-network-vlan.service sovereign-tetragon-policy-load.service
            sovereign-zfs-arc-clamp.service sovereign-nvidia-driver-bind.service
            sovereign-workstation-shell-setup.service)
  n=0
  for u in "${FB_UNITS[@]}"; do
    if [ -f "${REPO}/systemd/system/${u}" ]; then
      install -m 644 "${REPO}/systemd/system/${u}" /etc/systemd/system/ 2>/dev/null && n=$((n+1)) || true
    fi
  done
  if systemctl enable sovereign-firstboot.target 2>/dev/null; then
    log "first-boot automation installed (${n} units) + target enabled"
  else
    log "first-boot target enable failed (non-fatal) — ${n} units installed"
  fi
fi

# ── 7. UPS / power (APC Smart-UPS SMT2200C SmartConnect, graceful shutdown) ─
# Arms the graceful-shutdown guard (power.toml) + lays down the NUT base config.
# The correct client for a SmartConnect Smart-UPS is NUT + the apc_modbus driver
# (Modbus over TCP :502 on the embedded SmartConnect Ethernet port, OR Modbus
# RTU / serial over the DSD TECH USB→RJ50 cable); native USB-HID falls back to
# usbhid-ups. The ups-apc-setup first-boot hook DETECTS the transport, writes the
# working ups.conf, verifies comms with upsc, and enables the daemons on real
# hardware (skipped on VMs — no UPS in a guest).
if [ "${SOVEREIGN_OS_UPS:-}" = "1" ]; then
  SHUT_MIN="${SOVEREIGN_OS_UPS_SHUTDOWN_MIN:-30}"
  # (a) arm the sovereign graceful-shutdown guard via power.toml
  mkdir -p /etc/sovereign-os
  [ -f /etc/sovereign-os/power.toml ] || { [ -f "${REPO}/config/power.toml.example" ] && cp "${REPO}/config/power.toml.example" /etc/sovereign-os/power.toml; }
  if [ -f /etc/sovereign-os/power.toml ]; then
    [ "${SOVEREIGN_OS_UPS_ARM:-}" = "1" ] && sed -i -E 's|^[#[:space:]]*enabled[[:space:]]*=.*|enabled = true|' /etc/sovereign-os/power.toml
    sed -i -E "s|^[#[:space:]]*shutdown_minutes[[:space:]]*=.*|shutdown_minutes = ${SHUT_MIN}|" /etc/sovereign-os/power.toml
    log "power.toml → graceful soft shutdown armed at runtime < ${SHUT_MIN} min"
  fi
  # persist the UPS transport hints for the first-boot hook (read via the unit's
  # EnvironmentFile). Optional host pins the SmartConnect IP (else the hook scans).
  {
    printf '# sovereign-os — UPS transport hints for ups-apc-setup (first boot)\n'
    [ -n "${SOVEREIGN_OS_UPS_HOST:-}" ] && printf 'SOVEREIGN_OS_UPS_HOST=%s\n' "${SOVEREIGN_OS_UPS_HOST}"
    printf 'SOVEREIGN_OS_UPS_SLAVEID=%s\n' "${SOVEREIGN_OS_UPS_SLAVEID:-1}"
  } > /etc/sovereign-os/ups.env
  # (b) NUT base config (standalone, loopback). The device stanza + daemon enable
  #     are the first-boot hook's job (after it detects the transport). Here we
  #     lay the base down + skip the NUT daemons on VMs.
  if [ -d /etc/nut ]; then
    printf 'MODE=standalone\n' > /etc/nut/nut.conf
    printf '# sovereign-os — loopback only (operator exposes deliberately)\nLISTEN 127.0.0.1 %s\nLISTEN ::1 %s\n' "${SOVEREIGN_OS_NUT_LISTEN_PORT:-3493}" "${SOVEREIGN_OS_NUT_LISTEN_PORT:-3493}" > /etc/nut/upsd.conf
    # placeholder ups.conf — globals only, NO device stanza yet (upsd stays valid
    # + driverless until ups-apc-setup writes the detected transport at first boot).
    printf '# sovereign-os — device stanza written at first boot by ups-apc-setup\nmaxretry = 3\npollinterval = 5\n' > /etc/nut/ups.conf
    for u in nut-server nut-monitor nut-driver-enumerator; do
      mkdir -p "/etc/systemd/system/${u}.service.d"
      printf '[Unit]\n# no UPS in a guest — skip cleanly (real SAIN-01 detects + enables at first boot)\nConditionVirtualization=no\n' > "/etc/systemd/system/${u}.service.d/10-sovereign-vm-skip.conf"
    done
    log "NUT base laid down (apc_modbus/usbhid-ups; standalone, loopback :${SOVEREIGN_OS_NUT_LISTEN_PORT:-3493}); ups-apc-setup detects the transport at first boot"
  else
    log "NUT not installed (/etc/nut absent) — UPS monitoring skipped (needs 'nut-server'+'nut-client' in profile packages)"
  fi
  # (c) install + arm the guard timer + the first-boot setup unit
  for u in sovereign-power-shutdown-guard.service sovereign-power-shutdown-guard.timer sovereign-ups-setup.service; do
    [ -f "${REPO}/systemd/system/${u}" ] && install -m 644 "${REPO}/systemd/system/${u}" /etc/systemd/system/ 2>/dev/null || true
  done
  systemctl enable sovereign-ups-setup.service >/dev/null 2>&1 || true
  if [ "${SOVEREIGN_OS_UPS_ARM:-}" = "1" ]; then
    systemctl enable sovereign-power-shutdown-guard.timer >/dev/null 2>&1 \
      && log "power-shutdown-guard timer armed (minutely; soft shutdown < ${SHUT_MIN} min)" || true
  fi
fi

log "done — operator=${OPERATOR} posture=${POSTURE}"
exit 0
