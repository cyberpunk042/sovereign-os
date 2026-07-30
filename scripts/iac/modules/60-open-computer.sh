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

for u in sovereign-open-computer-install.service sovereign-open-computer.service; do
  systemctl list-unit-files "${u}" --no-legend 2>/dev/null | grep -q . \
    || { fail "unit ${u} not installed"; return 0 2>/dev/null || exit 0; }
done

# ---- provision (idempotent: base image present ⇒ already done) ----
_base=/var/lib/sovereign-os/open-computer/base_image/base.qcow2
_envf=/etc/sovereign-os/open-computer.env

if [ -s "${_base}" ] && [ -s "${_envf}" ]; then
  ok "open-computer provisioned (base image + env present)"
else
  if [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "provision open-computer (~3GB fetch via sovereign-open-computer-install.service)"
  else
    iac_info "provisioning — this downloads ~3GB and may take a while"
    if systemctl start sovereign-open-computer-install.service >/dev/null 2>&1; then
      # The installer unit is ExecStart=- (failure-tolerant by design, so a boot
      # without network does not wedge). Verify the artefacts instead of trusting
      # the exit status.
      if [ -s "${_base}" ] && [ -s "${_envf}" ]; then
        changed "open-computer provisioned"
      else
        fail "installer ran but artefacts missing — see: journalctl -u sovereign-open-computer-install"
        return 0 2>/dev/null || exit 0
      fi
    else
      fail "sovereign-open-computer-install.service failed to start"
      return 0 2>/dev/null || exit 0
    fi
  fi
fi

# ---- runtime state ----
# posture is installed-off, so only enable when the operator asked via the gate.
ensure_unit_state sovereign-open-computer.service enabled started

if [ "${IAC_DRY_RUN}" != 1 ] && systemctl is-active --quiet sovereign-open-computer.service 2>/dev/null; then
  iac_info "UI: http://localhost:${_port}"
fi
