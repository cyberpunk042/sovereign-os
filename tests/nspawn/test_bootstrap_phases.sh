#!/usr/bin/env bash
# tests/nspawn/test_bootstrap_phases.sh
#
# Layer 3 test for R162 — scripts/bootstrap/phases.sh +
# sovereign-osctl bootstrap phases (master spec § 12 chronological
# 5-phase pipeline surface).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/bootstrap/phases.sh"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_bootstrap_phases.sh"
echo

[ -x "${SCRIPT}" ] && ok "phases.sh executable" || { ko "missing"; exit 1; }
[ -x "${OSCTL}" ]  && ok "sovereign-osctl executable" || ko "osctl missing"

# ---------- master spec citation ----------
if grep -q "master spec § 12" "${SCRIPT}"; then
  ok "phases.sh cites master spec § 12"
else
  ko "master spec § 12 citation missing"
fi

# ---------- all 5 phases enumerated ----------
set +e
out="$(bash "${SCRIPT}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "phases.sh exit 0 (all artifacts present)"
else
  ko "phases.sh rc=${rc}"
fi
for ph in "Phase I" "Phase II" "Phase III" "Phase IV" "Phase V"; do
  if grep -qF "═══ ${ph} ═══" <<< "${out}"; then
    ok "output contains: ${ph}"
  else
    ko "output missing: ${ph}"
  fi
done

# ---------- verbatim master spec section anchors ----------
for kw in "Minimal Trixie" "Zen 5 Kernel" "Storage Layer" "Edge Isolation" "Tetragon" "Guardian"; do
  if grep -q "${kw}" <<< "${out}"; then
    ok "output anchors: ${kw}"
  else
    ko "output missing anchor: ${kw}"
  fi
done

# ---------- artifact presence checks (R152-R159 outputs ALL referenced) ----------
for artifact in \
    "scripts/build/01-bootstrap-forge.sh" \
    "scripts/build/04-kernel-compile.sh" \
    "scripts/hooks/post-install/zfs-arc-clamp.sh" \
    "scripts/network/render-asymmetric.sh" \
    "scripts/auditor/guardian-core.py" \
    "scripts/weaver/atomic-state.py" \
    "systemd/system/sovereign-guardian-core.service"; do
  if grep -q "${artifact}" <<< "${out}"; then
    ok "artifact enumerated: ${artifact}"
  else
    ko "artifact missing from inventory: ${artifact}"
  fi
done

# ---------- --phase filter ----------
set +e
out_iii="$(bash "${SCRIPT}" --phase III 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "Phase III" <<< "${out_iii}" && ! grep -q "═══ Phase I ═══" <<< "${out_iii}"; then
  ok "--phase III filters to phase 3 only"
else
  ko "--phase filter broken"
fi

# Accepts Arabic numerals too
set +e
out_3="$(bash "${SCRIPT}" --phase 3 2>&1)"
set -e
if grep -q "Storage Layer" <<< "${out_3}"; then
  ok "--phase 3 (Arabic) accepted"
else
  ko "--phase 3 Arabic numeral broken"
fi

# Bad phase
set +e
out_bad="$(bash "${SCRIPT}" --phase 9 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ]; then
  ok "--phase 9 → rc=2 (out of range)"
else
  ko "bad --phase didn't fail correctly"
fi

# ---------- --json output ----------
set +e
out_json="$(bash "${SCRIPT}" --json 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "--json exit 0"
else
  ko "--json rc=${rc}"
fi
# Parseable JSON
if python3 -c "import json,sys; d=json.loads('''${out_json}'''); assert len(d['phases'])==5" 2>/dev/null; then
  ok "--json parseable + contains 5 phases"
else
  ko "--json malformed or wrong phase count"
fi
# overall_missing field
if grep -q '"overall_missing"' <<< "${out_json}"; then
  ok "--json includes overall_missing field"
else
  ko "overall_missing field missing"
fi

# ---------- missing artifact path → rc=1 ----------
# Stash one artifact temporarily to simulate a gap
GUARDIAN_PATH="${__REPO_ROOT}/scripts/auditor/guardian-core.py"
[ -f "${GUARDIAN_PATH}" ] && mv "${GUARDIAN_PATH}" "${GUARDIAN_PATH}.bak" || true
set +e
out_gap="$(bash "${SCRIPT}" --phase V 2>&1)"
rc=$?
set -e
[ -f "${GUARDIAN_PATH}.bak" ] && mv "${GUARDIAN_PATH}.bak" "${GUARDIAN_PATH}" || true
if [ "${rc}" -eq 1 ] && grep -q "guardian-core" <<< "${out_gap}" && grep -q "MISSING" <<< "${out_gap}"; then
  ok "missing artifact → rc=1 + MISSING marker"
else
  ko "missing-artifact detection broken (rc=${rc})"
fi

# ---------- sovereign-osctl bootstrap phases dispatch ----------
set +e
out="$("${OSCTL}" bootstrap phases --phase 1 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "Phase I" <<< "${out}"; then
  ok "sovereign-osctl bootstrap phases dispatches the script"
else
  ko "osctl phases dispatch broken (rc=${rc})"
fi

# Help text updated
set +e
out_help="$("${OSCTL}" bootstrap help 2>&1)"
set -e
if grep -q "phases" <<< "${out_help}" && grep -q "5-phase pipeline" <<< "${out_help}"; then
  ok "osctl bootstrap help documents the phases subverb"
else
  ko "osctl help missing phases doc"
fi

echo
total=$((pass + fail))
echo "test_bootstrap_phases: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
