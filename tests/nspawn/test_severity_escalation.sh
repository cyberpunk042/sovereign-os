#!/usr/bin/env bash
# tests/nspawn/test_severity_escalation.sh — R273 (E6.M6).
# Severity escalation policy: attention → critical after dwell-time.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/diagnostics/severity-escalation.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_severity_escalation.sh"
echo

[ -x "${SCRIPT}" ] && ok "severity-escalation.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R273\|E6.M6" "${SCRIPT}" && ok "script cites R273/E6.M6" \
  || ko "R273 missing"
grep -q "^  severity)" "${OSCTL}" \
  && ok "osctl bridges 'severity'" || ko "osctl dispatch missing"

TMP="$(mktemp -d -t r273.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
export SOVEREIGN_OS_SEVERITY_STATE="${TMP}/state.json"

# ---- evaluate --json: shape + first-run all-new ----
set +e
out="$(python3 "${SCRIPT}" evaluate --json 2>/dev/null)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "evaluate rc ∈ {0,1} (got ${rc})"
else
  ko "rc unexpected ${rc}"
fi
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R273', d
for k in ('evaluated_at','state_path','escalate_after_seconds',
         'tracked_finding_count','new_count','escalated_count','findings'):
    assert k in d, f'missing {k}'
# Default 4-hour threshold.
assert d['escalate_after_seconds'] == 4*3600, d
" \
  && ok "evaluate --json: shape + 4h default threshold" \
  || ko "evaluate shape wrong"

# ---- second run with no time elapsed: new_count = 0 ----
out2="$(python3 "${SCRIPT}" evaluate --json 2>/dev/null || true)"
echo "${out2}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
# Findings tracked but none NEW this run.
assert d['new_count'] == 0, d
assert d['escalated_count'] == 0, d
" \
  && ok "second run: new_count=0 (state persists)" \
  || ko "state persistence broken"

# ---- in-process: escalation triggers when prior first_seen older than threshold ----
python3 -c "
import importlib.util, json, time, os
os.environ['SOVEREIGN_OS_SEVERITY_STATE'] = '${TMP}/synth.json'
spec = importlib.util.spec_from_file_location('se','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

synth_findings = [{
    'severity': 'attention',
    'source': 'synth',
    'module': 'E0.M0',
    'title': 'synthetic-lingering',
    'detail': 'd',
    'action': 'a',
}]
# Use the REAL identity hash so the prior-state lookup matches.
identity = m.finding_identity(synth_findings[0])

# Seed: one attention finding first_seen 5h ago at the REAL identity.
state_path = m.resolve_state_path()
state_path.parent.mkdir(parents=True, exist_ok=True)
old_ts = time.time() - 5*3600
state = {
    'version': 1,
    'last_eval_at': '2026-05-17T00:00:00Z',
    'findings': {
        identity: {
            'first_seen': old_ts,
            'first_seen_iso': '2026-05-17T00:00:00Z',
            'severity': 'attention',
            'title': 'synthetic-lingering',
            'source': 'synth',
            'module': 'E0.M0',
        }
    }
}
state_path.write_text(json.dumps(state))

report = m.evaluate(escalate_after_seconds=4*3600, source_findings=synth_findings)
assert report['escalated_count'] == 1, report
assert report['findings'][0]['escalated'] is True, report
assert report['findings'][0]['effective_severity'] == 'critical', report
assert report['findings'][0]['observed_severity'] == 'attention', report
" \
  && ok "escalation: attention >= 4h dwell → critical (5h synth)" \
  || ko "escalation logic wrong"

# ---- in-process: NEW finding does NOT escalate (no first_seen yet) ----
python3 -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('se','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
os.environ['SOVEREIGN_OS_SEVERITY_STATE'] = '${TMP}/synth-new.json'

# Empty state, fresh finding.
synth_findings = [{
    'severity': 'attention',
    'source': 'fresh',
    'module': 'E0.M0',
    'title': 'fresh-finding',
    'detail': 'd',
    'action': 'a',
}]
report = m.evaluate(escalate_after_seconds=4*3600, source_findings=synth_findings)
assert report['escalated_count'] == 0, report
assert report['new_count'] == 1, report
assert report['findings'][0]['effective_severity'] == 'attention', report
" \
  && ok "new finding: no escalation (duration < threshold)" \
  || ko "new-finding escalation wrong"

# ---- in-process: critical findings NEVER escalate further ----
python3 -c "
import importlib.util, time, json as j, os
os.environ['SOVEREIGN_OS_SEVERITY_STATE'] = '${TMP}/synth-crit.json'
spec = importlib.util.spec_from_file_location('se','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

synth_findings = [{
    'severity': 'critical',
    'source': 'src',
    'module': 'E0.M0',
    'title': 'already-crit',
    'detail': 'd',
    'action': 'a',
}]
identity = m.finding_identity(synth_findings[0])

state_path = m.resolve_state_path()
state_path.parent.mkdir(parents=True, exist_ok=True)
old_ts = time.time() - 5*3600
state = {
    'version': 1,
    'last_eval_at': '2026-05-17T00:00:00Z',
    'findings': {
        identity: {
            'first_seen': old_ts,
            'first_seen_iso': '2026-05-17T00:00:00Z',
            'severity': 'critical',
            'title': 'already-crit',
            'source': 'src',
            'module': 'E0.M0',
        }
    }
}
state_path.write_text(j.dumps(state))

report = m.evaluate(escalate_after_seconds=4*3600, source_findings=synth_findings)
# escalated counter does NOT bump for already-critical findings
assert report['escalated_count'] == 0, report
" \
  && ok "critical-already: no escalation (already at top severity)" \
  || ko "critical-stays-critical wrong"

# ---- finding_identity: stable hash across re-runs ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('se','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
f1 = {'source':'a','module':'E1.M1','title':'lingering'}
f2 = {'source':'a','module':'E1.M1','title':'lingering','severity':'attention','detail':'changed'}
# Same identity even with different detail/severity.
assert m.finding_identity(f1) == m.finding_identity(f2)
# Different identity when title changes.
f3 = {'source':'a','module':'E1.M1','title':'different'}
assert m.finding_identity(f1) != m.finding_identity(f3)
" \
  && ok "finding_identity: stable across detail changes, varies with title" \
  || ko "identity hashing wrong"

# ---- state verb dumps file ----
out="$(python3 "${SCRIPT}" state --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R273', d
assert 'state_path' in d and 'exists' in d
" \
  && ok "state --json: dump shape ok" \
  || ko "state shape wrong"

# ---- reset without --confirm → rc=2 ----
set +e
python3 "${SCRIPT}" reset > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "reset without --confirm → rc=2" \
  || ko "expected rc=2, got ${rc}"

# ---- reset --confirm clears state ----
set +e
out="$(python3 "${SCRIPT}" reset --confirm --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "reset --confirm rc=0" || ko "reset --confirm rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['removed'] is True, d
" \
  && ok "reset --confirm clears state file" \
  || ko "reset didn't clear"

# ---- osctl bridge ----
set +e
"${OSCTL}" severity state --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl severity state rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R273', d
" \
  && ok "osctl bridge surfaces R273 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" severity nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown severity subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_severity_escalation: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
