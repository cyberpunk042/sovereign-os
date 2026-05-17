#!/usr/bin/env bash
# R297 (E2.M11) — network install-layer advisor L3.
#
# Operator-named (§1b mandate row): "the DNS, the Cloudflared ?
# the tailscale, Traefik, non docker vs docker install ? when
# possible ? container level vs system level".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/network/install-layer-advisor.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope ──────────────────────────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R297'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M11'
assert d['component_count'] == 4
" || fail "envelope"
pass "1. list --json envelope (4 components)"

# ── 2. The 4 operator-named components are present ───────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {c['name'] for c in d['components']}
for n in ('dns', 'cloudflared', 'tailscale', 'traefik'):
    assert n in names, (n, names)
" || fail "operator-named components missing"
pass "2. dns + cloudflared + tailscale + traefik all present"

# ── 3. Every component has BOTH docker + system layer info ────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for c in d['components']:
    layers = {l['layer'] for l in c['layers']}
    assert layers == {'docker', 'system'}, (c['name'], layers)
    for l in c['layers']:
        assert 'supported' in l, (c['name'], l)
        assert 'install' in l, (c['name'], l)
        assert isinstance(l['install'], list) and l['install']
        assert 'pros' in l and l['pros']
        assert 'cons' in l and l['cons']
" || fail "per-layer shape"
pass "3. every component has both docker + system layers with install / pros / cons"

# ── 4. default_layer is set per operator preference ──────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
defaults = {c['name']: c['default_layer'] for c in d['components']}
# Operator-pinned defaults per §1b interpretation:
#   dns + cloudflared + tailscale default = system
#   traefik default = docker (docker label routing FTW)
assert defaults['dns'] == 'system', defaults
assert defaults['cloudflared'] == 'system', defaults
assert defaults['tailscale'] == 'system', defaults
assert defaults['traefik'] == 'docker', defaults
" || fail "defaults"
pass "4. defaults: dns/cloudflared/tailscale = system; traefik = docker"

# ── 5. show <component> ────────────────────────────────────
out_show="$(python3 "${SCRIPT}" show cloudflared --json)"
echo "${out_show}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['component']
assert c['name'] == 'cloudflared'
assert c['category'] == 'ingress-tunnel'
assert any('cloudflared service install' in s for l in c['layers']
           for s in l['install'])
" || fail "show shape"
pass "5. show <component> renders install commands"

# ── 6. coexist verb surfaces cross-component conflict notes ──
out_co="$(python3 "${SCRIPT}" coexist --json)"
echo "${out_co}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert len(d['rows']) == 4
notes = d['coexistence_notes']
# At least the port-53 + docker.sock notes.
joined = ' '.join(notes)
assert 'port 53' in joined, joined
assert 'docker.sock' in joined, joined
" || fail "coexist shape"
pass "6. coexist verb surfaces port-53 + docker.sock conflict notes"

# ── 7. recommend verb emits per-component recommendation ──────
out_rec="$(python3 "${SCRIPT}" recommend --json)"
echo "${out_rec}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
recs = {r['component']: r['recommended_layer'] for r in d['recommendations']}
assert recs['traefik'] == 'docker'
assert recs['tailscale'] == 'system'
" || fail "recommend shape"
pass "7. recommend verb emits per-component recommendation"

# ── 8. Unknown component → rc=1 + structured error ────────────
RC=0
python3 "${SCRIPT}" show no-such-component --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "expected rc=1; got ${RC}"
err="$(python3 "${SCRIPT}" show no-such-component --json 2>&1 1>/dev/null)" || true
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'unknown component' in d['error']
" || fail "unknown error JSON"
pass "8. unknown component → rc=1 + structured error JSON"

# ── 9. Operator overlay replaces catalog entirely ────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[components]]
name           = "operator-custom-proxy"
category       = "reverse-proxy"
summary        = "operator test entry"
default_layer  = "system"

[[components.layers]]
layer     = "system"
supported = true
install   = ["echo install-stub"]
pros      = ["operator-pull only"]
cons      = ["test fixture"]

[[components.layers]]
layer     = "docker"
supported = false
install   = ["echo not-supported"]
pros      = ["n/a"]
cons      = ["operator-mandated system-only"]
TOML

out_ov="$(python3 "${SCRIPT}" list --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [c['name'] for c in d['components']]
assert names == ['operator-custom-proxy'], names
" || fail "overlay list-replace"
rm -f "${overlay}"
pass "9. operator overlay (R283/SDD-030) replaces catalog"

# ── 10. Malformed overlay → defaults + _parse_error ──────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" list --config "${bad}" --json)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['component_count'] == 4  # defaults kept
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "10. malformed overlay → defaults + _parse_error"

# ── 11. sovereign-osctl dispatch + read-only invariant ────────
out_disp="$(bash "${OSCTL}" network-install-advisor list --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R297'
" || fail "sovereign-osctl dispatch"
out2="$(python3 "${SCRIPT}" list --json)"
[[ "${out}" == "${out2}" ]] || fail "list output changed between calls"
pass "11. sovereign-osctl dispatch + read-only invariant"

echo "ALL OK"
