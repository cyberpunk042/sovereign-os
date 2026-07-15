#!/usr/bin/env bash
# tests/nspawn/test_trinity.sh
#
# Layer 3 test for sovereign-osctl trinity (R149 — F-master-spec-§-17 closure).
# Verifies status + per-layer subverbs surface the master-spec citations
# and gracefully handle absent components (no Tetragon, no podman, no
# AVX-512 → degrade clearly, don't crash).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
state_dir="$(mktemp -d)"
trap 'rm -rf "${state_dir}"' EXIT
export SOVEREIGN_OS_STATE_DIR="${state_dir}"

echo "tests/nspawn/test_trinity.sh"
echo

# ---------- trinity status ----------
set +e
out="$("${OSCTL}" trinity status 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "trinity status → exit 0"
else
  ko "trinity status broken (rc=${rc})"
fi
# Master spec citation present
if grep -q "master spec § 17" <<< "${out}"; then
  ok "status surfaces master spec § 17 citation"
else
  ko "master spec citation missing from status"
fi
# All 3 modules brief
for module in Pulse Weaver Auditor; do
  if grep -q "\[${module}\]" <<< "${out}"; then
    ok "status surfaces ${module} brief"
  else
    ko "status missing ${module}"
  fi
done

# ---------- trinity pulse ----------
set +e
out="$("${OSCTL}" trinity pulse 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "trinity pulse → exit 0"
else
  ko "trinity pulse broken (rc=${rc})"
fi
# AVX-512 markers enumerated (master spec § 16 instruction set)
for flag in avx512f avx512vl avx512_vnni; do
  if grep -q "${flag}" <<< "${out}"; then
    ok "pulse enumerates ISA flag: ${flag}"
  else
    ko "pulse missing flag: ${flag}"
  fi
done
# CCD pinning citation
if grep -q "CCD0 cores 0-5" <<< "${out}"; then
  ok "pulse surfaces CCD0 cores 0-5 pinning (master spec § 19.2)"
else
  ko "pulse missing CCD pinning info"
fi
# Master spec § 20 (Wasm AOT)
if grep -q "Wasm-to-AVX-512 AOT" <<< "${out}"; then
  ok "pulse cites § 20 Wasm-to-AVX-512 AOT pipeline"
else
  ko "pulse missing § 20 citation"
fi
# Layer B metrics section
if grep -q "sovereign_os_inference_route_total" <<< "${out}"; then
  ok "pulse documents Layer B metric names operators can scrape"
else
  ko "pulse missing Layer B metric pointers"
fi

# ---------- trinity weaver ----------
set +e
out="$("${OSCTL}" trinity weaver 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "trinity weaver → exit 0"
else
  ko "trinity weaver broken (rc=${rc})"
fi
if grep -q "CCD1 cores 6-9" <<< "${out}"; then
  ok "weaver surfaces CCD1 cores 6-9 pinning"
else
  ko "weaver missing CCD1 pinning info"
fi
if grep -q "master spec § 7" <<< "${out}" || grep -q "Vibe state files" <<< "${out}"; then
  ok "weaver cites state fabric per master spec § 7"
else
  ko "weaver missing state-fabric citation"
fi
for state_file in IDENTITY.md SOUL.md AGENTS.md CLAUDE.md; do
  if grep -q "${state_file}" <<< "${out}"; then
    ok "weaver enumerates state file: ${state_file}"
  else
    ko "weaver missing state file: ${state_file}"
  fi
done
if grep -q "R154" <<< "${out}"; then
  ok "weaver names R154 as the round that lands atomic state protocol"
else
  ko "weaver missing R154 forward reference"
fi

# ---------- trinity auditor ----------
set +e
out="$("${OSCTL}" trinity auditor 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "trinity auditor → exit 0"
else
  ko "trinity auditor broken (rc=${rc})"
fi
if grep -q "sovereign-kernel-fence" <<< "${out}"; then
  ok "auditor cites the master spec § 6 sovereign-kernel-fence policy"
else
  ko "auditor missing § 6 policy name"
fi
if grep -q "R155" <<< "${out}"; then
  ok "auditor names R155 as the round that lands Guardian Daemon"
else
  ko "auditor missing R155 forward reference"
