#!/usr/bin/env bash
# R310 (E2.M16) — container-vs-system install-mode advisor L3.
#
# Operator-named (§1b mandate row): "non docker vs docker install ?
# when possible ? container level vs system level".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/install/install-mode-advisor.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope + ≥10 components ──────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R310'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M16'
assert d['total_count'] >= 10
" || fail "envelope"
pass "1. list --json envelope + ≥10 components"

# ── 2. Operator-named anchor components present ────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {c['name'] for c in d['components']}
must = {'ollama', 'vllm', 'selfdef-daemon', 'suricata',
        'tailscale', 'cloudflared', 'traefik',
        'prometheus', 'grafana', 'polarproxy'}
missing = must - names
assert not missing, missing
" || fail "anchors"
pass "2. operator-named anchors present (ollama/vllm/tailscale/cloudflared/traefik + selfdef)"

# ── 3. Every component has full decision schema ────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for c in d['components']:
    for k in ('name', 'axis', 'isolation_need', 'dependency_footprint',
              'ipc_requirement', 'root_required', 'gpu_passthrough',
              'kernel_module', 'recommendation', 'rationale',
              'system_tradeoff', 'container_tradeoff'):
        assert k in c, (k, c['name'])
" || fail "schema"
pass "3. every component carries full decision schema (12 fields)"

# ── 4. --axis filter narrows ───────────────────────────────
out_n="$(python3 "${SCRIPT}" list --axis network --json)"
echo "${out_n}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert all(c['axis'] == 'network' for c in d['components'])
assert d['filtered_count'] >= 4
" || fail "axis filter"
pass "4. --axis network filter narrows (≥4 components)"

# ── 5. recommend buckets by system / container / either ───
out_r="$(python3 "${SCRIPT}" recommend --json)"
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R310'
rec = d['recommendations']
assert 'system' in rec and 'container' in rec and 'either' in rec
total = sum(len(v) for v in rec.values())
assert total == d['total_components'], (total, d['total_components'])
" || fail "recommend buckets"
pass "5. recommend buckets all components into system / container / either"

# ── 6. Network-namespace-required → system ─────────────────
out_s="$(python3 "${SCRIPT}" show suricata --json)"
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['component']
assert c['root_required'] is True
assert d['effective_recommendation'] == 'system', d['effective_recommendation']
" || fail "suricata system"
pass "6. network-namespace-required component (suricata) → system"

# ── 7. Userspace + isolation-friendly → container ──────────
out_c="$(python3 "${SCRIPT}" show traefik --json)"
echo "${out_c}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['component']
assert c['root_required'] is False
assert d['effective_recommendation'] == 'container'
" || fail "traefik container"
pass "7. userspace + isolation-friendly (traefik) → container"

# ── 8. Unknown component → rc=1 + structured error ─────────
RC=0
python3 "${SCRIPT}" show no-such-component --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "show unknown rc expected 1; got ${RC}"
pass "8. show unknown component → rc=1 + structured error"

# ── 9. Operator overlay can pin recommendation ────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[recommendation_override]
ollama = "container"
suricata = "system"
TOML

out_ov="$(python3 "${SCRIPT}" show ollama --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['effective_recommendation'] == 'container'
assert d['component']['operator_pinned_recommendation'] == 'container'
# Default recommendation must be preserved separately.
assert d['component']['recommendation'] == 'either'
" || fail "overlay pin"
rm -f "${overlay}"
pass "9. operator overlay can pin per-component recommendation (preserves default)"

# ── 10. sovereign-osctl install-mode dispatch ──────────────
out_disp="$(bash "${OSCTL}" install-mode recommend --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R310'
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl install-mode dispatches"

echo "ALL OK"
