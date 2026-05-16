#!/usr/bin/env bash
# scripts/models/pull.sh — Download a model declared in models/catalog.yaml.
#
# Master spec § 17 binds models to The Genesis Trinity tiers; the
# canonical catalog at models/catalog.yaml declares which models the
# system intends to host and their HuggingFace repo ids. This script is
# the operator-runnable downloader that turns a catalog entry into
# resident bytes under SOVEREIGN_OS_MODELS_DIR.
#
# Usage:
#   scripts/models/pull.sh                    # list catalog entries
#   scripts/models/pull.sh <model-id>         # pull one
#   scripts/models/pull.sh --all              # pull every verified-real entry
#
# Env vars:
#   SOVEREIGN_OS_MODELS_DIR   destination (default: /mnt/vault/models)
#   HUGGINGFACE_HUB_TOKEN     optional auth token (some licenses gated)
#   SOVEREIGN_OS_DRY_RUN      print intent + exit 0
#
# Layer B metrics:
#   sovereign_os_models_pull_total{model,result}
#   sovereign_os_models_pull_last_timestamp{model}

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/build/lib/common.sh" 2>/dev/null || true
# shellcheck source=../build/lib/observability.sh
. "${__REPO_ROOT}/build/lib/observability.sh" 2>/dev/null || true

type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [models/pull] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [models/pull] $*"; }
type log_error >/dev/null 2>&1 || log_error() { echo "ERROR [models/pull] $*" >&2; }
type emit_metric >/dev/null 2>&1 || emit_metric() { :; }

: "${SOVEREIGN_OS_MODELS_DIR:=/mnt/vault/models}"

CATALOG="${__REPO_ROOT}/../models/catalog.yaml"
[ -f "${CATALOG}" ] || CATALOG="${__REPO_ROOT}/models/catalog.yaml"
[ -f "${CATALOG}" ] || { log_error "catalog not found at expected paths"; exit 1; }

# ---------- catalog query helpers (python3 + PyYAML) ----------
catalog_query() {
  local query="$1"
  python3 - "${CATALOG}" "${query}" <<'PYEOF'
import sys, yaml
path, query = sys.argv[1], sys.argv[2]
with open(path) as f:
    doc = yaml.safe_load(f)
models = doc["catalog"]["models"]
if query == "list":
    for m in models:
        repo = m.get("hf_repo_id", "(no repo — " + m["status"] + ")")
        print(f'  {m["id"]:40s} tier={m["tier"]:8s} status={m["status"]:22s} repo={repo}')
elif query == "ids":
    for m in models:
        print(m["id"])
elif query == "verified-real":
    for m in models:
        if m["status"] == "verified-real":
            print(m["id"])
elif query.startswith("entry:"):
    target = query.split(":",1)[1]
    for m in models:
        if m["id"] == target:
            print(yaml.safe_dump(m, sort_keys=False))
            sys.exit(0)
    sys.exit(2)
PYEOF
}

cmd_list() {
  log_info "==== sovereign-os model catalog ===="
  log_info "  master spec § 17 (Genesis Trinity tier bindings)"
  log_info "  catalog:     ${CATALOG}"
  log_info "  models dir:  ${SOVEREIGN_OS_MODELS_DIR}"
  catalog_query list
}

pull_one() {
  local model_id="$1"
  local entry
  if ! entry="$(catalog_query "entry:${model_id}")" || [ -z "${entry}" ]; then
    log_error "model '${model_id}' not found in catalog"
    exit 2
  fi

  local repo status
  repo="$(echo "${entry}" | awk -F': *' '/^hf_repo_id:/{print $2; exit}')"
  status="$(echo "${entry}" | awk -F': *' '/^status:/{print $2; exit}')"

  log_info "==== pulling ${model_id} ===="
  log_info "  status: ${status}"
  log_info "  repo:   ${repo:-<none — aspirational>}"
  log_info "  dest:   ${SOVEREIGN_OS_MODELS_DIR}/${model_id}"

  if [ "${status}" != "verified-real" ] || [ -z "${repo}" ]; then
    log_warn "  ${model_id} status='${status}' — no real HF repo to pull"
    log_warn "  see models/catalog.yaml operator_note for the substitution path"
    emit_metric sovereign_os_models_pull_total 1 "model=\"${model_id}\",result=\"skip-aspirational\""
    return 0
  fi

  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    log_info "  DRY-RUN: would huggingface-cli download \\"
    log_info "             ${repo} \\"
    log_info "             --local-dir ${SOVEREIGN_OS_MODELS_DIR}/${model_id}"
    emit_metric sovereign_os_models_pull_total 1 "model=\"${model_id}\",result=\"dry-run\""
    return 0
  fi

  if ! command -v huggingface-cli >/dev/null 2>&1; then
    log_error "huggingface-cli not installed"
    log_error "  install via: pip install --user huggingface_hub[cli]"
    emit_metric sovereign_os_models_pull_total 1 "model=\"${model_id}\",result=\"missing-tool\""
    exit 1
  fi

  mkdir -p "${SOVEREIGN_OS_MODELS_DIR}/${model_id}"
  if huggingface-cli download "${repo}" \
       --local-dir "${SOVEREIGN_OS_MODELS_DIR}/${model_id}" \
       --local-dir-use-symlinks False; then
    log_info "  ✓ ${model_id} resident at ${SOVEREIGN_OS_MODELS_DIR}/${model_id}"
    emit_metric sovereign_os_models_pull_total 1 "model=\"${model_id}\",result=\"success\""
    emit_metric sovereign_os_models_pull_last_timestamp "$(date +%s)" "model=\"${model_id}\""
  else
    log_error "  huggingface-cli download failed"
    emit_metric sovereign_os_models_pull_total 1 "model=\"${model_id}\",result=\"fail\""
    exit 1
  fi
}

cmd_pull_all() {
  log_info "==== pulling every verified-real catalog entry ===="
  local rc=0
  while IFS= read -r model_id; do
    pull_one "${model_id}" || rc=$?
  done < <(catalog_query "verified-real")
  return ${rc}
}

# ---------- dispatch ----------
case "${1:-}" in
  ""|"list"|"-l"|"--list")
    cmd_list
    ;;
  "--all"|"-a"|"all")
    cmd_pull_all
    ;;
  -*)
    log_error "unknown flag: $1"
    exit 2
    ;;
  *)
    pull_one "$1"
    ;;
esac
