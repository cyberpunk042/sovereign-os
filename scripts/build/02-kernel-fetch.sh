#!/usr/bin/env bash
# scripts/build/02-kernel-fetch.sh — fetch the kernel source into the
# forge tmpfs. Honors the profile's kernel.source + kernel.version_minimum.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
. "${__SCRIPT_DIR}/lib/common.sh"
# shellcheck source=./lib/observability.sh
. "${__SCRIPT_DIR}/lib/observability.sh"

STEP_ID="02-kernel-fetch"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_FORGE_DIR:=/mnt/kernel_forge}"
: "${SOVEREIGN_OS_KERNEL_REMOTE:=https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git}"

kernel_source="$(profile_field kernel.source)"
kernel_version_minimum="$(profile_field kernel.version_minimum)"

log_info "profile: ${SOVEREIGN_OS_PROFILE}"
log_info "kernel source: ${kernel_source}"
log_info "kernel version minimum: ${kernel_version_minimum}"

# Q18-A: substrate-default profiles skip kernel-build steps 02-04.
# The substrate adapter (mkosi/live-build) pulls linux-image-amd64
# from the Debian archive instead.
if [ "${kernel_source}" = "substrate-default" ] || [ -z "${kernel_source}" ]; then
  log_info "skipping ${STEP_ID} (kernel.source=substrate-default — Debian archive supplies the kernel)"
  exit 0
fi

inputs_hash="$(state_inputs_hash "${BASH_SOURCE[0]}" "${SOVEREIGN_OS_PROFILE_FILE}")"

if ! state_step_should_run "${STEP_ID}" "${inputs_hash}"; then
  log_info "step ${STEP_ID} already completed with matching inputs — skipping"
  exit 0
fi

log_step_header "${STEP_ID}" "fetch kernel source"
state_step_start "${STEP_ID}" "${inputs_hash}"

# ---- DRY-RUN short-circuit (operator-verbatim CI/preview safety) ----
if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN set — skipping kernel source clone/fetch"
  emit_metric sovereign_os_build_step_kernel_fetch_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"dry-run\""
  # Record 'dry-run', NOT 'completed' — completing here with the real
  # inputs_hash makes the next REAL run skip this step body entirely.
  state_step_dry_run "${STEP_ID}"
  exit 0
fi

require_dir "${SOVEREIGN_OS_FORGE_DIR}"
require_command git

case "${kernel_source}" in
  kernel.org-stable)
    target="${SOVEREIGN_OS_FORGE_DIR}/linux-stable"
    # SOVEREIGN_OS_KERNEL_TAG (optional) pins an exact tag — SDD-019
    # reproducibility input. Falls back to "v<version_minimum>".
    pinned_tag="${SOVEREIGN_OS_KERNEL_TAG:-v${kernel_version_minimum}}"
    if [ -d "${target}/.git" ]; then
      log_info "kernel repo already cloned at ${target} — fetching"
      # A prior build may own this repo as a DIFFERENT user (e.g. root) — mark it
      # safe so git doesn't refuse with 'dubious ownership'. Idempotent.
      git config --global --add safe.directory "${target}" 2>/dev/null || true
      if ! git -C "${target}" fetch --tags --depth 1; then
        # The source is ALREADY here. A failed fetch — offline snapshot mirror,
        # unreachable remote, or a read-only/foreign-owned clone — must NOT sink
        # the build: this step's job is to ENSURE the kernel source exists, not
        # to require network on every re-run. Proceed with the existing clone so
        # long as it resolves a HEAD; only hard-fail on a genuinely broken repo.
        if git -C "${target}" rev-parse --verify HEAD >/dev/null 2>&1; then
          log_warn "git fetch failed (offline / foreign-owned repo) — using the existing clone at ${target}"
        else
          log_error "kernel repo at ${target} is unusable (fetch failed AND no resolvable HEAD)"
          emit_metric sovereign_os_build_step_kernel_fetch_total 1 \
            "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
          state_step_fail "${STEP_ID}" "kernel-fetch-failed"
          exit 1
        fi
      fi
    else
      log_info "cloning ${SOVEREIGN_OS_KERNEL_REMOTE} → ${target} (shallow, tag=${pinned_tag})"
      git clone --depth 1 --branch "${pinned_tag}" "${SOVEREIGN_OS_KERNEL_REMOTE}" "${target}" || {
        log_warn "shallow clone of ${pinned_tag} failed; falling back to default branch"
        # The fallback clone was bare: if it ALSO failed, set -e aborted the step
        # with NO state_step_fail and NO metric — a total clone failure (remote
        # down, bad tag, disk full) was invisible to both the state machine and
        # the observability surface. Guard it like every other terminal path.
        git clone --depth 1 "${SOVEREIGN_OS_KERNEL_REMOTE}" "${target}" || {
          log_error "kernel clone failed for both tag=${pinned_tag} and default branch (remote unreachable or disk full)"
          emit_metric sovereign_os_build_step_kernel_fetch_total 1 \
            "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
          state_step_fail "${STEP_ID}" "kernel-clone-failed"
          exit 1
        }
      }
    fi
    # Record the resolved commit SHA — pinned + verifiable per SDD-019.
    resolved_sha="$(git -C "${target}" rev-parse HEAD 2>/dev/null || echo unknown)"
    resolved_tag="$(git -C "${target}" describe --tags --always 2>/dev/null || echo unknown)"
    log_info "kernel source: tag=${resolved_tag} sha=${resolved_sha}"
    mkdir -p "${SOVEREIGN_OS_STATE_DIR}"
    printf 'tag: %s\nsha: %s\nremote: %s\n' \
      "${resolved_tag}" "${resolved_sha}" "${SOVEREIGN_OS_KERNEL_REMOTE}" \
      > "${SOVEREIGN_OS_STATE_DIR}/kernel-source-resolution.yaml"
    ;;
  xanmod|liquorix)
    log_error "kernel source '${kernel_source}' not yet implemented (Stage-2+)"
    emit_metric sovereign_os_build_step_kernel_fetch_total 1 \
      "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
    state_step_fail "${STEP_ID}" "unsupported-kernel-source"
    exit 1
    ;;
  substrate-default)
    log_info "kernel source is substrate-default — no fetch needed (substrate provides kernel)"
    ;;
  *)
    log_error "unknown kernel.source value: ${kernel_source}"
    emit_metric sovereign_os_build_step_kernel_fetch_total 1 \
      "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
    state_step_fail "${STEP_ID}" "unknown-kernel-source"
    exit 1
    ;;
esac

# Emit env handoff
env_file="${SOVEREIGN_OS_STATE_DIR}/env-kernel-source.sh"
cat > "${env_file}" <<EOF
# auto-generated by ${STEP_ID}
export SOVEREIGN_OS_KERNEL_SRC="${SOVEREIGN_OS_FORGE_DIR}/linux-stable"
export SOVEREIGN_OS_KERNEL_RESOLVED_SHA="${resolved_sha:-unknown}"
export SOVEREIGN_OS_KERNEL_RESOLVED_TAG="${resolved_tag:-unknown}"
EOF
log_info "env handoff: ${env_file}"

emit_metric sovereign_os_build_step_kernel_fetch_total 1 \
  "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"success\""
state_step_complete "${STEP_ID}"
log_info "step ${STEP_ID} complete"
