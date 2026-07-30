#!/usr/bin/env bash
# local model — profiles.provisioning.model
# gate: IAC_ENABLE_MODEL   (OFF by default — tens of GB)
#
# WHY GATED OFF: the profile asks for
#   nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16 at bf16 into
#   /mnt/vault/models/... with min_free_gb: 80. A 30B BF16 checkpoint is ~60GB.
#
# BLOCKER THIS MODULE REPORTS RATHER THAN WORKS AROUND
#   /mnt/vault does not exist. It is almost certainly the mount the missing ZFS
#   pool was meant to provide — the same pool sovereign-zfs-scrub.timer and
#   sovereign-backup-snapshot.timer expect (tank/context). Converge will not
#   invent a mountpoint on the root filesystem: silently writing 60GB to / when
#   the operator asked for a vault is worse than stopping and saying so.
#
#   Decide the storage first (create the pool, or repoint provisioning.model
#   .local_dir), then re-run with IAC_ENABLE_MODEL=1.
#
# shellcheck shell=bash

_repo="$(profile_get provisioning.model.repo)"
_dir="$(profile_get provisioning.model.local_dir)"
_minfree="$(profile_get provisioning.model.min_free_gb 0)"

if [ -z "${_repo}" ] || [ -z "${_dir}" ]; then
  skip "provisioning.model not fully declared"
  return 0 2>/dev/null || exit 0
fi

iac_info "repo=${_repo}"
iac_info "dir=${_dir} (min_free_gb=${_minfree})"

_parent="$(dirname "${_dir}")"
_mountroot="/$(printf '%s' "${_dir}" | cut -d/ -f2)"   # e.g. /mnt

# ---- storage must exist and be a real mount, not an accidental root dir ----
if [ ! -d "${_parent}" ]; then
  # Is the intended vault even mounted?
  if [ "${_mountroot}" != "/" ] && ! mountpoint -q "$(printf '%s' "${_dir}" | cut -d/ -f1-3)" 2>/dev/null; then
    fail "$(printf '%s' "${_dir}" | cut -d/ -f1-3) is not a mounted filesystem — create the vault storage before fetching a ~60GB model"
  else
    fail "${_parent} does not exist"
  fi
  return 0 2>/dev/null || exit 0
fi

# ---- free space ----
if [ "${_minfree}" -gt 0 ] 2>/dev/null; then
  _avail_gb="$(df -BG --output=avail "${_parent}" 2>/dev/null | tail -1 | tr -dc '0-9')"
  if [ -n "${_avail_gb}" ] && [ "${_avail_gb}" -lt "${_minfree}" ] 2>/dev/null; then
    fail "only ${_avail_gb}GB free at ${_parent}, profile requires min_free_gb=${_minfree}"
    return 0 2>/dev/null || exit 0
  fi
  ok "free space at ${_parent}: ${_avail_gb:-?}GB (need ${_minfree}GB)"
fi

# ---- already fetched? ----
if [ -s "${_dir}/config.json" ]; then
  ok "model present at ${_dir}"
  return 0 2>/dev/null || exit 0
fi

_fetch=/opt/sovereign-os/scripts/intelligence/fetch-model.sh
if [ ! -x "${_fetch}" ]; then
  fail "fetch script missing: ${_fetch}"
  return 0 2>/dev/null || exit 0
fi

if [ "${IAC_DRY_RUN}" = 1 ]; then
  changed "fetch ${_repo} → ${_dir}"
else
  iac_info "fetching — this is a large download"
  if SOVEREIGN_MODEL_REPO="${_repo}" "${_fetch}" "${_dir}" >/dev/null 2>&1; then
    changed "model fetched → ${_dir}"
  else
    fail "model fetch failed — see ${_fetch}"
  fi
fi
