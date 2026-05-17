#!/usr/bin/env bash
# tests/nspawn/test_osctl_audit_cycle3.sh
#
# Layer 3 test for R200 — `sovereign-osctl audit cycle3` umbrella
# verb. Runs every available cycle-2+3 audit sub-tool and aggregates
# the exit code.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_osctl_audit_cycle3.sh"
echo

[ -x "${OSCTL}" ] && ok "sovereign-osctl executable" \
  || { ko "missing"; exit 1; }

grep -q "cycle3)" "${OSCTL}" \
  && ok "osctl carries R200 'cycle3' audit dispatch" \
  || ko "cycle3 dispatch missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# Stage a catalog with mixed state.
mkdir -p "${WORK}/m1" "${WORK}/m2"
cat > "${WORK}/m1/module.toml" <<'TOML'
name = "m1"
TOML
cat > "${WORK}/m2/module.toml" <<'TOML'
name = "m2"
[signing]
required = true
TOML

# All-clean expected? No — m2 has required signing but no .minisig
# present → signing-audit returns rc=1 → cycle3 returns rc=1.
set +e
SOVEREIGN_OS_SELFDEF_MODULES_DIR="${WORK}" \
  "${OSCTL}" audit cycle3 >"${WORK}/audit.out" 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "audit cycle3 → rc=1 when sub-tool flags issue" \
  || ko "expected rc=1 got ${rc}"

grep -q "R200: comprehensive cycle-2+3 audit" "${WORK}/audit.out" \
  && ok "umbrella banner emitted" || ko "no banner"
grep -q "selfdef modules signing posture (R195/SD-R55)" "${WORK}/audit.out" \
  && ok "signing-audit subsection runs" || ko "no signing-audit"
grep -q "selfdef modules resource quotas (R198/SD-R61)" "${WORK}/audit.out" \
  && ok "resources-audit subsection runs" || ko "no resources-audit"
grep -q "selfdef cycle-2+3 readiness (R187)" "${WORK}/audit.out" \
  && ok "cycle2-status subsection runs" || ko "no cycle2-status"
grep -q "one or more cycle audit sub-tools surfaced issues" "${WORK}/audit.out" \
  && ok "summary cites issues correctly" || ko "missing summary"

# Clean catalog → all-pass rc=0.
mkdir -p "${WORK}/clean/m1"
cat > "${WORK}/clean/m1/module.toml" <<'TOML'
name = "m1"
[signing]
required = false
[resources]
cpu_max = "1.0"
memory_max = "256M"
io_weight = 100
time_max_seconds = 60
TOML
set +e
SOVEREIGN_OS_SELFDEF_MODULES_DIR="${WORK}/clean" \
  "${OSCTL}" audit cycle3 >"${WORK}/audit-clean.out" 2>&1
rc_clean=$?
set -e
grep -q "R200: cycle-2+3 audit clean" "${WORK}/audit-clean.out" \
  && ok "clean catalog → summary cites all-clean" \
  || ko "summary missing on clean: $(tail -5 ${WORK}/audit-clean.out)"

echo
total=$((pass + fail))
echo "test_osctl_audit_cycle3: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
