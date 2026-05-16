#!/usr/bin/env bash
# scripts/hooks/recurrent/model-catalog-sync.sh
#
# Daily verification of the resident model catalog at
# ${SOVEREIGN_OS_MODELS_DIR}. Catalog manifest format:
#
#   ${SOVEREIGN_OS_MODELS_DIR}/<model-id>/manifest.sha256
#
# where manifest.sha256 contains 'sha256(filename)' lines matching
# the produced `sha256sum *` format. If manifest absent, we record
# the model as 'unmanaged' (operator pulled but didn't sign manifest).
#
# Emits Layer B metrics:
#   sovereign_os_models_catalog_total {result=verified|missing-manifest|corrupt}
#   sovereign_os_models_catalog_last_run_timestamp
#   sovereign_os_models_catalog_resident_count
#   sovereign_os_models_catalog_total_bytes
#
# Honors SOVEREIGN_OS_DRY_RUN=1.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

: "${SOVEREIGN_OS_MODELS_DIR:=/mnt/vault/models}"

log_step_header "model-catalog-sync" "verify resident model catalog at ${SOVEREIGN_OS_MODELS_DIR}"

emit_summary() {
  local verified="$1" missing="$2" corrupt="$3" total_bytes="$4" resident="$5"
  emit_metric_set models-catalog \
    '# HELP sovereign_os_models_catalog_total Per-result catalog verification counters from the last run' \
    '# TYPE sovereign_os_models_catalog_total gauge' \
    "sovereign_os_models_catalog_total{result=\"verified\"} ${verified}" \
    "sovereign_os_models_catalog_total{result=\"missing-manifest\"} ${missing}" \
    "sovereign_os_models_catalog_total{result=\"corrupt\"} ${corrupt}" \
    '# HELP sovereign_os_models_catalog_resident_count Total resident model directories' \
    '# TYPE sovereign_os_models_catalog_resident_count gauge' \
    "sovereign_os_models_catalog_resident_count ${resident}" \
    '# HELP sovereign_os_models_catalog_total_bytes Total disk usage of models dir (bytes)' \
    '# TYPE sovereign_os_models_catalog_total_bytes gauge' \
    "sovereign_os_models_catalog_total_bytes ${total_bytes}" \
    '# HELP sovereign_os_models_catalog_last_run_timestamp Unix timestamp of last verification' \
    '# TYPE sovereign_os_models_catalog_last_run_timestamp gauge' \
    "sovereign_os_models_catalog_last_run_timestamp $(date +%s)"
}

if [ ! -d "${SOVEREIGN_OS_MODELS_DIR}" ]; then
  log_warn "models dir not present: ${SOVEREIGN_OS_MODELS_DIR}; nothing to verify"
  emit_summary 0 0 0 0 0
  exit 0
fi

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would inspect resident models in ${SOVEREIGN_OS_MODELS_DIR}"
  exit 0
fi

verified=0 missing=0 corrupt=0 resident=0
total_bytes="$(du -sb "${SOVEREIGN_OS_MODELS_DIR}" 2>/dev/null | cut -f1 || echo 0)"

mapfile -t model_dirs < <(find "${SOVEREIGN_OS_MODELS_DIR}" -maxdepth 2 -mindepth 1 -type d 2>/dev/null | sort)

for d in "${model_dirs[@]}"; do
  resident=$((resident + 1))
  name="${d##*/}"
  manifest="${d}/manifest.sha256"
  size="$(du -sh "${d}" 2>/dev/null | cut -f1)"

  if [ ! -f "${manifest}" ]; then
    log_warn "  ${name}  (${size})  — no manifest.sha256 (unmanaged)"
    missing=$((missing + 1))
    continue
  fi

  # Verify each entry in the manifest. sha256sum exits non-zero if any fail.
  if (cd "${d}" && sha256sum -c manifest.sha256 --status 2>/dev/null); then
    log_info "  ✓ ${name}  (${size})  — manifest verified"
    verified=$((verified + 1))
  else
    log_error "  ✗ ${name}  (${size})  — manifest FAILED verification (corrupt or modified)"
    corrupt=$((corrupt + 1))
  fi
done

log_info "summary: resident=${resident} verified=${verified} unmanaged=${missing} corrupt=${corrupt}"
emit_summary "${verified}" "${missing}" "${corrupt}" "${total_bytes}" "${resident}"

# Exit non-zero if any corruption — alarm signal for ops dashboards
if [ "${corrupt}" -gt 0 ]; then
  exit 2
fi
exit 0
