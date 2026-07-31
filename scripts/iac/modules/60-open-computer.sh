#!/usr/bin/env bash
# open-computer QEMU sandbox — profiles.provisioning.open_computer + bake.open_computer
# gate: IAC_ENABLE_OPEN_COMPUTER   (OFF by default — ~3GB download)
#
# WHY GATED OFF: provisioning is a ~3GB base-image fetch plus a node build. That
# is not something a routine converge should do without being asked. Set
# IAC_ENABLE_OPEN_COMPUTER=1 in converge.conf when you want it.
#
# ORDER MATTERS: this module deliberately runs after 10-operator-user. The
# runtime unit declares User=operator/Group=operator, and open-computer-install.sh
# does `usermod -aG kvm ${operator}` and `chown -R ${operator}:${operator}`
# WITHOUT creating the account. Provisioning before the user exists produces a
# unit that installs cleanly and then dies at 217/USER on every start.
#
# shellcheck shell=bash

_want="$(profile_get provisioning.bake.open_computer false)"
if [ "${_want}" != "true" ]; then
  skip "provisioning.bake.open_computer is not true"
  return 0 2>/dev/null || exit 0
fi

_user="${IAC_OPERATOR_USER:-$(profile_get provisioning.operator.username operator)}"
_port="$(profile_get provisioning.open_computer.web_port 9800)"
_backend="$(profile_get provisioning.open_computer.backend local)"

iac_info "backend=${_backend} web_port=${_port} runtime user=${_user}"

# ---- preconditions ----
if ! getent passwd "${_user}" >/dev/null 2>&1; then
  fail "user ${_user} missing — run module 10 first (the runtime would die 217/USER)"
  return 0 2>/dev/null || exit 0
fi
if [ ! -e /dev/kvm ]; then
  fail "/dev/kvm absent — the sandbox cannot accelerate"
  return 0 2>/dev/null || exit 0
fi
ok "preconditions: ${_user} exists, /dev/kvm present"

systemctl list-unit-files sovereign-open-computer.service --no-legend 2>/dev/null | grep -q . \
  || { fail "unit sovereign-open-computer.service not installed"; return 0 2>/dev/null || exit 0; }

# ---- provision (idempotent: base image present ⇒ already done) ----
_base=/var/lib/sovereign-os/open-computer/base_image/base.qcow2
_envf=/etc/sovereign-os/open-computer.env
# THE completeness criterion — copy it from the consumer, do not invent one.
# Both the runtime and the installer gate on the same thing:
#   open-computer-run.sh:16    if [ ! -x "${OC_APP}/open-computer" ]
#   open-computer-install.sh:118  if [ ! -x "${OC_APP}/open-computer" ]
#
# `open-computer` is a SYMLINK in the upstream repo (-> cli/dist/open-computer),
# so -x follows it and is false until `npm run build` in cli/ has produced the
# target. That build is best-effort in the hook ("CLI build hiccup ...
# non-fatal"), which is exactly how a clone-succeeded/build-failed tree ends up
# looking provisioned.
#
# Two earlier criteria were wrong here and both produced a restart loop:
#   base.qcow2 + env only  -> passed against a failed git clone
#   ... + [ -d app ]       -> passed against a failed CLI build
# Verify what the consumer verifies.
_app=/var/lib/sovereign-os/open-computer/src/open-computer
_cli="${_app}/open-computer"

if [ -s "${_base}" ] && [ -s "${_envf}" ] && [ -x "${_cli}" ]; then
  ok "open-computer provisioned (base image + env + built CLI)"
