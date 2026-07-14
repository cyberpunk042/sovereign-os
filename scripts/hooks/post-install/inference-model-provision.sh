#!/usr/bin/env bash
# scripts/hooks/post-install/inference-model-provision.sh
#
# Provision the inference model vLLM serves (SDD-702). Downloads the profile's
# provisioning.model.repo to its local_dir (under the tank/models ZFS dataset) so
# a flashed SAIN-01 actually has a real model to serve — the serving layer
# (model_serve_cli / VllmBackend / oracle-core, all operator-launched per the
# installed-off posture) assumed a model existed, but nothing provisioned one.
#
# BEST-EFFORT / NON-FATAL: a multi-GB model pull needs network + the huggingface
# CLI (operator-deps [pip]) + free space + (for a gated repo) SOVEREIGN_OS_HF_TOKEN.
# Any of those missing → a clear message + clean skip; it is fully resumable
# post-flash (`huggingface-cli download` resumes, and re-running the hook re-tries).
# A model download must NEVER brick first boot. Idempotent (a present model is a
# no-op) + VM-skipped by the unit. Not the tiny opt-in intelligence/fetch-model.sh
# (SmolLM smoke) — this pulls the real, sharded serving model.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="inference-model-provision"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "${STEP_ID}" "provision the inference model for vLLM"

require_root

emit_provision_metric() {
  emit_metric sovereign_os_post_install_model_provision_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"$1\""
}

repo="$(profile_field provisioning.model.repo)"
local_dir="$(profile_field provisioning.model.local_dir)"
min_free_gb="$(profile_field provisioning.model.min_free_gb)"
: "${min_free_gb:=0}"

if [ -z "${repo}" ] || [ -z "${local_dir}" ]; then
  log_info "no provisioning.model.{repo,local_dir} configured — nothing to provision"
  emit_provision_metric no-model
  exit 0
fi

# ---- idempotency: a present model config means it's already downloaded ----
if [ -s "${local_dir}/config.json" ]; then
  log_info "model already present at ${local_dir} (config.json exists) — skipping"
  emit_provision_metric already-present
  exit 0
fi

# ---- the huggingface CLI comes from operator-deps [pip] (vllm + huggingface_hub) ----
hf_cli="$(command -v huggingface-cli 2>/dev/null || true)"
if [ -z "${hf_cli}" ]; then
  log_warn "huggingface-cli not found — apply operator-deps first (config/operator-deps.toml [pip]: vllm + huggingface_hub), then re-run; skipping (non-fatal)"
  emit_provision_metric no-hf-cli
  exit 0
fi

# ---- free-space gate: refuse a huge pull that would fill the pool ----
mkdir -p "${local_dir}"
avail_gb="$(df -BG --output=avail "${local_dir}" 2>/dev/null | tail -1 | tr -dc '0-9')"
if [ -n "${avail_gb}" ] && [ "${min_free_gb%.*}" -gt 0 ] 2>/dev/null; then
  if [ "${avail_gb}" -lt "${min_free_gb%.*}" ] 2>/dev/null; then
    log_warn "only ${avail_gb}GB free at ${local_dir} (< ${min_free_gb}GB required) — skipping model pull (non-fatal); free space or lower provisioning.model.min_free_gb"
    emit_provision_metric no-space
    exit 0
  fi
fi

# ---- gated repos need a token; pass it through when present ----
token_args=()
if [ -n "${SOVEREIGN_OS_HF_TOKEN:-}" ]; then
  token_args=(--token "${SOVEREIGN_OS_HF_TOKEN}")
  log_info "using SOVEREIGN_OS_HF_TOKEN for the (possibly gated) repo"
fi

log_info "downloading ${repo} → ${local_dir} (resumable; multi-GB — this takes a while)"
if "${hf_cli}" download "${repo}" --local-dir "${local_dir}" "${token_args[@]}" 2>&1 | sed 's/^/  /'; then
  if [ -s "${local_dir}/config.json" ]; then
    log_info "model ${repo} provisioned at ${local_dir}"
    # Point the vLLM Oracle Core at the provisioned model (the profile is the
    # source of truth for the oracle model — supersede the env's shipped default).
    oracle_env="/etc/sovereign-os/inference-oracle-core.env"
    mkdir -p /etc/sovereign-os
    if [ -f "${oracle_env}" ] && grep -q '^ORACLE_MODEL=' "${oracle_env}"; then
      sed -i -E "s#^ORACLE_MODEL=.*#ORACLE_MODEL=${local_dir}#" "${oracle_env}"
    else
      printf 'ORACLE_MODEL=%s\n' "${local_dir}" >> "${oracle_env}"
    fi
    log_info "  ORACLE_MODEL → ${local_dir} (${oracle_env})"
    emit_provision_metric provisioned
    emit_metric sovereign_os_post_install_model_info 1 \
      "profile=\"${SOVEREIGN_OS_PROFILE}\",repo=\"${repo}\""
  else
    log_warn "download reported success but ${local_dir}/config.json is missing — treat as incomplete (re-run to resume)"
    emit_provision_metric incomplete
  fi
else
  log_warn "model download failed — a GATED repo needs SOVEREIGN_OS_HF_TOKEN (or swap provisioning.model.repo for an ungated model); fully resumable, re-run post-flash (non-fatal)"
  emit_provision_metric download-failed
fi

log_info "${STEP_ID} complete"
