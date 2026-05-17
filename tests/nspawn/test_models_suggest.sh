#!/usr/bin/env bash
# tests/nspawn/test_models_suggest.sh — R214 profile-aware suggester.
# Cross-references master-spec § 18 runtime profile allocations against
# the R212 catalog and produces operator-actionable advice.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/models/suggest-by-profile.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_models_suggest.sh"
echo

[ -x "${SCRIPT}" ] && ok "suggest-by-profile.py executable" \
  || { ko "missing suggest-by-profile.py"; exit 1; }
grep -q "suggest)" "${OSCTL}" \
  && ok "osctl bridges 'models suggest'" \
  || ko "osctl bridge missing"
grep -q "models suggest --runtime-profile" "${OSCTL}" \
  && ok "osctl help documents 'models suggest'" \
  || ko "osctl help missing"

# --- --list ---
set +e
list_out="$(python3 "${SCRIPT}" --list)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--list rc=0" || ko "--list rc=${rc}"
for pid in ultra-sovereign-efficiency high-concurrency-burst deep-context-synthesis; do
  grep -qF "${pid}" <<< "${list_out}" && ok "list includes ${pid}" \
    || ko "list missing ${pid}"
done

# --- high-concurrency-burst — known to have flagged allocations ---
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
set +e
python3 "${SCRIPT}" --runtime-profile high-concurrency-burst > "${WORK}/hcb.txt"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "high-concurrency-burst rc=1 (flagged allocations)" \
  || ko "expected rc=1 on flagged profile, got ${rc}"
grep -q "R214 model suggester" "${WORK}/hcb.txt" \
  && ok "banner cites R214" || ko "no R214 banner"

# Allocations enumerated with declared models
for needle in "Agent: conductor_01" "Agent: translator_01" "Agent: deep_reasoner_01"; do
  grep -qF "${needle}" "${WORK}/hcb.txt" && ok "row present: ${needle}" \
    || ko "missing row: ${needle}"
done

# Aspirational flag on conductor (BitNet-b1.58-13B is aspirational)
grep -q "aspirational entry" "${WORK}/hcb.txt" \
  && ok "aspirational flag surfaced" || ko "missing aspirational flag"

# VRAM overrun flag on deep_reasoner (140 GiB > 88 GiB)
grep -q "VRAM requirement 140 GiB exceeds allocation limit 88.0 GiB" "${WORK}/hcb.txt" \
  && ok "VRAM overrun flag surfaced (140 vs 88)" || ko "missing VRAM overrun"

# Smaller-quant alternative offered for deep_reasoner
grep -q "DeepSeek-R1-Distill-Llama-70B-Q4_K_M" "${WORK}/hcb.txt" \
  && ok "smaller-quant Q4_K_M alternative surfaced" \
  || ko "no Q4_K_M alternative"

# Closing flagged banner
grep -q "At least one allocation flagged" "${WORK}/hcb.txt" \
  && ok "closing flagged banner present" || ko "no closing banner"

# --- JSON mode ---
set +e
python3 "${SCRIPT}" --runtime-profile high-concurrency-burst --json > "${WORK}/hcb.json"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "--json rc=1 on flagged profile" || ko "--json rc=${rc}"
python3 - "${WORK}/hcb.json" <<'PY' 2>/dev/null \
  && ok "JSON shape correct + any_flagged=True + 3 allocations" \
  || ko "JSON shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["profile_id"] == "high-concurrency-burst"
assert d["any_flagged"] is True
assert len(d["allocations"]) == 3
# deep_reasoner_01 must carry alternatives
deep = next(a for a in d["allocations"] if a["agent_id"] == "deep_reasoner_01")
assert any("Q4_K_M" in alt["id"] for alt in deep["alternatives"]), deep["alternatives"]
PY

# --- unknown profile → rc=2 ---
set +e
python3 "${SCRIPT}" --runtime-profile does-not-exist >/dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown profile → rc=2" \
  || ko "expected rc=2 on unknown profile, got ${rc}"

# --- usage error (no flag) → rc=2 ---
set +e
python3 "${SCRIPT}" >/dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "missing flag → rc=2" \
  || ko "expected rc=2 on missing flag, got ${rc}"

# --- osctl bridge ---
set +e
out_osctl="$("${OSCTL}" models suggest --list 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl models suggest --list rc=0" \
  || ko "osctl bridge failed (rc=${rc})"
grep -qF "ultra-sovereign-efficiency" <<< "${out_osctl}" \
  && ok "osctl --list surfaces profiles" || ko "osctl --list wrong"

echo
total=$((pass + fail))
echo "test_models_suggest: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
