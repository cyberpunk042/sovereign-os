#!/usr/bin/env bash
# tests/nspawn/test_assistant_next_steps.sh — R282 (E5.M10).
# Operator "assistant feel" next-best-step synthesizer + curated packs.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/diagnostics/assistant-next-steps.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_assistant_next_steps.sh"
echo

[ -x "${SCRIPT}" ] && ok "assistant-next-steps.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R282\|E5.M10" "${SCRIPT}" && ok "script cites R282/E5.M10" \
  || ko "R282 missing"
grep -q "^  next-steps)" "${OSCTL}" \
  && ok "osctl bridges 'next-steps'" || ko "osctl dispatch missing"

# ---- packs --json: 5 curated packs ----
out="$(python3 "${SCRIPT}" packs --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R282', d
# 5 cycle-9 packs shipped.
assert d['pack_count'] == 5, d
names = {p['name'] for p in d['packs']}
for required in ('inference-burst','headless-server','low-power',
                 'spec-conformance','graceful-shutdown-rehearsal'):
    assert required in names, f'missing pack {required}'
# Each pack has step_count >= 3.
for p in d['packs']:
    assert p['step_count'] >= 3, p
    assert p['summary']
    assert p['operator_note']
" \
  && ok "packs --json: 5 named packs with ≥3 steps each + summary + operator_note" \
  || ko "packs shape wrong"

# ---- next --json: shape contract ----
set +e
out="$(python3 "${SCRIPT}" next --json 2>/dev/null)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "next rc ∈ {0,1} (got ${rc})"
else
  ko "rc unexpected ${rc}"
fi
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R282', d
for f in ('evaluated_at','counts','next_steps','rendered_count','total_count'):
    assert f in d, f'missing {f}'
c = d['counts']
for k in ('critical','attention','informational','total'):
    assert k in c, c
# Findings are sorted by severity rank.
rank = {'critical':0,'attention':1,'informational':2}
prev = -1
for step in d['next_steps']:
    r = rank.get(step.get('severity','informational'), 99)
    assert r >= prev, [s.get('severity') for s in d['next_steps']]
    prev = r
" \
  && ok "next --json: shape + sorted-by-severity findings" \
  || ko "next shape wrong"

# ---- severity filter ----
set +e
out="$(python3 "${SCRIPT}" next --severity critical --json 2>/dev/null)"
set -e
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for step in d['next_steps']:
    assert step['severity'] == 'critical', step
" \
  && ok "--severity critical filters to critical-only" \
  || ko "severity filter wrong"

# ---- --limit caps render ----
set +e
out="$(python3 "${SCRIPT}" next --limit 1 --json 2>/dev/null)"
set -e
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert len(d['next_steps']) <= 1, d
" \
  && ok "--limit 1 caps rendered next_steps" \
  || ko "limit wrong"

# ---- apply-pack inference-burst --dry-run ----
out="$(python3 "${SCRIPT}" apply-pack inference-burst --dry-run --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R282', d
assert d['pack'] == 'inference-burst', d
assert d['dry_run'] is True, d
assert isinstance(d['results'], list)
assert len(d['results']) >= 3, d
# Every step's verb references a sovereign-osctl call (cycle-9
# advisory-only doctrine).
for s in d['results']:
    assert s['verb'].startswith('sovereign-osctl'), s
" \
  && ok "apply-pack inference-burst --dry-run: ≥3 advisory steps, each a sovereign-osctl call" \
  || ko "apply-pack shape wrong"

# ---- apply-pack unknown → rc=2 ----
set +e
python3 "${SCRIPT}" apply-pack ghost > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "apply-pack unknown → rc=2" \
  || ko "expected rc=2, got ${rc}"

# ---- spec-conformance pack includes the master-spec validators ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ans','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
sc = m.PACKS['spec-conformance']
verbs = ' '.join(s.get('verb','') for s in sc['steps'])
# Master-spec validators that MUST land in this pack:
assert 'ram-advisor' in verbs, verbs
assert 'memory-profile' in verbs, verbs
assert 'avx512-advisor' in verbs, verbs
assert 'pcie-policy' in verbs, verbs
assert 'wasm-aot' in verbs, verbs
assert 'zmm-ternary' in verbs, verbs
" \
  && ok "spec-conformance pack: ram + memory-profile + avx512 + pcie + wasm-aot + zmm-ternary" \
  || ko "spec-conformance pack incomplete"

# ---- inference-burst pack includes kernel + cpu-mode + gpu-card + power ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ans','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ib = m.PACKS['inference-burst']
verbs = ' '.join(s.get('verb','') for s in ib['steps'])
assert 'kernel apply inference-burst' in verbs, verbs
assert 'cpu-mode' in verbs, verbs
assert 'gpu-card-advisor' in verbs, verbs
assert 'power-status' in verbs, verbs
" \
  && ok "inference-burst pack: kernel + cpu-mode + gpu-card + power" \
  || ko "inference-burst pack incomplete"

# ---- graceful-shutdown-rehearsal pack uses R262 + R277 ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ans','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
gs = m.PACKS['graceful-shutdown-rehearsal']
verbs = ' '.join(s.get('verb','') for s in gs['steps'])
assert 'power-shutdown' in verbs, verbs
assert 'service-deps drain' in verbs, verbs
" \
  && ok "graceful-shutdown-rehearsal pack: power-shutdown + service-deps drain" \
  || ko "graceful-shutdown pack incomplete"

# ---- human render: banner + numbered list ----
out_h="$(python3 "${SCRIPT}" next --severity informational --limit 3 2>&1 || true)"
echo "${out_h}" | grep -q "R282 sovereign-os assistant-next-steps" \
  && ok "next human banner present" || ko "banner missing"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r282.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" next-steps packs --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl next-steps packs rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R282', d
" \
  && ok "osctl bridge surfaces R282 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" next-steps nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown next-steps subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_assistant_next_steps: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
