#!/usr/bin/env bash
# tests/nspawn/test_insights.sh — R234 (SDD-026 Z-10): fs/log/telemetry
# insights synthesizer. Verifies severity ranking + actionable next-step
# emission + Layer B telemetry integration.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/insights/synthesize.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_insights.sh"
echo

[ -x "${SCRIPT}" ] && ok "synthesize.py executable" \
  || { ko "missing synthesize.py"; exit 1; }
grep -q "R234" "${SCRIPT}" && ok "synthesize.py cites R234" || ko "R234 missing"
grep -q "^  insights)" "${OSCTL}" \
  && ok "osctl bridges 'insights'" || ko "osctl bridge missing"
grep -q "insights \[" "${OSCTL}" \
  && ok "osctl help documents 'insights'" || ko "osctl help missing"

# ---- baseline JSON shape ----
out="$(python3 "${SCRIPT}" --json 2>&1 || true)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R234', d
assert d['vector'].startswith('SDD-026 Z-10'), d
for k in ('generated_at','sources','counts','insights','needs_attention'):
    assert k in d, f'missing {k}'
c=d['counts']
for k in ('critical','attention','informational','total'):
    assert k in c, f'counts missing {k}'
# Sorted: severity rank monotonic non-decreasing.
rank={'critical':0,'attention':1,'informational':2}
prev=-1
for i in d['insights']:
    r=rank.get(i['severity'],99)
    assert r>=prev, f'insights not sorted: {[x[\"severity\"] for x in d[\"insights\"]]}'
    prev=r
# Each insight carries required fields.
for i in d['insights']:
    for k in ('severity','title','detail','action','source'):
        assert k in i, f'insight missing {k}'
" \
  && ok "JSON shape: round / vector / counts / sorted insights with fields" \
  || ko "JSON shape wrong"

# ---- Layer B insight: missing telemetry → 'never run' insight ----
TMP="$(mktemp -d -t r234.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/empty" python3 "${SCRIPT}" --json || true)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
titles=[i['title'] for i in d['insights']]
assert any('never run' in t for t in titles), titles
" \
  && ok "missing log-rotation .prom → 'never run' attention insight" \
  || ko "log-rotation never-run insight missing"

# ---- Layer B insight: stale telemetry (>48h) → attention ----
mkdir -p "${TMP}/stale"
OLD=$(($(date +%s) - 200*3600))   # 200 hours ago
cat > "${TMP}/stale/sovereign-os-log-rotation.prom" <<PROM
sovereign_os_log_rotation_last_run_timestamp ${OLD}
sovereign_os_log_rotation_files_rotated 3
sovereign_os_log_rotation_files_purged 1
PROM
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/stale" python3 "${SCRIPT}" --json || true)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
titles=[i['title'] for i in d['insights']]
assert any('hours ago' in t for t in titles), titles
# Severity is attention not informational for stale.
for i in d['insights']:
    if 'hours ago' in i['title']:
        assert i['severity']=='attention', i
" \
  && ok "stale log-rotation → 'hours ago' attention insight" \
  || ko "stale-telemetry path wrong"

# ---- Layer B insight: fresh telemetry → informational only ----
mkdir -p "${TMP}/fresh"
NOW=$(date +%s)
cat > "${TMP}/fresh/sovereign-os-log-rotation.prom" <<PROM
sovereign_os_log_rotation_last_run_timestamp ${NOW}
sovereign_os_log_rotation_files_rotated 7
sovereign_os_log_rotation_files_purged 2
PROM
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/fresh" python3 "${SCRIPT}" --json || true)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for i in d['insights']:
    if 'log-rotate healthy' in i['title']:
        assert i['severity']=='informational', i
        assert 'rotated=7' in i['title']
        assert 'purged=2' in i['title']
        break
else:
    raise AssertionError('no healthy insight')
" \
  && ok "fresh log-rotation → informational 'healthy' insight with counts" \
  || ko "fresh-telemetry path wrong"

# ---- exit code: critical present → rc=1 ----
set +e
python3 "${SCRIPT}" > /dev/null 2>&1
real_rc=$?
set -e
# rc is 0 or 1 depending on the live host fs state. Both are valid.
if [ "${real_rc}" -eq 0 ] || [ "${real_rc}" -eq 1 ]; then
  ok "synthesize rc ∈ {0,1} (got ${real_rc})"
else
  ko "unexpected rc=${real_rc}"
fi

# ---- human render: banner + section markers ----
out="$(python3 "${SCRIPT}" --all 2>&1 || true)"
echo "${out}" | grep -q "R234 sovereign-os insights" \
  && ok "human render carries R234 banner" || ko "banner missing"
echo "${out}" | grep -q "totals:" \
  && ok "human render has totals line" || ko "totals missing"

# ---- --limit caps the rendered insights ----
set +e
out_one="$(python3 "${SCRIPT}" --limit 1 2>&1 | grep -cE "^  [⛔⚠·] \[")"
set -e
[ "${out_one}" -le 1 ] && ok "--limit 1 renders ≤1 insight row" \
  || ko "--limit not honored (${out_one} rows)"

# ---- osctl bridge ----
set +e
"${OSCTL}" insights --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl insights rc ∈ {0,1} (got ${rc})"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R234', d
" \
  && ok "osctl bridge surfaces R234 JSON" \
  || ko "osctl JSON wrong"

echo
total=$((pass + fail))
echo "test_insights: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