fi
if grep -q "sovereign_os_perimeter_status" <<< "${out}"; then
  ok "auditor documents perimeter Layer B metric"
else
  ko "auditor missing perimeter metric pointer"
fi

# ---------- trinity profile list ----------
set +e
out="$("${OSCTL}" trinity profile list 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "master spec § 18" <<< "${out}"; then
  ok "trinity profile list → exit 0 + cites § 18"
else
  ko "profile list broken (rc=${rc})"
fi
for p in ultra-sovereign-efficiency high-concurrency-burst deep-context-synthesis; do
  if grep -q "${p}" <<< "${out}"; then
    ok "profile list contains: ${p}"
  else
    ko "profile list missing: ${p}"
  fi
done

# ---------- trinity profile show <id> ----------
set +e
out="$("${OSCTL}" trinity profile show ultra-sovereign-efficiency 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "ALLOCATIONS" <<< "${out}"; then
  ok "trinity profile show → exit 0 + ALLOCATIONS section"
else
  ko "profile show broken (rc=${rc})"
fi
for kw in "BitNet-b1.58-3B" "core_mask" "GPU STATE" "EXPECTED POWER"; do
  if grep -q "${kw}" <<< "${out}"; then
    ok "profile show surfaces: ${kw}"
  else
    ko "profile show missing: ${kw}"
  fi
done

# ---------- trinity profile show <missing> ----------
set +e
out="$("${OSCTL}" trinity profile show no-such-profile 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "no such profile" <<< "${out}"; then
  ok "profile show missing → exit 1 + clear error"
else
  ko "profile show missing-gate broken (rc=${rc})"
fi

# ---------- trinity profile show with no arg ----------
set +e
out="$("${OSCTL}" trinity profile show 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "usage:" <<< "${out}"; then
  ok "profile show no-arg → exit 2 + usage"
else
  ko "profile show no-arg gate broken (rc=${rc})"
fi

# ---------- trinity profile switch + active ----------
set +e
out="$("${OSCTL}" trinity profile switch high-concurrency-burst 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "active profile set to: high-concurrency-burst" <<< "${out}"; then
  ok "profile switch → exit 0 + confirmation"
else
  ko "profile switch broken (rc=${rc})"
fi

env_file="${state_dir}/active-runtime-profile-env.sh"
if [ -s "${env_file}" ] && grep -qF "# profile: high-concurrency-burst" "${env_file}"; then
  ok "profile switch writes env state beside the active-profile marker"
else
  ko "profile switch did not write the runtime env file under SOVEREIGN_OS_STATE_DIR"
fi

set +e
out="$("${OSCTL}" trinity profile active 2>&1)"
set -e
if grep -q "high-concurrency-burst" <<< "${out}"; then
  ok "profile active returns the just-switched-to profile"
else
  ko "profile active not reflecting switch"
fi

# ---------- profile switch to missing ----------
set +e
out="$("${OSCTL}" trinity profile switch no-such 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "no such profile" <<< "${out}"; then
  ok "profile switch missing → exit 1"
else
  ko "profile switch missing-gate broken (rc=${rc})"
fi

# ---------- profile subverb unknown ----------
set +e
out="$("${OSCTL}" trinity profile bogus 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown trinity profile subcommand" <<< "${out}"; then
  ok "profile bogus → exit 2"
else
  ko "profile bogus gate broken (rc=${rc})"
fi

# ---------- unknown subverb ----------
set +e
out="$("${OSCTL}" trinity bogus 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown trinity subcommand" <<< "${out}"; then
  ok "unknown subverb → exit 2 with clear error"
else
  ko "unknown-subverb gate broken (rc=${rc})"
fi

# ---------- help ----------
help_out="$("${OSCTL}" help 2>&1)"
for kw in "trinity status" "trinity pulse" "trinity weaver" "trinity auditor"; do
  if grep -q "${kw}" <<< "${help_out}"; then
    ok "help documents: ${kw}"
  else
    ko "help missing: ${kw}"
  fi
done

# ---------- dispatch ----------
if grep -qE "trinity\)\s+cmd_trinity" "${OSCTL}"; then
  ok "dispatcher routes 'trinity' → cmd_trinity"
else
  ko "dispatch entry missing"
fi

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_trinity: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
