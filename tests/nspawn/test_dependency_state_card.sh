#!/usr/bin/env bash
# tests/nspawn/test_dependency_state_card.sh — R274 (E4.M6).
# Network-state-reactive grey-out card on the dashboard.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SERVE="${__REPO_ROOT}/scripts/dashboard/serve.py"

echo "tests/nspawn/test_dependency_state_card.sh"
echo

grep -q "R274\|E4.M6" "${SERVE}" && ok "serve.py cites R274/E4.M6" \
  || ko "R274 missing"
grep -q "card_dependency_state" "${SERVE}" \
  && ok "card_dependency_state function present" || ko "card fn missing"
grep -q "greyed_card_ids" "${SERVE}" \
  && ok "greyed_card_ids field documented" || ko "greyed_card_ids missing"

# ---- /api/dependency_state endpoint via --once ----
PORT=$(python3 -c "import random; print(random.randint(18800,18900))")
python3 "${SERVE}" --bind "127.0.0.1:${PORT}" --once > /tmp/r274-srv.log 2>&1 &
SRV_PID=$!
for _ in 1 2 3 4 5 6 7 8; do
  grep -q serving /tmp/r274-srv.log 2>/dev/null && break
  sleep 0.5
done

set +e
curl -fsS "http://127.0.0.1:${PORT}/api/dependency_state" > /tmp/r274-resp.json 2>/dev/null
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "GET /api/dependency_state rc=0" \
  || ko "endpoint rc=${rc}"

python3 -c "
import json
card = json.load(open('/tmp/r274-resp.json'))
assert card['id'] == 'dependency_state'
d = card['data']
assert d['round'] == 'R274', d
for f in ('down_components','greyed_card_ids','greyed_features','summary','needs_attention'):
    assert f in d, f'missing {f}'
assert isinstance(d['down_components'], list)
assert isinstance(d['greyed_card_ids'], list)
assert isinstance(d['greyed_features'], list)
" \
  && ok "response shape: card.id + data.{down_components,greyed_card_ids,greyed_features}" \
  || ko "response shape wrong"

wait "${SRV_PID}" 2>/dev/null || true
rm -f /tmp/r274-resp.json /tmp/r274-srv.log

# ---- in-process synthesis: feed synthetic network-status output ----
python3 -c "
import importlib.util, subprocess, sys, os
# Monkey-patch subprocess.run to return a controlled JSON.
spec = importlib.util.spec_from_file_location('serve','${SERVE}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class FakeResult:
    def __init__(self, stdout, returncode=0, stderr=''):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr

# Synthetic: internet OK, docker down, cloudflared down.
synth = {
    'components': [
        {'component':'internet','status':'ok','detail':'ok','alternative': None},
        {'component':'dns','status':'ok','detail':'ok','alternative': None},
        {'component':'docker','status':'down',
         'detail':'daemon unreachable',
         'alternative':'use podman OR system-level install'},
        {'component':'cloudflared','status':'down',
         'detail':'tunnel down',
         'alternative':'use tailscale-funnel'},
        {'component':'tailscale','status':'ok','detail':'ok','alternative': None},
        {'component':'traefik','status':'ok','detail':'ok','alternative': None},
    ]
}

import json as j
real_run = subprocess.run
def fake_run(cmd, *args, **kwargs):
    return FakeResult(j.dumps(synth))
m.subprocess.run = fake_run

card = m.card_dependency_state()
data = card['data']
m.subprocess.run = real_run

assert card['id'] == 'dependency_state'
assert data['round'] == 'R274'
# 2 components down (docker + cloudflared).
assert len(data['down_components']) == 2, data
down_ids = {c['component'] for c in data['down_components']}
assert down_ids == {'docker','cloudflared'}, down_ids
# greyed_card_ids must include install_paths (depends on docker) and
# others depending only on internet are NOT greyed (internet=ok).
assert 'install_paths' in data['greyed_card_ids'], data
# models / toolchains / fine_tune depend only on internet (which is ok)
# so they must NOT be greyed.
for not_greyed in ('models','toolchains','fine_tune'):
    assert not_greyed not in data['greyed_card_ids'], (not_greyed, data)
# greyed_features: cloudflared + traefik features.
features = {f['feature'] for f in data['greyed_features']}
assert 'cloudflared' in features, features
assert 'traefik' in features, features
# tailscale is ok → NOT greyed.
assert 'tailscale' not in features, features
# Alternative surfaces (R220 supplies it).
cf_feature = next(f for f in data['greyed_features'] if f['feature'] == 'cloudflared')
assert 'tailscale-funnel' in (cf_feature.get('alternative') or ''), cf_feature
" \
  && ok "synthesis: docker+cloudflared down → install_paths+traefik greyed; tailscale stays ok" \
  || ko "synthesis logic wrong"

# ---- in-process: ALL components ok → no grey-out ----
python3 -c "
import importlib.util, json as j
spec = importlib.util.spec_from_file_location('serve','${SERVE}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class FakeResult:
    def __init__(self, stdout, returncode=0, stderr=''):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr

synth = {
    'components': [
        {'component':'internet','status':'ok'},
        {'component':'dns','status':'ok'},
        {'component':'docker','status':'ok'},
        {'component':'cloudflared','status':'ok'},
        {'component':'tailscale','status':'ok'},
        {'component':'traefik','status':'ok'},
    ]
}
m.subprocess.run = lambda *a, **kw: FakeResult(j.dumps(synth))

card = m.card_dependency_state()
data = card['data']
assert data['down_components'] == [], data
assert data['greyed_card_ids'] == [], data
assert data['greyed_features'] == [], data
assert data['needs_attention'] is False, data
" \
  && ok "all-ok: no grey-outs (down_components/greyed_card_ids/greyed_features all empty)" \
  || ko "all-ok path wrong"

# ---- in-process: internet down → toolchains/models/fine_tune all greyed ----
python3 -c "
import importlib.util, json as j
spec = importlib.util.spec_from_file_location('serve','${SERVE}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class FakeResult:
    def __init__(self, stdout, returncode=0, stderr=''):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr

synth = {
    'components': [
        {'component':'internet','status':'down',
         'detail':'no egress','alternative':'tailscale exit-node'},
        {'component':'docker','status':'ok'},
    ]
}
m.subprocess.run = lambda *a, **kw: FakeResult(j.dumps(synth))

card = m.card_dependency_state()
data = card['data']
greyed_ids = set(data['greyed_card_ids'])
# Every card that depends on internet should be greyed.
for needed in ('models','toolchains','fine_tune','install_paths'):
    assert needed in greyed_ids, (needed, greyed_ids)
# Plenty of features greyed.
assert len(data['greyed_features']) >= 8, data
" \
  && ok "internet-down: models+toolchains+fine_tune+install_paths greyed; ≥8 features greyed" \
  || ko "internet-down cascade wrong"

# ---- robustness: network-status missing → empty card, no crash ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('serve','${SERVE}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Force bin_path miss by pointing REPO_ROOT at a directory without the script.
m.REPO_ROOT = m.Path('/tmp')
card = m.card_dependency_state()
data = card['data']
assert data['down_components'] == []
assert 'unavailable' in data['summary']
" \
  && ok "robustness: missing network-status → empty card with unavailable summary" \
  || ko "robustness path wrong"

echo
total=$((pass + fail))
echo "test_dependency_state_card: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
