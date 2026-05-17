#!/usr/bin/env bash
# tests/nspawn/test_selfdef_resources_audit.sh
#
# Layer 3 test for R198 — selfdef SD-R61 [resources] catalog audit.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/selfdef-resources-audit.py"

echo "tests/nspawn/test_selfdef_resources_audit.sh"
echo

[ -x "${SCRIPT}" ] && ok "selfdef-resources-audit.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R198" "${SCRIPT}" \
  && ok "carries R198 marker" || ko "R198 marker missing"
grep -q "SD-R61" "${SCRIPT}" \
  && ok "cites selfdef SD-R61 (cross-repo provenance)" \
  || ko "SD-R61 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

mkdir -p "${WORK}/m1" "${WORK}/m2" "${WORK}/m3"
cat > "${WORK}/m1/module.toml" <<'TOML'
name = "m1"
TOML
cat > "${WORK}/m2/module.toml" <<'TOML'
name = "m2"
[resources]
cpu_max = "1.0"
memory_max = "512M"
TOML
cat > "${WORK}/m3/module.toml" <<'TOML'
name = "m3"
[resources]
cpu_max = "2.0"
memory_max = "1G"
io_weight = 200
time_max_seconds = 60
TOML

# Human output
set +e
out="$("${SCRIPT}" --dir "${WORK}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "rc=0 on mixed catalog" || ko "rc=${rc}"
grep -q "unquotad=1" <<< "${out}" \
  && ok "counts: unquotad correct" || ko "wrong unquotad count"
grep -q "partial=1" <<< "${out}" \
  && ok "counts: partial correct" || ko "wrong partial count"
grep -q "full=1" <<< "${out}" \
  && ok "counts: full correct" || ko "wrong full count"
grep -q "✓ full" <<< "${out}" \
  && ok "marker: m3 shows ✓ full" || ko "m3 marker missing"

# JSON shape
set +e
out_json="$("${SCRIPT}" --dir "${WORK}" --json 2>&1)"
set -e
if python3 -c "
import json
d = json.loads('''${out_json}''')
assert d['schema_version'] == '1.0.0'
assert d['total'] == 3
assert d['counts']['full'] == 1
assert d['counts']['partial'] == 1
assert d['counts']['unquotad'] == 1
# Verify field passthrough on m3
m3 = next(m for m in d['modules'] if m['name'] == 'm3')
assert m3['fields']['cpu_max'] == '2.0'
assert m3['fields']['memory_max'] == '1G'
assert m3['fields']['io_weight'] == 200
assert m3['fields']['time_max_seconds'] == 60
" 2>/dev/null; then
  ok "--json schema + per-module fields correct"
else
  ko "--json shape wrong: ${out_json}"
fi

# Missing dir → rc=2
set +e
"${SCRIPT}" --dir "${WORK}/no-such" 2>/dev/null
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "missing dir → rc=2" || ko "rc=${rc}"

echo
total=$((pass + fail))
echo "test_selfdef_resources_audit: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
