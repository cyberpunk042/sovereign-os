#!/usr/bin/env bash
# scripts/build/07-image-build.sh — invoke the substrate to produce the
# bootable image artifact.
#
# mkosi: 'mkosi build' from the prepared config tree (step 05 + 06).
# live-build: 'lb build' from the prepared config tree (step 05 + 06).
# rpm-ostree, nixos: deferred to Stage 2+ (ALT paths).

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
. "${__SCRIPT_DIR}/lib/common.sh"
# shellcheck source=./lib/observability.sh
. "${__SCRIPT_DIR}/lib/observability.sh"

STEP_ID="07-image-build"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

env_substrate="${SOVEREIGN_OS_STATE_DIR}/env-substrate.sh"
require_file "${env_substrate}"
# shellcheck disable=SC1090
. "${env_substrate}"

env_debs="${SOVEREIGN_OS_STATE_DIR}/env-kernel-debs.sh"
if [ -f "${env_debs}" ]; then
  # shellcheck disable=SC1090
  . "${env_debs}"
fi

inputs_hash="$(state_inputs_hash "${BASH_SOURCE[0]}" "${SOVEREIGN_OS_PROFILE_FILE}")"

if ! state_step_should_run "${STEP_ID}" "${inputs_hash}"; then
  log_info "step ${STEP_ID} already completed with matching inputs — skipping"
  exit 0
fi

log_step_header "${STEP_ID}" "build image (substrate=${SOVEREIGN_OS_SUBSTRATE})"
state_step_start "${STEP_ID}" "${inputs_hash}"

emit_build_metric() {
  emit_metric sovereign_os_build_step_image_build_total 1 \
    "substrate=\"${SOVEREIGN_OS_SUBSTRATE}\",profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"$1\""
}

