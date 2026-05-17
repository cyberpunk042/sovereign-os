#!/usr/bin/env bash
# tests/nspawn/test_services_inventory.sh — R240 (SDD-026 Z-15).
# systemd services inventory + failures + timers + shipped catalog.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/services/inventory.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_services_inventory.sh"
echo

[ -x "${SCRIPT}" ] && ok "inventory.py executable" \
  || { ko "missing inventory.py"; exit 1; }
grep -q "R240" "${SCRIPT}" && ok "inventory.py cites R240" || ko "R240 missing"
grep -q "^  services)" "${OSCTL}" \
  && ok "osctl bridges 'services'" || ko "osctl dispatch missing"
grep -q "services list" "${OSCTL}" \
  && ok "osctl help documents 'services'" || ko "osctl help missing"

TMP="$(mktemp -d -t r240.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

# ---- shipped: enumerates units this repo declares ----
set +e
out="$(python3 "${SCRIPT}" shipped --json 2>/dev/null)"
rc=$?
set -e
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R240', d
assert d['count']>=20, f'expected ≥20 shipped units, got {d[\"count\"]}'
# Every row has required fields.
for r in d['units']:
    for f in ('name','kind','description','path','loaded_on_this_host'):
        assert f in r, f'shipped row missing {f}'
    assert r['kind'] in ('service','timer','socket','target'), r
" \
  && ok "shipped --json: ≥20 units with required fields" \
  || ko "shipped shape wrong: ${out:0:200}"

# ---- shipped human render carries banner + glyphs ----
out_h="$(python3 "${SCRIPT}" shipped 2>&1 || true)"
echo "${out_h}" | grep -q "R240 sovereign-os services shipped" \
  && ok "shipped human banner present" || ko "banner missing"
echo "${out_h}" | grep -q "sovereign-alerts-check.service" \
  && ok "shipped lists known alerts-check unit" || ko "alerts-check missing"
echo "${out_h}" | grep -q "sovereign-notify-dispatch.service" \
  && ok "shipped lists R229 notify-dispatch unit" || ko "R229 unit missing"

# ---- list: emits valid JSON even on hosts where systemctl is absent ----
set +e
out="$(python3 "${SCRIPT}" list --json 2>/dev/null)"
set -e
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R240', d
assert 'systemctl_available' in d, d
assert isinstance(d['units'], list), d
" \
  && ok "list --json shape (regardless of systemctl availability)" \
  || ko "list shape wrong"

# ---- list --prefix passthrough (CI may have systemctl + units) ----
set +e
out="$(python3 "${SCRIPT}" list --prefix sovereign --json 2>/dev/null)"
set -e
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['filter']['prefix']=='sovereign', d
# If systemctl unavailable, units stays empty — both branches valid.
" \
  && ok "list --prefix records the filter in output" \
  || ko "prefix not echoed"

# ---- list --state filter accepts the three valid states ----
for state in active inactive failed; do
  set +e
  python3 "${SCRIPT}" list --state "${state}" --json > /dev/null 2>&1
  rc=$?
  set -e
  [ "${rc}" -eq 0 ] && ok "list --state ${state} rc=0" \
    || ko "list --state ${state} rc=${rc}"
done

# ---- list --state with bogus value → rc=2 (argparse) ----
set +e
python3 "${SCRIPT}" list --state nope > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "list --state bogus → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- failures: JSON shape + rc semantics ----
set +e
out="$(python3 "${SCRIPT}" failures --json 2>/dev/null)"
rc=$?
set -e
# rc ∈ {0, 1} — 0 when no failed, 1 when any failed.
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "failures rc ∈ {0,1} (got ${rc})"
else
  ko "unexpected rc=${rc}"
fi
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R240', d
assert isinstance(d['failed'], list), d
assert d['failed_count']==len(d['failed']), d
" \
  && ok "failures JSON shape (failed_count == len(failed))" \
  || ko "failures shape wrong"

# ---- timers ----
set +e
out="$(python3 "${SCRIPT}" timers --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "timers rc=0" || ko "timers rc=${rc}"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R240', d
assert isinstance(d['timers'], list), d
" \
  && ok "timers JSON shape ok" \
  || ko "timers shape wrong"

# ---- osctl bridge: services shipped --json ----
set +e
"${OSCTL}" services shipped --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl services shipped rc ∈ {0,1} (got ${rc})"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R240', d
" \
  && ok "osctl bridge surfaces R240 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" services nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown services subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_services_inventory: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