else
  # DO NOT `systemctl start sovereign-open-computer-install.service`.
  # That unit carries ConditionFirstBoot=yes, so on any boot after the first
  # systemd SKIPS it — and a skipped unit reports SUCCESS to `systemctl start`.
  # The result is a provisioning step that silently does nothing while claiming
  # to have worked. (`sovereign-osctl open-computer install` has this same bug:
  # it starts the same condition-gated unit, so that documented command is a
  # no-op on every established system. Worth reporting upstream.)
  #
  # Run the hook the unit would have run, directly. It is standalone-safe:
  # set -euo pipefail + its own require_root.
  _hook=/opt/sovereign-os/scripts/hooks/post-install/open-computer-install.sh
  [ -x "${_hook}" ] || _hook="${IAC_SOURCE_RESOLVED_DIR:-/home/jfortin/sovereign-os}/scripts/hooks/post-install/open-computer-install.sh"

  if [ ! -x "${_hook}" ]; then
    fail "install hook not found: ${_hook}"
    return 0 2>/dev/null || exit 0
  fi

  if [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "provision open-computer (~3GB) via ${_hook}"
  else
    _oclog="/var/log/sovereign-os/iac-open-computer.log"
    install -d "$(dirname "${_oclog}")" 2>/dev/null || true
    iac_info "provisioning via ${_hook} — ~3GB download + node build"
    iac_info "log: ${_oclog}"

    "${_hook}" >"${_oclog}" 2>&1 || true

    # ---- repair the missing execute bit on the built CLI ----
    # UPSTREAM BUG (Mintplex-Labs/anything-llm): open-computer/cli's
    # `npm run build` (tsc --noEmit && node build.mjs) writes
    # cli/dist/open-computer with mode 0664 — no execute bit. Reproduced in a
    # clean clone 2026-07-30: npm install and the build both succeed, the
    # 156KB artefact appears, and it is -rw-rw-r--.
    #
    # open-computer/open-computer is a symlink to that file, and BOTH consumers
    # test executability:
    #     open-computer-run.sh:16      if [ ! -x "${OC_APP}/open-computer" ]
    #     open-computer-install.sh:118 if [ ! -x "${OC_APP}/open-computer" ]
    # so the sandbox is permanently unprovisionable through this path: the hook
    # re-clones and rebuilds on every run, always lands 0664, and always
    # concludes "not provisioned". The runtime then respawns forever.
    #
    # A build that produced its artefact is a SUCCESS with a wrong mode, not a
    # failure — so repair the mode rather than reporting a phantom build error.
    _dist="${_app}/cli/dist/open-computer"
    if [ -f "${_dist}" ] && [ ! -x "${_dist}" ]; then
      if chmod 0755 "${_dist}" 2>/dev/null; then
        changed "chmod +x ${_dist} (upstream build.mjs writes it 0664)"
      else
        fail "could not chmod +x ${_dist}"
      fi
    fi

    # The hook is deliberately failure-tolerant (the unit is ExecStart=-), so its
    # exit status is not evidence. Verify the artefacts.
    if [ -s "${_base}" ] && [ -s "${_envf}" ] && [ -x "${_cli}" ]; then
      changed "open-computer provisioned"
    else
      _missing=""
      [ -s "${_base}" ] || _missing="${_missing} base.qcow2"
      [ -s "${_envf}" ] || _missing="${_missing} open-computer.env"
      if [ ! -x "${_cli}" ]; then
        if [ -d "${_app}" ]; then
          _missing="${_missing} cli/dist/open-computer(npm-build)"
        else
          _missing="${_missing} src/open-computer(git-clone)"
        fi
      fi
      _err="$(grep -oiE '^(error|fatal|npm ERR)[: !].*' "${_oclog}" 2>/dev/null | head -3)"
      [ -z "${_err}" ] && _err="$(grep -oiE '(hiccup|failed|deferred)[^\n]*' "${_oclog}" 2>/dev/null | head -3)"
      [ -z "${_err}" ] && _err="$(tail -4 "${_oclog}" 2>/dev/null)"
      fail "provisioning incomplete, missing:${_missing}"
      printf '%s\n' "${_err}" | while IFS= read -r l; do [ -n "${l}" ] && iac_info "${l}"; done
      iac_info "full log: ${_oclog}"
      return 0 2>/dev/null || exit 0
    fi
  fi
fi

# ---- UEFI firmware shim: upstream names vs Debian/Ubuntu names ----
# open-computer/cli/src/config.ts resolves, on Linux with no QEMU_DIST:
#     resolveEfiCode() -> /usr/share/qemu/edk2-x86_64-code.fd
#     resolveEfiVars() -> /usr/share/qemu/edk2-i386-vars.fd
# Those are UPSTREAM QEMU / Alpine names. Debian and Ubuntu ship the same
# firmware under different names in a different directory:
#     /usr/share/OVMF/OVMF_CODE_4M.fd   (CODE, read-only pflash)
#     /usr/share/OVMF/OVMF_VARS_4M.fd   (VARS, the writable variable store)
# so QEMU dies with:
#     Could not open '/usr/share/qemu/edk2-x86_64-code.fd': No such file
#
# config.ts honours OPEN_COMPUTER_QEMU_DIR (QEMU_DIST) and searches
# ${QEMU_DIST}/share/qemu/<file> first, falling back to PATH for the qemu binary
# itself — so a shim directory of symlinks satisfies it without touching
# /usr/share, which is dpkg territory.
#
# CODE and VARS must stay DISTINCT: cli/src/config.ts warns that copying CODE
# into the vars slot leaves OVMF without a variable store, so it never POSTs and
# the display stays blank. The 4M pair is matched deliberately.
_qshim=/var/lib/sovereign-os/open-computer/qemu-dist
_ovmf_code=/usr/share/OVMF/OVMF_CODE_4M.fd
_ovmf_vars=/usr/share/OVMF/OVMF_VARS_4M.fd

if [ ! -r "${_ovmf_code}" ] || [ ! -r "${_ovmf_vars}" ]; then
  fail "OVMF firmware missing (${_ovmf_code} / ${_ovmf_vars}) — install: apt install ovmf"
else
  ensure_dir "${_qshim}/share/qemu" 0755 root:root
  for pair in "edk2-x86_64-code.fd:${_ovmf_code}" "edk2-i386-vars.fd:${_ovmf_vars}"; do
    _lnk="${_qshim}/share/qemu/${pair%%:*}"
    _tgt="${pair#*:}"
    if [ "$(readlink -f "${_lnk}" 2>/dev/null)" = "${_tgt}" ]; then
      ok "efi shim $(basename "${_lnk}")"
    elif [ "${IAC_DRY_RUN}" = 1 ]; then
      changed "efi shim $(basename "${_lnk}") → ${_tgt}"
    elif ln -sfn "${_tgt}" "${_lnk}" 2>/dev/null; then
      changed "efi shim $(basename "${_lnk}") → ${_tgt}"
    else
      fail "could not link ${_lnk}"
    fi
  done

  # Point the CLI at the shim. A drop-in, not open-computer.env — that file is
  # rendered and owned by agent-backend.py, so converge writing into it would
  # be clobbered on the next provision.
  ensure_dropin sovereign-open-computer.service 10-qemu-dist <<EOF
# Managed by scripts/iac/modules/60-open-computer.sh — do not edit by hand.
# open-computer's CLI hardcodes upstream QEMU firmware names under
# /usr/share/qemu; Ubuntu ships OVMF under /usr/share/OVMF with different names.
# QEMU_DIST makes config.ts search our shim first. The qemu BINARY still comes
# from PATH (config.ts falls back), so this only redirects firmware lookup.
[Service]
Environment=OPEN_COMPUTER_QEMU_DIR=${_qshim}
EOF
  iac_daemon_reload
fi

# ---- Type=forking: the CLI daemonizes, it does not stay foreground ----
# The shipped unit is Type=simple and its ExecStart runs `open-computer up`,
# whose comment says:
#     "runs `open-computer up` in the foreground so systemd supervises it. If the
#      CLI daemonizes instead of staying foreground on the real box, switch the
#      unit to Type=forking (documented in SDD-706 as unverified)."
# Verified on the real box 2026-07-30: it daemonizes. cli/src/vm.ts:232
#     spawn(binary, args, { detached: true, ... }); child.unref();
# so the parent exits 0 the moment QEMU is up. Under Type=simple systemd reads
# that as the service having completed and tears the cgroup down — taking the
# VM with it. The journal shows exactly that:
#     Started (pid 86895).
#     sovereign-open-computer.service: Deactivated successfully.
#
# QEMU is launched with -pidfile (vm.ts:141) at ${AGENTS_DIR}/<agent>/qemu.pid
# (registry.ts:31), so systemd can track the real main process. Resolve the
# agent name the same way the launcher does: OPEN_COMPUTER_AGENT, default
# "sovereign" (open-computer-run.sh:14).
_agent="$(sed -n 's/^OPEN_COMPUTER_AGENT=//p' "${_envf}" 2>/dev/null | head -1)"
: "${_agent:=sovereign}"
_agents_dir="$(sed -n 's/^OPEN_COMPUTER_AGENTS_DIR=//p' "${_envf}" 2>/dev/null | head -1)"
: "${_agents_dir:=/var/lib/sovereign-os/open-computer/agents}"
_pidfile="${_agents_dir}/${_agent}/qemu.pid"

iac_info "agent='${_agent}' pidfile=${_pidfile}"
ensure_dropin sovereign-open-computer.service 20-forking <<EOF
# Managed by scripts/iac/modules/60-open-computer.sh — do not edit by hand.
# The open-computer CLI spawns QEMU detached + unref'd (cli/src/vm.ts:232) and
# exits, so Type=simple makes systemd tear the VM down the instant it starts.
# QEMU writes -pidfile, so Type=forking + PIDFile tracks the real process.
# The shipped unit anticipated this: "switch the unit to Type=forking
# (documented in SDD-706 as unverified)". Now verified.
[Service]
Type=forking
PIDFile=${_pidfile}
EOF
iac_daemon_reload

# ---- runtime state ----
# posture is installed-off, so only enable when the operator asked via the gate.
ensure_unit_state sovereign-open-computer.service enabled started

if [ "${IAC_DRY_RUN}" != 1 ] && systemctl is-active --quiet sovereign-open-computer.service 2>/dev/null; then
  iac_info "UI: http://localhost:${_port}"
fi
