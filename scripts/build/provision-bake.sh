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

# R3 (SDD-999): provisioning is NON-FATAL BY DESIGN for the many OPTIONAL steps
# (dashboards, GUI, live-reload, gatewayd, ghostproxy, UPS, node-exporter, config
# defaults…) — a hiccup there must never brick the image build; they degrade and
# are recoverable post-flash. But a few steps are LOAD-BEARING for a usable image:
# if they silently fail the flashed box boots broken (no operator login, or a
# first boot that runs no hardware setup) while the build still reports success.
# `crit` records such a failure so provision-bake exits non-zero at the end
# (failing the mkosi postinst loudly) instead of the blanket `exit 0`, without
# turning every optional hiccup fatal (which `set -e` would wrongly do).
_CRIT_FAILURES=0
crit() { _CRIT_FAILURES=$((_CRIT_FAILURES + 1)); log "CRITICAL: $*"; }

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
if mkdir -p /var/lib/sovereign-os /var/log/sovereign-os /etc/bash.bashrc.d \
           /var/lib/node_exporter/textfile_collector 2>/dev/null; then
  log "state dirs ensured (/var/lib/sovereign-os · /var/log/sovereign-os · /etc/bash.bashrc.d · node_exporter textfile_collector)"
else
  log "state-dir creation hiccup (non-fatal)"
fi
# node_exporter scrapes the textfile collector — enable it so the Layer-B .prom
# metrics every recurrent hook + first-boot unit emits are actually collected.
if [ -f /lib/systemd/system/prometheus-node-exporter.service ] || [ -f /usr/lib/systemd/system/prometheus-node-exporter.service ]; then
  systemctl enable prometheus-node-exporter.service >/dev/null 2>&1 \
    && log "prometheus-node-exporter enabled (scrapes the textfile collector)" \
    || log "node_exporter enable failed (non-fatal)"
fi

