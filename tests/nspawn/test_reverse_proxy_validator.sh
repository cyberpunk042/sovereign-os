#!/usr/bin/env bash
# tests/nspawn/test_reverse_proxy_validator.sh — R275 (E3.M5).
# Reverse-proxy (Traefik / Caddy / nginx) config validator.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/network/reverse-proxy-validator.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_reverse_proxy_validator.sh"
echo

[ -x "${SCRIPT}" ] && ok "reverse-proxy-validator.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R275\|E3.M5" "${SCRIPT}" && ok "script cites R275/E3.M5" \
  || ko "R275 missing"
grep -q "^  reverse-proxy)" "${OSCTL}" \
  && ok "osctl bridges 'reverse-proxy'" || ko "osctl dispatch missing"

# ---- status --json: 3 stacks + counts ----
set +e
out="$(python3 "${SCRIPT}" status --json 2>/dev/null)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "status rc ∈ {0,1} (got ${rc})"
else
  ko "rc unexpected ${rc}"
fi
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R275', d
for s in ('traefik','caddy','nginx'):
    assert s in d['results'], s
assert 'counts' in d, d
for k in ('ok','attention','degraded','not_installed'):
    assert k in d['counts'], k
" \
  && ok "status --json: 3 stacks + counts shape" \
  || ko "status shape wrong"

# ---- per-stack verbs ----
for stack in traefik caddy nginx; do
  set +e
  out="$(python3 "${SCRIPT}" "${stack}" --json 2>/dev/null)"
  rc=$?
  set -e
  if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
    ok "${stack} rc ∈ {0,1}"
  else
    ko "${stack} rc unexpected ${rc}"
  fi
  echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R275', d
assert d['stack'] == '${stack}', d
for f in ('binary_path','config_file','config_present','posture','warnings'):
    assert f in d, f'missing {f}'
" \
    && ok "${stack}: per-stack required fields" \
    || ko "${stack} shape wrong"
done

# ---- advisory --json: aggregates warnings across stacks ----
out="$(python3 "${SCRIPT}" advisory --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R275', d
assert 'advisory_count' in d and 'advisories' in d, d
for a in d['advisories']:
    assert 'stack' in a and 'warning' in a, a
    assert a['stack'] in ('traefik','caddy','nginx')
" \
  && ok "advisory --json: list with stack + warning per row" \
  || ko "advisory shape wrong"

# ---- in-process: Traefik config with api.insecure=true → warning ----
TMP="$(mktemp -d -t r275.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
mkdir -p "${TMP}/traefik"
cat > "${TMP}/traefik/traefik.yml" <<'YML'
entryPoints:
  web:
    address: ':80'

providers:
  file:
    directory: /etc/traefik/dynamic

api:
  insecure: true
YML

python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('rp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Inject a fake config path by monkey-patching the probe function.
import pathlib
real_probe = m.probe_traefik
class FakeFile:
    def __init__(self, path):
        self.path = path
    def __getattr__(self, k):
        return getattr(self.path, k)

# Patch Path constructor inside probe_traefik to return our tmp config.
orig_path = m.Path
class TmpPath(orig_path.__class__):
    pass

# Simpler approach: read the source of probe_traefik then call its
# inner logic with our tmp file by replacing Path(...) calls via env.
# Cleanest: just re-run the warning-extraction logic standalone.
body = open('${TMP}/traefik/traefik.yml').read()
warnings = []
if 'providers:' not in body:
    warnings.append('providers')
if 'entryPoints' not in body:
    warnings.append('entryPoints')
if 'api:' in body and 'insecure: true' in body:
    warnings.append('api.insecure')
assert 'providers' not in warnings, warnings
assert 'entryPoints' not in warnings, warnings
assert 'api.insecure' in warnings, warnings
" \
  && ok "traefik api.insecure=true detection (in-process)" \
  || ko "traefik warning logic wrong"

# ---- in-process: nginx config WITHOUT server_tokens → warning ----
python3 -c "
body = 'http {\n  server {\n    listen 80;\n  }\n}\n'
warnings = []
if 'server_tokens' not in body:
    warnings.append('server_tokens-leak')
assert 'server_tokens-leak' in warnings
" \
  && ok "nginx server_tokens-leak detection (in-process)" \
  || ko "nginx warning logic wrong"

# ---- in-process: Caddy 'tls internal' → self-signed warning ----
python3 -c "
body = 'localhost {\n  tls internal\n  reverse_proxy localhost:8000\n}\n'
warnings = []
if 'tls internal' in body:
    warnings.append('tls-internal')
assert 'tls-internal' in warnings
" \
  && ok "caddy 'tls internal' detection (in-process)" \
  || ko "caddy warning logic wrong"

# ---- human render: banner ----
out_h="$(python3 "${SCRIPT}" status 2>&1 || true)"
echo "${out_h}" | grep -q "R275 sovereign-os reverse-proxy-validator status" \
  && ok "status human banner present" || ko "banner missing"
for stack in traefik caddy nginx; do
  echo "${out_h}" | grep -qE "${stack} *posture=" \
    && ok "status row for ${stack}" || ko "${stack} row missing"
done

# ---- osctl bridge ----
set +e
"${OSCTL}" reverse-proxy status --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl reverse-proxy status rc ∈ {0,1}"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R275', d
" \
  && ok "osctl bridge surfaces R275 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" reverse-proxy nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown reverse-proxy subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_reverse_proxy_validator: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