# Stage compiled kernel .debs into substrate-specific cache (mkosi:
# mkosi.extra/...; live-build: config/packages.chroot/...)
stage_kernel_debs() {
  local cache_dir="$1"
  if [ -n "${SOVEREIGN_OS_KERNEL_DEBS_DIR:-}" ] && [ -d "${SOVEREIGN_OS_KERNEL_DEBS_DIR}" ]; then
    mkdir -p "${cache_dir}"
    # Idempotent re-stage: drop leftovers from prior runs (a previously
    # staged -dbg deb would otherwise ship 984M into the image).
    rm -f "${cache_dir}"/*.deb
    # -dbg deb excluded: 984M of debug symbols that would otherwise ship
    # INSIDE the final image filesystem via mkosi.extra. Newest revision
    # per package only: the forge accumulates a .deb per rebuild
    # (6.12.0-1.. -7 after the first real build's fix iterations) and
    # dpkg would otherwise unpack every one of them in sequence.
    local deb base name
    declare -A latest=()
    while IFS= read -r deb; do
      [ -e "${deb}" ] || continue
      case "${deb}" in *-dbg_*) continue ;; esac
      base="$(basename "${deb}")"
      name="${base%%_*}"
      latest["${name}"]="${deb}"   # sort -V order → last seen wins
    done < <(printf '%s\n' "${SOVEREIGN_OS_KERNEL_DEBS_DIR}"/*.deb | sort -V)
    if [ "${#latest[@]}" -gt 0 ]; then
      cp "${latest[@]}" "${cache_dir}/"
      log_info "staged ${#latest[@]} kernel .deb(s) (newest revision each): ${!latest[*]}"
    else
      log_warn "no kernel .debs to copy (dry-run mode? substrate-default kernel?)"
    fi
  fi
}

# Stage the selfdef SOURCE into the image (mkosi.extra → /opt/selfdef) so
# the postinst can build+install it — the operator's "ready after flash,
# no manual compile" (SOVEREIGN_OS_BAKE_SELFDEF). Excludes the heavy
# target/ + .git; the emit's postinst runs `make build` in /opt/selfdef.
stage_selfdef_source() {
  local dest="$1"
  local src="${SOVEREIGN_OS_SELFDEF_DIR:-${HOME}/selfdef}"
  [ -n "${SOVEREIGN_OS_BAKE_SELFDEF:-}" ] || return 0
  if [ ! -d "${src}/.git" ] && [ ! -f "${src}/Cargo.toml" ]; then
    log_warn "SOVEREIGN_OS_BAKE_SELFDEF set but no selfdef checkout at ${src} — skipping stage"
    return 0
  fi
  log_info "staging selfdef source → ${dest} (baked build at postinst)"
  mkdir -p "${dest}"
  ( cd "${src}" && tar --exclude=./target --exclude=./.git -cf - . ) \
    | ( cd "${dest}" && tar -xf - )
}

case "${SOVEREIGN_OS_SUBSTRATE}" in
  mkosi)
    stage_kernel_debs "${SOVEREIGN_OS_BUILD_OUT}/mkosi.extra/var/cache/local-debs"
    stage_selfdef_source "${SOVEREIGN_OS_BUILD_OUT}/mkosi.extra/opt/selfdef"
    cd "${SOVEREIGN_OS_BUILD_OUT}" || exit 1
    if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
      log_warn "SOVEREIGN_OS_DRY_RUN — skipping 'mkosi build'"
      emit_build_metric skip
      state_step_complete "${STEP_ID}"
      exit 0
    fi
    require_command mkosi
    log_info "running 'mkosi --force build' in ${SOVEREIGN_OS_BUILD_OUT}"
    # --force: without it mkosi sees an existing output and exits 0 doing
    # NOTHING — step 07 then reports success over a stale image (caught
    # on the first real rebuild, 2026-06-10). Rebuild decisions belong to
    # the orchestrator's state machine, not mkosi's output cache.
    if mkosi --force build 2>&1 | tee "${SOVEREIGN_OS_LOG_DIR}/image-build-${SOVEREIGN_OS_BUILD_ID}.log"; then
      emit_build_metric success
    else
      rc=${PIPESTATUS[0]}
      log_error "mkosi build failed (rc=${rc})"
      emit_build_metric fail
      state_step_fail "${STEP_ID}" "mkosi-build-failed-${rc}"
      exit 1
    fi
    ;;

  live-build)
    stage_kernel_debs "${SOVEREIGN_OS_BUILD_OUT}/config/packages.chroot"
    cd "${SOVEREIGN_OS_BUILD_OUT}" || exit 1
    if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
      log_warn "SOVEREIGN_OS_DRY_RUN — skipping 'lb build'"
      emit_build_metric skip
      state_step_complete "${STEP_ID}"
      exit 0
    fi
    require_command lb
    log_info "running 'lb build' in ${SOVEREIGN_OS_BUILD_OUT}"
    if lb build 2>&1 | tee "${SOVEREIGN_OS_LOG_DIR}/image-build-${SOVEREIGN_OS_BUILD_ID}.log"; then
      emit_build_metric success
    else
      rc=${PIPESTATUS[0]}
      log_error "lb build failed (rc=${rc})"
      emit_build_metric fail
      state_step_fail "${STEP_ID}" "lb-build-failed-${rc}"
      exit 1
    fi
    ;;

  rpm-ostree|nixos)
    log_error "substrate '${SOVEREIGN_OS_SUBSTRATE}' image-build not yet implemented (Stage 2+ ALT path)"
    emit_build_metric not-implemented
    state_step_fail "${STEP_ID}" "substrate-image-build-not-implemented"
    exit 1
    ;;

  *)
    log_error "unknown substrate: ${SOVEREIGN_OS_SUBSTRATE}"
    emit_build_metric unknown
    state_step_fail "${STEP_ID}" "unknown-substrate"
    exit 1
    ;;
esac

# Discover output (per substrate)
case "${SOVEREIGN_OS_SUBSTRATE}" in
  mkosi)      output_dir="${SOVEREIGN_OS_BUILD_OUT}/output" ;;
  live-build) output_dir="${SOVEREIGN_OS_BUILD_OUT}" ;;  # lb build emits to the same dir
esac

if [ -d "${output_dir}" ] && [ -z "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "image artifacts in ${output_dir}:"
  find "${output_dir}" -maxdepth 1 -type f \( -name '*.raw' -o -name '*.img' -o -name '*.iso' -o -name '*.qcow2' \) \
    -exec ls -lh {} \; | while read -r line; do
    log_info "  ${line}"
  done
fi

env_file="${SOVEREIGN_OS_STATE_DIR}/env-image.sh"
cat > "${env_file}" <<EOF
# auto-generated by ${STEP_ID}
export SOVEREIGN_OS_IMAGE_DIR="${output_dir}"
EOF
log_info "env handoff: ${env_file}"

state_step_complete "${STEP_ID}"
log_info "step ${STEP_ID} complete"
