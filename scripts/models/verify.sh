#!/usr/bin/env bash
# scripts/models/verify.sh — Verify resident model catalog matches the
# declared canonical models/catalog.yaml.
#
# Distinct from scripts/hooks/recurrent/model-catalog-sync.sh (which
# verifies the integrity of resident bytes against per-model
# manifest.sha256). THIS script verifies that the DECLARED catalog is
# satisfied: every catalog entry with status=verified-real is resident
# at ${SOVEREIGN_OS_MODELS_DIR}/<model-id>/, and reports per-tier
# coverage for the operator.
#
# Env vars:
#   SOVEREIGN_OS_MODELS_DIR   (default: /mnt/vault/models)
#   SOVEREIGN_OS_DRY_RUN      print intent + exit 0

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/build/lib/common.sh" 2>/dev/null || true

type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [models/verify] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [models/verify] $*"; }
type log_error >/dev/null 2>&1 || log_error() { echo "ERROR [models/verify] $*" >&2; }

: "${SOVEREIGN_OS_MODELS_DIR:=/mnt/vault/models}"

CATALOG="${__REPO_ROOT}/../models/catalog.yaml"
[ -f "${CATALOG}" ] || CATALOG="${__REPO_ROOT}/models/catalog.yaml"
[ -f "${CATALOG}" ] || { log_error "catalog not found"; exit 1; }

log_info "==== sovereign-os model catalog verification ===="
log_info "  catalog:     ${CATALOG}"
log_info "  models dir:  ${SOVEREIGN_OS_MODELS_DIR}"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN: would verify every status=verified-real entry has resident dir"
  log_info "DRY-RUN: would report per-tier (pulse/logic/oracle) coverage"
  exit 0
fi

# Disable -e + clear ERR trap around the python3 invocation so the
# verifier's exit code (2 = absent entries detected) is surfaced
# cleanly without the parent common.sh ERR trap logging the heredoc.
set +e
trap - ERR
python3 - "${CATALOG}" "${SOVEREIGN_OS_MODELS_DIR}" <<'PYEOF'
import os, sys, yaml
catalog_path, models_dir = sys.argv[1], sys.argv[2]
with open(catalog_path) as f:
    doc = yaml.safe_load(f)

models = doc["catalog"]["models"]
total = len(models)
verified_real = [m for m in models if m["status"] == "verified-real"]
present = []
absent = []

for m in verified_real:
    p = os.path.join(models_dir, m["id"])
    if os.path.isdir(p):
        present.append(m["id"])
    else:
        absent.append(m["id"])

print(f"  TOTAL catalog entries:        {total}")
print(f"  verified-real:                {len(verified_real)}")
print(f"  aspirational:                 {sum(1 for m in models if m['status']=='aspirational')}")
print(f"  operator-must-confirm:        {sum(1 for m in models if m['status']=='operator-must-confirm')}")
print()
print(f"  RESIDENT (verified-real):     {len(present)}/{len(verified_real)}")
for mid in present:
    print(f"    ✓ {mid}")
print()
if absent:
    print(f"  ABSENT (verified-real, not on disk):")
    for mid in absent:
        print(f"    ✗ {mid} — run: scripts/models/pull.sh {mid}")
    print()

# Per-tier breakdown
for tier in ("pulse", "logic", "oracle", "router"):
    tier_models = [m for m in models if m["tier"] == tier]
    if not tier_models:
        continue
    print(f"  tier={tier} ({len(tier_models)} declared):")
    for m in tier_models:
        residency = "✓" if m["id"] in present else (
            "—" if m["status"] != "verified-real" else "✗"
        )
        print(f"    {residency} {m['id']:40s} status={m['status']}")

sys.exit(0 if not absent else 2)
PYEOF
rc=$?
exit ${rc}
