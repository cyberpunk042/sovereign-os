#!/usr/bin/env bash
# tests/nspawn/test_osctl_install_suggest_modules.sh
#
# Layer 3 test for R185 — `sovereign-osctl install suggest-modules
# --profile <p>` recommends which selfdef modules to enable based on
# profile + probed hardware.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_osctl_install_suggest_modules.sh"
echo

[ -x "${OSCTL}" ] && ok "sovereign-osctl executable" \
  || { ko "missing"; exit 1; }

grep -q "suggest-modules)" "${OSCTL}" \
  && ok "install carries R185 'suggest-modules' dispatch" \
  || ko "suggest-modules dispatch missing"

# ---------- sain-01 profile ----------
set +e
out_s01="$("${OSCTL}" install suggest-modules --profile sain-01 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "sain-01 → rc=0" || ko "sain-01 rc=${rc}: ${out_s01}"
grep -q "# R185:" <<< "${out_s01}" \
  && ok "output carries R185 marker" || ko "no R185 marker"
grep -q "# profile: sain-01" <<< "${out_s01}" \
  && ok "sain-01 profile is echoed" || ko "missing profile echo"
grep -q "# detected:" <<< "${out_s01}" \
  && ok "detected line shows host probe summary" \
  || ko "no detected line"
grep -q "# Copy-paste this block" <<< "${out_s01}" \
  && ok "operator-actionable copy-paste hint present" \
  || ko "no copy-paste hint"

# ---------- developer profile: AVX-512 host → hardware-tune-cache only ----------
set +e
out_dev="$("${OSCTL}" install suggest-modules --profile developer 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "developer → rc=0" || ko "developer rc=${rc}"
# On CI hosts (AVX-512 mostly present) we should see hardware-tune-cache
# but NOT bitnet-gpu-inference (developer profile doesn't recommend GPU
# inference modules even if a GPU is present).
! grep -q "bitnet-gpu-inference" <<< "${out_dev}" \
  && ok "developer profile: bitnet-gpu-inference NOT recommended" \
  || ko "developer should not recommend bitnet-gpu-inference"

# ---------- minimal profile: never recommends modules ----------
set +e
out_min="$("${OSCTL}" install suggest-modules --profile minimal 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "minimal → rc=0" || ko "minimal rc=${rc}"
grep -q "no selfdef modules recommended for minimal" <<< "${out_min}" \
  && ok "minimal profile: explicit 'no modules' message" \
  || ko "minimal output unexpected: ${out_min}"

# ---------- old-workstation profile: same as minimal ----------
set +e
out_ow="$("${OSCTL}" install suggest-modules --profile old-workstation 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "old-workstation → rc=0" || ko "old-workstation rc=${rc}"
grep -q "no selfdef modules recommended for old-workstation" <<< "${out_ow}" \
  && ok "old-workstation profile: explicit 'no modules' message" \
  || ko "old-workstation output unexpected"

# ---------- unknown profile: rc=2 with clear error ----------
set +e
out_un="$("${OSCTL}" install suggest-modules --profile bogus 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown profile → rc=2" \
  || ko "unknown profile rc=${rc}: ${out_un}"

# ---------- help mentions suggest-modules ----------
set +e
out_help="$("${OSCTL}" install bogus-subcmd 2>&1)"
set -e
grep -q "suggest-modules" <<< "${out_help}" \
  && ok "install help table mentions suggest-modules" \
  || ko "help table missing suggest-modules"

echo
total=$((pass + fail))
echo "test_osctl_install_suggest_modules: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
