#!/usr/bin/env bash
# scripts/build/06-whitelabel-render.sh — render whitelabel templates +
# overlays into the substrate's build directory.
#
# Reads the profile's whitelabel.profile binding → loads the named
# whitelabel YAML → for each surface declaration, applies its strategy
# per SDD-007. Output is placed into substrate-specific locations:
# mkosi.skeleton/ for skeleton overlays, mkosi.extra/ for late overlays.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
. "${__SCRIPT_DIR}/lib/common.sh"
# shellcheck source=./lib/observability.sh
. "${__SCRIPT_DIR}/lib/observability.sh"

STEP_ID="06-whitelabel-render"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

env_substrate="${SOVEREIGN_OS_STATE_DIR}/env-substrate.sh"
require_file "${env_substrate}"
# shellcheck disable=SC1090
. "${env_substrate}"

wl_profile_name="$(profile_field whitelabel.profile)"
: "${wl_profile_name:=default}"
wl_file="${SOVEREIGN_OS_WHITELABEL_DIR}/${wl_profile_name}.yaml"
require_file "${wl_file}"

inputs_hash="$(state_inputs_hash "${BASH_SOURCE[0]}" "${SOVEREIGN_OS_PROFILE_FILE}" "${wl_file}")"

if ! state_step_should_run "${STEP_ID}" "${inputs_hash}"; then
  log_info "step ${STEP_ID} already completed with matching inputs — skipping"
  exit 0
fi

log_step_header "${STEP_ID}" "render whitelabel (profile=${SOVEREIGN_OS_PROFILE} whitelabel=${wl_profile_name})"
state_step_start "${STEP_ID}" "${inputs_hash}"

# Render engine (Stage-2+ Layer 1 of SDD-007)
render_engine="${SOVEREIGN_OS_SCRIPTS_DIR}/whitelabel/render.py"
require_file "${render_engine}"

log_info "invoking render engine: ${render_engine}"
log_info "  profile:    ${SOVEREIGN_OS_PROFILE_FILE}"
log_info "  whitelabel: ${wl_file}"
log_info "  out:        ${SOVEREIGN_OS_BUILD_OUT}"

emit_render_metric() {
  emit_metric sovereign_os_build_step_render_total 1 \
    "whitelabel=\"${wl_profile_name}\",substrate=\"${SOVEREIGN_OS_SUBSTRATE}\",profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"$1\""
}

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would invoke render engine"
  emit_render_metric skip
  state_step_complete "${STEP_ID}"
  exit 0
fi

if python3 "${render_engine}" \
     --profile "${SOVEREIGN_OS_PROFILE_FILE}" \
     --whitelabel "${wl_file}" \
     --out "${SOVEREIGN_OS_BUILD_OUT}" \
     --substrate "${SOVEREIGN_OS_SUBSTRATE}"; then
  emit_render_metric success
else
  rc=$?
  log_error "render engine failed (rc=${rc})"
  emit_render_metric fail
  state_step_fail "${STEP_ID}" "render-failed-${rc}"
  exit 1
fi

state_step_complete "${STEP_ID}"
log_info "step ${STEP_ID} complete"
