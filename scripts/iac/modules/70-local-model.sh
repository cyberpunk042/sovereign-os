#!/usr/bin/env bash
# local model — profiles.provisioning.model, reconciled against loader capability
# gate: IAC_ENABLE_MODEL
#
# THE PROFILE ASKS FOR SOMETHING THIS RUNTIME CANNOT LOAD.
#
#   provisioning.model.repo = nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16
#   provisioning.model.local_dir = /mnt/vault/models/...   (min_free_gb: 80)
#
# Three independent blockers, verified 2026-07-30:
#
#   1. /mnt/vault does not exist and cannot without reclaiming the Debian 13
#      disk or adding hardware — both NVMe devices are fully partitioned.
#   2. A 30B BF16 checkpoint ships SHARDED (model-0000N-of-0000M.safetensors +
#      model.safetensors.index.json). Nothing in crates/ handles a shard index:
#          grep -rl 'safetensors.index|model-.*-of-' crates/   -> no matches
#      and scripts/intelligence/fetch-model.sh fetches exactly three files
#      (config.json, tokenizer.json, model.safetensors) — single-file only.
#   3. The gateway generates on CPU. No crate in sovereign-gatewayd's dependency
#      tree links CUDA (only sovereign-nvfp4-runtime does, and it is not a dep).
#      A 30B BF16 forward pass on CPU is not interactive, whatever the RAM.
#
# So the profile's model is ASPIRATIONAL — it describes where this is going, not
# what today's gateway can serve. Converge does not pretend otherwise and does
# not silently substitute: it reports the gap, and serves the model the runtime
# actually supports, declared as a machine truth in converge.conf.
#
# When the loader grows shard + GPU support, drop IAC_MODEL_REPO from
# converge.conf and this module follows the profile again.
#
# shellcheck shell=bash

_prof_repo="$(profile_get provisioning.model.repo)"
_prof_dir="$(profile_get provisioning.model.local_dir)"
_minfree="$(profile_get provisioning.model.min_free_gb 0)"

# Machine truth wins where the profile outruns the runtime (same pattern as the
# GPU power floor). Empty override ⇒ follow the profile verbatim.
_repo="${IAC_MODEL_REPO:-${_prof_repo}}"
_dir="${IAC_MODEL_DIR:-${_prof_dir}}"

if [ -z "${_repo}" ] || [ -z "${_dir}" ]; then
  skip "no model declared (profile provisioning.model + no converge.conf override)"
  return 0 2>/dev/null || exit 0
fi

if [ "${_repo}" != "${_prof_repo}" ]; then
  iac_info "profile asks for : ${_prof_repo}"
  iac_info "serving instead  : ${_repo}"
  iac_info "reason: the gateway loads single-file safetensors on CPU; see this module's header"
fi
iac_info "dir=${_dir}"

# ---- the gateway must ADVERTISE the id its clients ask for ----
# profiles.provisioning.open_computer.model_id and .openclaw.model_id both say
# "local-oracle", but the gateway defaults its primary id to "primary"
# (SOVEREIGN_GATEWAY_MODEL_ID, lib.rs:1969). The serving path treats any name
# that is not primary_id as a SECONDARY model and, finding none registered,
# returns "no local model loaded" — indistinguishable from having no model at
# all. Both clients would have failed that way against a perfectly loaded model.
#
# Align the daemon with the profile via a drop-in (never by editing the shipped
# unit), so the id the clients request is the id the gateway answers to.
_client_model_id="$(profile_get provisioning.open_computer.model_id)"
[ -n "${_client_model_id}" ] || _client_model_id="$(profile_get provisioning.openclaw.model_id)"

if [ -n "${_client_model_id}" ]; then
  _cur_id="$(systemctl show sovereign-gatewayd -p Environment --value 2>/dev/null \
             | tr ' ' '\n' | sed -n 's/^SOVEREIGN_GATEWAY_MODEL_ID=//p')"
  : "${_cur_id:=primary}"
  if [ "${_cur_id}" = "${_client_model_id}" ]; then
    ok "gateway advertises '${_client_model_id}' (matches profile clients)"
  else
    iac_info "gateway advertises '${_cur_id}' but clients ask for '${_client_model_id}'"
    ensure_dropin sovereign-gatewayd.service 20-model-id <<EOF
