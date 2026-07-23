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

# Stage the COMPILED intelligence layer (crates/ → daemon binaries) into the
# image (mkosi.extra → /usr/local/bin). Built on the BUILD HOST, not in the bake
# container: the bake has NO external network (snapshot mirror only) and apt
# cargo is older than the pinned 1.89, so rustup cannot fetch the toolchain there
# — an in-container build is impossible. The host carries rustup 1.89 and the
# image is the same arch/distro (trixie/x86_64), so the binaries run as-is. This
# is the same "STAGED from the build host" pattern as Claude Code.
# Gated on SOVEREIGN_OS_BAKE_INTELLIGENCE (opt-in, like BAKE_SELFDEF).
stage_intelligence_binaries() {
  local dest="$1"   # mkosi.extra/usr/local/bin
  [ -n "${SOVEREIGN_OS_BAKE_INTELLIGENCE:-}" ] || return 0
  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    log_info "dry-run — skipping intelligence-layer host build/stage"
    return 0
  fi
  log_info "building intelligence layer on host → staging daemons to ${dest}"
  mkdir -p "${dest}"
  if SOVEREIGN_OS_RUST_BINDIR="${dest}" "${__SCRIPT_DIR}/build-intelligence.sh"; then
    log_info "staged $(find "${dest}" -maxdepth 1 -type f 2>/dev/null | wc -l) intelligence daemon(s) → image /usr/local/bin"
  else
    log_warn "intelligence host build failed — flashed image falls back to a provision-time build (non-fatal)"
  fi
}

# Stage a small REAL model into the image (mkosi.extra → /var/lib/sovereign-os/
# models/<name>) so sovereign-gatewayd generates out of the box on first boot
# (its unit points SOVEREIGN_GATEWAY_MODEL here). Fetched on the host (network
# available). Gated on SOVEREIGN_OS_BAKE_MODEL (opt-in — adds ~0.5 GB to the
# image). The gateway degrades to decision-only if this is skipped.
stage_intelligence_model() {
  local dest="$1"   # mkosi.extra/var/lib/sovereign-os/models/smollm-135m
  [ -n "${SOVEREIGN_OS_BAKE_MODEL:-}" ] || return 0
  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    log_info "dry-run — skipping model fetch/stage"
    return 0
  fi
  local repo="${SOVEREIGN_OS_BAKE_MODEL_REPO:-HuggingFaceTB/SmolLM-135M}"
  log_info "fetching ${repo} on host → staging model to ${dest}"
  mkdir -p "${dest}"
  if MODEL_REPO="${repo}" "${__SCRIPT_DIR}/../intelligence/fetch-model.sh" "${dest}"; then
    log_info "staged model ${repo} → image (gateway generates on first boot)"
  else
    log_warn "model fetch failed — gateway runs decision-only until a model is fetched (non-fatal)"
  fi
}

# Derive the intelligence/model bake toggles from the profile when the build-host
# env does not force them — the same env-OR-profile pattern mkosi-emit uses. So a
# profile that declares provisioning.bake.intelligence:true bakes the compiled brain
# into the image with no manual flag, and the panel/operator can still override:
# '1' forces on, '0' forces off, unset/empty inherits the profile. (The staging
# functions above gate on a NON-EMPTY value, so '0' must normalise to empty.)
_bake_from_profile() {  # $1 = env var name, $2 = provisioning.bake.<key>
  case "${!1:-}" in
    1) export "$1=1"; return 0 ;;
    0) export "$1=";  return 0 ;;
  esac
  if [ "$(profile_field "provisioning.bake.$2")" = "True" ]; then
    export "$1=1"
  else
    export "$1="
  fi
}
_bake_from_profile SOVEREIGN_OS_BAKE_INTELLIGENCE intelligence
_bake_from_profile SOVEREIGN_OS_BAKE_MODEL model

case "${SOVEREIGN_OS_SUBSTRATE}" in
  mkosi)
    stage_kernel_debs "${SOVEREIGN_OS_BUILD_OUT}/mkosi.extra/var/cache/local-debs"
    stage_selfdef_source "${SOVEREIGN_OS_BUILD_OUT}/mkosi.extra/opt/selfdef"
    # The sovereign brain: compiled daemons + (optionally) a real model, staged
    # from the host so the flashed image ships them ready (the bake can't build
    # the 1.89-pinned crates offline).
    stage_intelligence_binaries "${SOVEREIGN_OS_BUILD_OUT}/mkosi.extra/usr/local/bin"
    stage_intelligence_model "${SOVEREIGN_OS_BUILD_OUT}/mkosi.extra/var/lib/sovereign-os/models/smollm-135m"
    cd "${SOVEREIGN_OS_BUILD_OUT}" || exit 1
    if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
      log_warn "SOVEREIGN_OS_DRY_RUN — skipping 'mkosi build'"
      emit_build_metric skip
      # Record 'dry-run', NOT 'completed' — resume-poisoning guard.
      state_step_dry_run "${STEP_ID}"
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
      # Record 'dry-run', NOT 'completed' — resume-poisoning guard.
      state_step_dry_run "${STEP_ID}"
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