# ── 0b. runtime config defaults → /etc/sovereign-os (operator-editable) ─────
# Every config/*.{toml,yaml}.example is a runtime default. Lay each down at
# /etc/sovereign-os/<name> (copy-if-ABSENT — never clobber an operator edit) so
# the operator gets an editable override AND the daemons that resolve
# /etc/sovereign-os/<x> find it on any layout (not only the baked /opt fallback).
# Skips installer-INPUT templates (cloud-init / preseed). power.toml +
# shutdown-manifest.toml are further armed in §7.
if [ -d "${REPO}/config" ]; then
  mkdir -p /etc/sovereign-os
  cn=0
  for ex in "${REPO}"/config/*.toml.example "${REPO}"/config/*.yaml.example "${REPO}"/config/science/*.toml.example; do
    [ -f "${ex}" ] || continue
    dst="/etc/sovereign-os/$(basename "${ex}" .example)"
    if [ ! -e "${dst}" ] && install -m 644 "${ex}" "${dst}" 2>/dev/null; then cn=$((cn+1)); fi
  done
  [ "${cn}" -gt 0 ] && log "config defaults installed to /etc/sovereign-os (${cn} file(s))"
fi

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
    log "useradd '${OPERATOR}' failed"
  fi
fi
# R3: verify the operator account actually exists now — a flashed image with no
# operator login is a broken deliverable (root-console still works, but the
# operator promise is core). Only a genuine absence is critical.
if ! id "${OPERATOR}" >/dev/null 2>&1; then
  crit "operator account '${OPERATOR}' does not exist after provisioning — the flashed image would have no operator login"
fi
# password = root's (copy the hash — no plaintext needed) unless opted out
if [ "${SOVEREIGN_OS_OPERATOR_PASSWORD_FROM_ROOT:-1}" = "1" ] && id "${OPERATOR}" >/dev/null 2>&1; then
  rh="$(getent shadow root | cut -d: -f2)"
  if [ -n "${rh}" ] && [ "${rh}" != "!" ] && [ "${rh}" != "*" ]; then
    if echo "${OPERATOR}:${rh}" | chpasswd -e 2>/dev/null; then
      log "operator password set (= root's)"
    else
      log "chpasswd failed (non-fatal)"
    fi
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

# ── 4b. OpenClaw Node gateway daemon (SDD-705 — installed-off, first-boot install) ──
# OpenClaw needs Node ≥22 + `npm install -g openclaw` — neither reachable at postinst
# (no network in the image build). So the bake here only STAGES the two units; the
# actual install (Node + npm + preconfig → the local endpoint) runs at FIRST BOOT via
# sovereign-openclaw-install.service (network available), non-fatal + resumable. The
# runtime daemon (sovereign-openclaw.service) stays installed-off — `sovereign-osctl
# openclaw on` starts it. Gated on bake.openclaw.
if [ "${SOVEREIGN_OS_BAKE_OPENCLAW:-}" = "1" ]; then
  _oc_n=0
  for u in sovereign-openclaw-install.service sovereign-openclaw.service; do
    if [ -f "${REPO}/systemd/system/${u}" ]; then
      install -m 644 "${REPO}/systemd/system/${u}" /etc/systemd/system/ 2>/dev/null && _oc_n=$((_oc_n+1))
    fi
  done
  # Enable ONLY the first-boot installer (the runtime daemon stays installed-off).
  systemctl enable sovereign-openclaw-install.service >/dev/null 2>&1 \
    && log "OpenClaw staged — ${_oc_n} unit(s); first-boot installer enabled (runtime daemon installed-off; turn on: sovereign-osctl openclaw on)" \
    || log "OpenClaw units staged (${_oc_n}) — installer enable deferred (no running systemd)"
fi

# ── 4c. open-computer QEMU AI-sandbox (SDD-706 — installed-off, first-boot install) ──
# Like OpenClaw: QEMU/KVM + Node + a repo build + a ~3GB base image are unreachable at
# postinst, so the bake only STAGES the two units; the install (qemu/node/clone/build/
# base-image/preconfig) runs at FIRST BOOT via sovereign-open-computer-install.service.
# The runtime daemon (sovereign-open-computer.service) stays installed-off. Gated on
# bake.open_computer.
if [ "${SOVEREIGN_OS_BAKE_OPEN_COMPUTER:-}" = "1" ]; then
  _ocp_n=0
  for u in sovereign-open-computer-install.service sovereign-open-computer.service; do
    if [ -f "${REPO}/systemd/system/${u}" ]; then
      install -m 644 "${REPO}/systemd/system/${u}" /etc/systemd/system/ 2>/dev/null && _ocp_n=$((_ocp_n+1))
    fi
  done
  systemctl enable sovereign-open-computer-install.service >/dev/null 2>&1 \
    && log "open-computer staged — ${_ocp_n} unit(s); first-boot installer enabled (runtime daemon installed-off; turn on: sovereign-osctl open-computer on)" \
    || log "open-computer units staged (${_ocp_n}) — installer enable deferred (no running systemd)"
fi

# ── 5. dashboards hub + panel APIs (dashboards LIVE on boot — ON by default) ──
# The hub (build-configurator) serves every panel's HTML; each panel's live data
# comes from its own read-only sovereign-<x>-api daemon. Enable the hub + master
# dashboard + ALL read-only panel APIs so the dashboards show live data out of the
# box (operator directive: "dashboards running by default"). The privileged
# execution panels (flash/emulate/ups) + the sole write daemon (control-exec) are
# deliberately NOT auto-enabled — they are operator-launched (panel.sh) so their
# privileged actions stay deliberate. Mask any read-only API via
# SOVEREIGN_OS_DASHBOARD_API_SKIP="sovereign-foo-api,...".
if [ "${SOVEREIGN_OS_BAKE_DASHBOARDS:-}" = "1" ] && [ -d "${REPO}/systemd/system" ]; then
  _API_MANAGED="sovereign-flash-api sovereign-emulate-api sovereign-ups-api sovereign-control-exec-api"
  IFS=',' read -ra _ASKIP <<< "${SOVEREIGN_OS_DASHBOARD_API_SKIP:-}"
  dn=0
  for unit in sovereign-dashboards.service sovereign-master-dashboard-api.service; do
    [ -f "${REPO}/systemd/system/${unit}" ] || continue
    install -m 644 "${REPO}/systemd/system/${unit}" /etc/systemd/system/ 2>/dev/null || true
    systemctl enable "${unit}" >/dev/null 2>&1 && dn=$((dn+1))
  done
  for svc in "${REPO}"/systemd/system/sovereign-*-api.service; do
    [ -f "${svc}" ] || continue
    base="$(basename "${svc}" .service)"
    case " ${_API_MANAGED} " in *" ${base} "*) continue;; esac
    _sk=0; for s in "${_ASKIP[@]}"; do [ "${base}" = "${s}" ] && _sk=1; done
    [ "${_sk}" = "1" ] && continue
    install -m 644 "${svc}" /etc/systemd/system/ 2>/dev/null || true
    systemctl enable "${base}.service" >/dev/null 2>&1 && dn=$((dn+1))
  done
  log "dashboards LIVE — hub + ${dn} panel API service(s) enabled (flash/emulate/ups + control-exec stay operator-launched)"
fi

# ── 5b. desktop on the IMAGE (opt-in — bake.gui) ──────────────────────────
# The root-reflash install (install-sovereign-root.sh) ALWAYS installs the GUI;
# for the mkosi appliance image it is opt-in. When bake.gui is set, run
# install-gui-dashboards.sh in the postinst (apt is available here) so the
# flashed image boots straight to a desktop + the dashboards. NON-FATAL — a
# desktop apt hiccup must never brick the image build (it stays headless).
if [ "${SOVEREIGN_OS_BAKE_GUI:-}" = "1" ] && [ -x "${REPO}/scripts/install/install-gui-dashboards.sh" ]; then
  # SDD-704: the profile's provisioning.frontend.default (SOVEREIGN_OS_FRONTEND) picks
  # what the image presents (gnome | dashboards-kiosk | open-computer-kiosk | none);
  # install-gui-dashboards.sh reads it and stages the matching stack. Absent → gnome.
  log "installing frontend on the image (bake.gui=1) — frontend=${SOVEREIGN_OS_FRONTEND:-gnome}, de=${SOVEREIGN_OS_DESKTOP:-gnome}"
  if SOVEREIGN_OS_SRC="${REPO}" SOVEREIGN_OS_DESKTOP="${SOVEREIGN_OS_DESKTOP:-gnome}" \
       SOVEREIGN_OS_FRONTEND="${SOVEREIGN_OS_FRONTEND:-gnome}" \
       SOVEREIGN_OS_FRONTEND_INSTALL="${SOVEREIGN_OS_FRONTEND_INSTALL:-gnome}" \
       bash "${REPO}/scripts/install/install-gui-dashboards.sh" 2>&1 | sed 's/^/provision-bake:   /' >&2; then
    log "desktop installed on the image"
  else
    log "desktop install hiccup (non-fatal — image stays headless; run install-gui-dashboards.sh post-flash)"
  fi
fi

# ── 5c. live-reload on the installed box (SDD-203 — ON by default) ────────
# The operator keeps developing on the LIVE /opt/sovereign-os checkout after
# install (/usr/local/lib/sovereign-os → /opt/sovereign-os). Two moving parts,
# both dev-ergonomic and toggleable off for a locked build (bake.livereload=0):
#   • the broker (sovereign-livereload-broker.service) watches the tree + offers
#     each open panel a refresh when something IT depends on changes — webapp +
#     shelled-script edits already take effect on the next request (the daemons
#     read fresh), so those become a pure refresh;
#   • each enabled panel API is wrapped through reload-run.py via a DROP-IN, so
#     an edit to a daemon's OWN .py re-execs it IN PLACE (same PID, no kill, no
#     systemctl restart). The shipped unit files stay byte-identical — the
#     override lives only in /etc/systemd/system/<unit>.d/livereload.conf.
if [ "${SOVEREIGN_OS_BAKE_LIVERELOAD:-1}" = "1" ] && [ -d "${REPO}/systemd/system" ]; then
  _RR="/usr/local/lib/sovereign-os/scripts/operator/lib/reload-run.py"
  if [ -f "${REPO}/systemd/system/sovereign-livereload-broker.service" ]; then
    install -m 644 "${REPO}/systemd/system/sovereign-livereload-broker.service" \
      /etc/systemd/system/ 2>/dev/null || true
    systemctl enable sovereign-livereload-broker.service >/dev/null 2>&1 || true
  fi
  # Wrap every ENABLED sovereign python service (installed to /etc by §5) in the
  # self-re-exec launcher. Read the ORIGINAL ExecStart script from the installed
  # unit so the override is exact; regenerated each provision (idempotent).
  _lr=0
  for _u in /etc/systemd/system/sovereign-*-api.service \
            /etc/systemd/system/sovereign-dashboards.service; do
    [ -f "${_u}" ] || continue
    _base="$(basename "${_u}")"
    _script="$(grep -oE '/usr/local/lib/sovereign-os/scripts/operator/[a-z0-9-]+\.py' "${_u}" | head -1)"
    [ -n "${_script}" ] || continue
    mkdir -p "/etc/systemd/system/${_base}.d"
    {
      printf '[Service]\n'
      printf 'Environment=SOVEREIGN_OS_LIVERELOAD=1\n'
      printf 'ExecStart=\n'
      printf 'ExecStart=/usr/bin/python3 %s %s\n' "${_RR}" "${_script}"
    } > "/etc/systemd/system/${_base}.d/livereload.conf"
    _lr=$((_lr+1))
  done
  systemctl daemon-reload >/dev/null 2>&1 || true
  log "live-reload ON — broker enabled + ${_lr} service(s) wrapped for in-place self-re-exec (edit /opt/sovereign-os live; bake.livereload=0 to disable)"
fi

# ── 5d. the sovereign brain (intelligence layer) — gatewayd auto-start ────
# When the intelligence layer was staged into the image (bake.intelligence via
# step 07 → /usr/local/bin/sovereign-gatewayd), install + enable its unit so the
# flashed image auto-starts the gateway: it resumes durable memory, and — if a
# model was baked (bake.model → /var/lib/sovereign-os/models/…) — serves the
# OpenAI chat shim so the cockpit chat works out of the box. No model ⇒ it runs
# as a pure decision surface (chat falls back to the tier router). Gated on the
# staged binary so a source-only image never enables a unit with no ExecStart.
if [ "${SOVEREIGN_OS_BAKE_INTELLIGENCE:-}" = "1" ] && [ -f "${REPO}/systemd/system/sovereign-gatewayd.service" ]; then
  if [ -x /usr/local/bin/sovereign-gatewayd ]; then
    install -m 644 "${REPO}/systemd/system/sovereign-gatewayd.service" /etc/systemd/system/ 2>/dev/null || true
    _model="none"
    [ -f /var/lib/sovereign-os/models/smollm-135m/config.json ] && _model="baked"
    if systemctl enable sovereign-gatewayd.service >/dev/null 2>&1; then
      log "sovereign brain LIVE — gatewayd enabled (baked binary; model: ${_model})"
    else
      log "gatewayd enable failed (non-fatal)"
    fi
  else
    log "bake.intelligence=1 but /usr/local/bin/sovereign-gatewayd not staged — gatewayd NOT enabled (check step-07 host build)"
  fi
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
            sovereign-network-vlan.service
            sovereign-tetragon-install.service sovereign-tetragon-policy-load.service
            sovereign-zfs-arc-clamp.service sovereign-nvidia-driver-install.service
            sovereign-nvidia-driver-bind.service
            sovereign-warp-setup.service
            sovereign-workstation-shell-setup.service
            sovereign-inference-model-provision.service)
  n=0
  for u in "${FB_UNITS[@]}"; do
    if [ -f "${REPO}/systemd/system/${u}" ]; then
      if install -m 644 "${REPO}/systemd/system/${u}" /etc/systemd/system/ 2>/dev/null; then n=$((n+1)); fi
    fi
  done
  if systemctl enable sovereign-firstboot.target 2>/dev/null; then
    # R3: verify the enable actually created the wants symlink — an offline
    # `systemctl enable` can no-op silently, and the WHOLE hardware first boot
    # (vfio/nvidia/vlan/zfs/tetragon) hinges on the target being reachable from
    # multi-user.target (the SDD-998 Wants= fix is upstream of this).
    if [ -L /etc/systemd/system/multi-user.target.wants/sovereign-firstboot.target ]; then
      log "first-boot automation installed (${n} units) + target enabled + wants-symlink verified"
    else
      crit "sovereign-firstboot.target enabled but no multi-user.target.wants symlink — first boot would run no hardware setup"
    fi
  else
    crit "first-boot target enable FAILED — the flashed image would boot inert (no vfio/nvidia/vlan/zfs/tetragon); ${n} units installed"
  fi
  # SDD-701: the GPU power-limit unit runs EVERY boot (nvidia-smi -pl is not
  # persistent), so it is enabled at multi-user.target, not a first-boot member.
  if [ -f "${REPO}/systemd/system/sovereign-nvidia-power-limit.service" ]; then
    install -m 644 "${REPO}/systemd/system/sovereign-nvidia-power-limit.service" /etc/systemd/system/ 2>/dev/null || true
    systemctl enable sovereign-nvidia-power-limit.service >/dev/null 2>&1 \
      && log "nvidia power-limit unit enabled (every-boot GPU caps from profile tdp_watts)" \
      || log "nvidia power-limit enable failed (non-fatal)"
  fi
fi

# ── 6b. recurrent maintenance timers (self-maintaining box — ON by default) ──
# Every scripts/hooks/recurrent/*.sh ships a sovereign-<slug>.{service,timer}. On a
# real provisioned machine (firstboot=true) install + enable them ALL so the box
# self-maintains out of the box: zfs-scrub, thermal-watch, wattage/telemetry
# sampling, security-update + model/selfdef sync, tetragon/ghostproxy verify,
# the Memory-OS lifecycle (janitor/observe), the session reaper, log-rotate,
# backups. Each hook self-degrades when its dependency is absent. power-shutdown-
# guard is handled UPS-gated in §7. A profile may mask any via
# SOVEREIGN_OS_RECURRENT_SKIP="sovereign-foo,sovereign-bar".
if [ "${SOVEREIGN_OS_BAKE_FIRSTBOOT:-}" = "1" ] && [ -d "${REPO}/systemd/system" ]; then
  IFS=',' read -ra _RSKIP <<< "${SOVEREIGN_OS_RECURRENT_SKIP:-}"
  rn=0
  for tmr in "${REPO}"/systemd/system/sovereign-*.timer; do
    [ -f "${tmr}" ] || continue
    base="$(basename "${tmr}" .timer)"
    [ "${base}" = "sovereign-power-shutdown-guard" ] && continue   # §7 arms it UPS-gated
    _sk=0; for s in "${_RSKIP[@]}"; do [ "${base}" = "${s}" ] && _sk=1; done
    [ "${_sk}" = "1" ] && { log "recurrent ${base}.timer skipped (profile mask)"; continue; }
    [ -f "${REPO}/systemd/system/${base}.service" ] \
      && install -m 644 "${REPO}/systemd/system/${base}.service" /etc/systemd/system/ 2>/dev/null
    install -m 644 "${tmr}" /etc/systemd/system/ 2>/dev/null
    if systemctl enable "${base}.timer" >/dev/null 2>&1; then rn=$((rn+1)); fi
  done
  log "recurrent maintenance timers enabled (${rn})"
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
  WARN_LEAD="${SOVEREIGN_OS_UPS_WARN_LEAD:-15}"
  if [ -f /etc/sovereign-os/power.toml ]; then
    [ "${SOVEREIGN_OS_UPS_ARM:-}" = "1" ] && sed -i -E 's|^[#[:space:]]*enabled[[:space:]]*=.*|enabled = true|' /etc/sovereign-os/power.toml
    sed -i -E "s|^[#[:space:]]*shutdown_minutes[[:space:]]*=.*|shutdown_minutes = ${SHUT_MIN}|" /etc/sovereign-os/power.toml
    sed -i -E "s|^[#[:space:]]*warn_lead_minutes[[:space:]]*=.*|warn_lead_minutes = ${WARN_LEAD}|" /etc/sovereign-os/power.toml
    log "power.toml → graceful soft shutdown armed (shutdown < ${SHUT_MIN} min, warn ${WARN_LEAD} min ahead)"
  fi
  # (a2) install the staged soft-exit manifest (announce → drain → unload →
  #      stop → sync → poweroff). The guard runs `schedule-manifest apply` on it.
  [ -f /etc/sovereign-os/shutdown-manifest.toml ] || \
    { [ -f "${REPO}/config/shutdown-manifest.toml.example" ] \
      && cp "${REPO}/config/shutdown-manifest.toml.example" /etc/sovereign-os/shutdown-manifest.toml \
      && log "shutdown-manifest.toml installed (staged graceful soft-exit sequence)"; }
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
    if [ -f "${REPO}/systemd/system/${u}" ]; then install -m 644 "${REPO}/systemd/system/${u}" /etc/systemd/system/ 2>/dev/null || true; fi
  done
  systemctl enable sovereign-ups-setup.service >/dev/null 2>&1 || true
  if [ "${SOVEREIGN_OS_UPS_ARM:-}" = "1" ]; then
    if systemctl enable sovereign-power-shutdown-guard.timer >/dev/null 2>&1; then
      log "power-shutdown-guard timer armed (minutely; soft shutdown < ${SHUT_MIN} min)"
    fi
  fi
fi

if [ "${_CRIT_FAILURES}" -gt 0 ]; then
  log "done WITH ${_CRIT_FAILURES} CRITICAL failure(s) — refusing to certify the image (see the CRITICAL line(s) above)"
  exit 1
fi
log "done — operator=${OPERATOR} posture=${POSTURE}"
exit 0