# Managed by scripts/iac/modules/70-local-model.sh — do not edit by hand.
# provisioning.open_computer.model_id / .openclaw.model_id = ${_client_model_id}
# The gateway's default primary id is "primary"; a request for any other name is
# treated as a secondary model and fails with "no local model loaded" even when
# the primary is loaded and healthy. Make the daemon answer to what its own
# clients are configured to ask for.
[Service]
Environment=SOVEREIGN_GATEWAY_MODEL_ID=${_client_model_id}
EOF
    if [ "${IAC_DRY_RUN}" != 1 ]; then
      systemctl daemon-reload 2>/dev/null || true
      if systemctl is-active --quiet sovereign-gatewayd 2>/dev/null; then
        if run "restart-gateway-id" systemctl restart sovereign-gatewayd; then
          changed "sovereign-gatewayd restarted to advertise '${_client_model_id}'"
        else
          fail "could not restart sovereign-gatewayd after model-id change"
        fi
      fi
    fi
  fi
fi

# ---- the gateway must be pointed at this exact directory or it ignores it ----
_gw_model="$(systemctl show sovereign-gatewayd -p Environment --value 2>/dev/null \
             | tr ' ' '\n' | sed -n 's/^SOVEREIGN_GATEWAY_MODEL=//p')"
if [ -n "${_gw_model}" ] && [ "${_gw_model}" != "${_dir}" ]; then
  iac_info "note: sovereign-gatewayd looks at ${_gw_model}"
  iac_info "      a model elsewhere is downloaded but never served"
fi

# ---- storage ----
_parent="$(dirname "${_dir}")"
if [ ! -d "${_parent}" ]; then
  _mnt="$(printf '%s' "${_dir}" | cut -d/ -f1-3)"
  if printf '%s' "${_dir}" | grep -q '^/mnt/' && ! mountpoint -q "${_mnt}" 2>/dev/null; then
    fail "${_mnt} is not a mounted filesystem — create the vault storage first, or set IAC_MODEL_DIR"
    return 0 2>/dev/null || exit 0
  fi
  ensure_dir "${_parent}" 0755 root:root
fi

if [ "${_minfree}" -gt 0 ] 2>/dev/null; then
  _avail_gb="$(df -BG --output=avail "${_parent}" 2>/dev/null | tail -1 | tr -dc '0-9')"
  if [ -n "${_avail_gb}" ] && [ "${_avail_gb}" -lt "${_minfree}" ] 2>/dev/null; then
    fail "only ${_avail_gb}GB free at ${_parent}, profile requires min_free_gb=${_minfree}"
    return 0 2>/dev/null || exit 0
  fi
  ok "free space at ${_parent}: ${_avail_gb:-?}GB (profile wants ${_minfree}GB)"
fi

# ---- already fetched? the loader needs all three ----
_complete=1
for f in config.json tokenizer.json model.safetensors; do
  [ -s "${_dir}/${f}" ] || _complete=0
done
if [ "${_complete}" = 1 ]; then
  ok "model present at ${_dir}"
  return 0 2>/dev/null || exit 0
fi

_fetch=/opt/sovereign-os/scripts/intelligence/fetch-model.sh
[ -x "${_fetch}" ] || _fetch="${IAC_SOURCE_RESOLVED_DIR:-/home/jfortin/sovereign-os}/scripts/intelligence/fetch-model.sh"
if [ ! -x "${_fetch}" ]; then
  fail "fetch script not found"
  return 0 2>/dev/null || exit 0
fi

if [ "${IAC_DRY_RUN}" = 1 ]; then
  changed "fetch ${_repo} → ${_dir}"
  return 0 2>/dev/null || exit 0
fi

# The script reads MODEL_REPO. (An earlier version of this module exported
# SOVEREIGN_MODEL_REPO, which fetch-model.sh ignores — it would have silently
# downloaded the DEFAULT model while reporting the requested one.)
iac_info "fetching — network download"
if MODEL_REPO="${_repo}" "${_fetch}" "${_dir}" >/dev/null 2>&1; then
  _missing=""
  for f in config.json tokenizer.json model.safetensors; do
    [ -s "${_dir}/${f}" ] || _missing="${_missing} ${f}"
  done
  if [ -n "${_missing}" ]; then
    # Sharded repos "succeed" with a 404-free partial set — catch that here
    # rather than handing the gateway an unloadable directory.
    fail "fetch incomplete, missing:${_missing} (is ${_repo} sharded? this loader needs a single model.safetensors)"
  else
    changed "model fetched → ${_dir}"
    # The gateway loads the model at STARTUP only.
    if systemctl is-active --quiet sovereign-gatewayd 2>/dev/null \
       && [ "${_gw_model}" = "${_dir}" ]; then
      if run "restart-gateway" systemctl restart sovereign-gatewayd; then
        changed "sovereign-gatewayd restarted to load the model"
      else
        fail "could not restart sovereign-gatewayd"
      fi
    fi
  fi
else
  fail "model fetch failed — MODEL_REPO=${_repo} ${_fetch} ${_dir}"
fi
