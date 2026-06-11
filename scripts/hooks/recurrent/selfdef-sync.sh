#!/usr/bin/env bash
# scripts/hooks/recurrent/selfdef-sync.sh
#
# Weekly selfdef freshness check + gated update.
#
# Cross-repo contract (SDD-001): sovereign-os BUILDS, selfdef RUNS,
# info-hub SYNTHESIZES. selfdef (the IPS) is installed from its OWN
# repo and publishes typed-mirror artifacts to
# /run/sovereign-os/selfdef-mirror/*.json which the cockpit dashboards
# render READ-ONLY. This hook keeps the selfdef checkout current so
# the operator keeps receiving the latest modules + mirror schemas
# after install — without sovereign-os ever mutating IPS state.
#
# Behavior (triple-gate convention, sister to operator-deps R284):
#   - DEFAULT: report-only. git fetch + how far behind + latest tag.
#     Never modifies the working tree.
#   - APPLY:   requires SOVEREIGN_OS_CONFIRM_SELFDEF_SYNC=YES.
#     Fast-forward-only pull (refuses diverged trees), then defers the
#     rebuild to selfdef's own tooling (`make build`) and attempts a
#     `systemctl try-restart 'selfdef*'` so refreshed mirror
#     publishers pick up. selfdef's signed-release path
#     (ansible/update.yml — cosign-verified .deb upgrade) is still
#     PLANNED upstream; when it ships, this hook should delegate to it
#     and the git path becomes the dev-checkout fallback.
#
# Emits Layer B metrics:
#   sovereign_os_selfdef_sync_behind_commits
#   sovereign_os_selfdef_sync_last_run_timestamp
#   sovereign_os_selfdef_sync_result{result=current|behind|updated|absent|diverged}
#
# Honors SOVEREIGN_OS_DRY_RUN=1 (forces report-only even with confirm).

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

: "${SOVEREIGN_OS_SELFDEF_DIR:=${HOME}/selfdef}"
: "${SOVEREIGN_OS_SELFDEF_REMOTE:=origin}"
: "${SOVEREIGN_OS_SELFDEF_BRANCH:=main}"

log_step_header "selfdef-sync" "freshness check for selfdef checkout at ${SOVEREIGN_OS_SELFDEF_DIR}"

emit_summary() {
  local behind="$1" result="$2"
  emit_metric_set selfdef-sync \
    '# HELP sovereign_os_selfdef_sync_behind_commits Commits behind upstream at last check' \
    '# TYPE sovereign_os_selfdef_sync_behind_commits gauge' \
    "sovereign_os_selfdef_sync_behind_commits ${behind}" \
    '# HELP sovereign_os_selfdef_sync_result Last sync outcome (1 = this result)' \
    '# TYPE sovereign_os_selfdef_sync_result gauge' \
    "sovereign_os_selfdef_sync_result{result=\"${result}\"} 1" \
    '# HELP sovereign_os_selfdef_sync_last_run_timestamp Unix timestamp of last run' \
    '# TYPE sovereign_os_selfdef_sync_last_run_timestamp gauge' \
    "sovereign_os_selfdef_sync_last_run_timestamp $(date +%s)"
}

if [ ! -d "${SOVEREIGN_OS_SELFDEF_DIR}/.git" ]; then
  log_error "no selfdef checkout at ${SOVEREIGN_OS_SELFDEF_DIR} (set SOVEREIGN_OS_SELFDEF_DIR)"
  emit_summary 0 absent
  exit 0   # absent is a report, not a hook failure
fi

cd "${SOVEREIGN_OS_SELFDEF_DIR}"
require_command git

git fetch --quiet "${SOVEREIGN_OS_SELFDEF_REMOTE}" "${SOVEREIGN_OS_SELFDEF_BRANCH}"

UPSTREAM="${SOVEREIGN_OS_SELFDEF_REMOTE}/${SOVEREIGN_OS_SELFDEF_BRANCH}"
BEHIND="$(git rev-list --count "HEAD..${UPSTREAM}" 2>/dev/null || echo 0)"
AHEAD="$(git rev-list --count "${UPSTREAM}..HEAD" 2>/dev/null || echo 0)"
LATEST_TAG="$(git describe --tags --abbrev=0 "${UPSTREAM}" 2>/dev/null || echo "none")"
LOCAL_REV="$(git rev-parse --short HEAD)"

log_info "  local:    ${LOCAL_REV} (${AHEAD} ahead)"
log_info "  upstream: ${UPSTREAM} (${BEHIND} behind; latest tag ${LATEST_TAG})"

if [ "${BEHIND}" -eq 0 ]; then
  log_info "  selfdef is current."
  emit_summary 0 current
  exit 0
fi

if [ "${AHEAD}" -gt 0 ]; then
  log_warn "  local checkout has diverged (${AHEAD} local commits) — refusing to auto-update."
  log_warn "  resolve manually in ${SOVEREIGN_OS_SELFDEF_DIR}, then re-run."
  emit_summary "${BEHIND}" diverged
  exit 0
fi

if [ "${SOVEREIGN_OS_CONFIRM_SELFDEF_SYNC:-}" != "YES" ] || [ "${SOVEREIGN_OS_DRY_RUN:-0}" = "1" ]; then
  log_warn "  ${BEHIND} commit(s) behind. Report-only (set SOVEREIGN_OS_CONFIRM_SELFDEF_SYNC=YES to apply)."
  emit_summary "${BEHIND}" behind
  exit 0
fi

log_info "  applying: fast-forward to ${UPSTREAM}"
git merge --ff-only "${UPSTREAM}"
log_info "  rebuilding via selfdef's own tooling (make build)"
if ! make build; then
  log_error "selfdef build failed — checkout updated, binaries stale. Fix in ${SOVEREIGN_OS_SELFDEF_DIR}."
  emit_summary 0 behind
  exit 1
fi
# refreshed mirror publishers pick up the new schemas; ignore if no units
systemctl try-restart 'selfdef*' 2>/dev/null || true
log_info "  selfdef updated to $(git rev-parse --short HEAD) (was ${LOCAL_REV})."
emit_summary 0 updated
