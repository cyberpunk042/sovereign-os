#!/usr/bin/env bash
# operator service account — profiles.provisioning.operator
# gate: IAC_ENABLE_OPERATOR
#
# WHY: three shipped units declare User=operator / Group=operator —
#   sovereign-open-computer.service, sovereign-openclaw.service,
#   sovereign-frontend-kiosk.service
# and the user does not exist on this machine. Nothing in the sovereign-os
# scripts tree creates it: open-computer-install.sh only does
#   usermod -aG kvm "${operator}"      (line ~100)
#   chown -R "${operator}:${operator}" (line ~178)
# both of which ASSUME the account is already there — it was meant to come from
# the OS installer's provisioning step, which created `jfortin` instead.
# Without this module those three units die at 217/USER.
#
# shellcheck shell=bash

_op_user="$(profile_get provisioning.operator.username operator)"
_op_shell="$(profile_get provisioning.operator.shell /bin/bash)"
_op_home_repo="$(profile_get provisioning.operator.home_repo sovereign-os)"

# HOME lives under the state root, NOT /home. sovereign-open-computer.service
# runs with ProtectHome=read-only (see its unit comment: "HOME relocated to the
# state root so the CLI's checkout + base image + agent overlays live under a
# writable tree OUTSIDE /home"). A /home/operator would be read-only to it.
_op_home="/var/lib/sovereign-os/operator"

iac_info "user=${_op_user} home=${_op_home} shell=${_op_shell}"

# ---- group ----
if getent group "${_op_user}" >/dev/null 2>&1; then
  ok "group ${_op_user}"
else
  if run "groupadd" groupadd --system "${_op_user}"; then changed "group ${_op_user} created"
  else fail "group ${_op_user} — groupadd failed"; fi
fi

# ---- user ----
if getent passwd "${_op_user}" >/dev/null 2>&1; then
  ok "user ${_op_user}"
  cur_home="$(getent passwd "${_op_user}" | cut -d: -f6)"
  cur_shell="$(getent passwd "${_op_user}" | cut -d: -f7)"
  if [ "${cur_home}" != "${_op_home}" ]; then
    if run "usermod-home" usermod -d "${_op_home}" "${_op_user}"; then
      changed "user ${_op_user} home → ${_op_home}"
    else fail "user ${_op_user} home"; fi
  fi
  if [ "${cur_shell}" != "${_op_shell}" ]; then
    if run "usermod-shell" usermod -s "${_op_shell}" "${_op_user}"; then
      changed "user ${_op_user} shell → ${_op_shell}"
    else fail "user ${_op_user} shell"; fi
  fi
else
  if run "useradd" useradd --system --gid "${_op_user}" \
        --home-dir "${_op_home}" --create-home --shell "${_op_shell}" "${_op_user}"; then
    changed "user ${_op_user} created"
  else
    fail "user ${_op_user} — useradd failed"
  fi
fi

ensure_dir "${_op_home}" 0750 "${_op_user}:${_op_user}"

# ---- supplementary groups ----
# `sudo` is in profiles.provisioning.operator.groups and is applied deliberately.
# Reviewed and accepted by the operator 2026-07-31: this account is also the
# runtime user for sovereign-open-computer, a browser-reachable QEMU sandbox, so
# the combination is a real (if accepted) exposure. Settled — not an oversight,
# and not to be re-raised.
# The profile lists sudo/podman/render/video/adm. kvm is added on top because
# the open-computer runtime needs /dev/kvm (open-computer-install.sh does the
# same, but only if the account already exists — which is the bug above).
# Groups absent on this host are reported, not invented: silently creating a
# `podman` group would make the account look provisioned when podman is not.
_want_groups="$(profile_get provisioning.operator.groups)"
for g in ${_want_groups} kvm; do
  [ -n "${g}" ] || continue
  if ! getent group "${g}" >/dev/null 2>&1; then
    skip "group ${g} absent on this host — not adding ${_op_user} to it"
    continue
  fi
  if id -nG "${_op_user}" 2>/dev/null | tr ' ' '\n' | grep -qx "${g}"; then
    ok "${_op_user} in ${g}"
  else
    if run "usermod-aG" usermod -aG "${g}" "${_op_user}"; then
      changed "${_op_user} added to ${g}"
    else fail "${_op_user} → group ${g}"; fi
  fi
done

# Export for later modules (05 runs first but reads these via the same helpers;
# 60/70 need the home path).
export IAC_OPERATOR_USER="${_op_user}"
export IAC_OPERATOR_HOME="${_op_home}"
export IAC_OPERATOR_HOME_REPO="${_op_home_repo}"
