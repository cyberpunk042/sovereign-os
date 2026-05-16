#!/usr/bin/env bash
# scripts/hooks/recurrent/model-catalog-sync.sh
#
# Daily check that the resident model catalog (E110) is intact +
# weights match expected hashes. Stub for now; full Stage-2+
# integration with whichever inference backend wins Q-017 (vLLM /
# llama.cpp / etc.).

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

: "${SOVEREIGN_OS_MODELS_DIR:=/mnt/vault/models}"

log_step_header "model-catalog-sync" "verify resident model catalog"

if [ ! -d "${SOVEREIGN_OS_MODELS_DIR}" ]; then
  log_warn "models dir not present: ${SOVEREIGN_OS_MODELS_DIR}; nothing to verify"
  exit 0
fi

# Stub: list residents + their sizes. Full integrity verification
# (sha256 against catalog manifest) lands at E110 stage when Q-017
# resolves and a real catalog manifest format is locked.
log_info "resident models:"
find "${SOVEREIGN_OS_MODELS_DIR}" -maxdepth 2 -type d | tail -n +2 | while read -r d; do
  size="$(du -sh "$d" 2>/dev/null | cut -f1)"
  log_info "  ${d##*/}  (${size})"
done

log_info "model-catalog-sync complete (full integrity verification at Stage 2+ post-Q-017)"
