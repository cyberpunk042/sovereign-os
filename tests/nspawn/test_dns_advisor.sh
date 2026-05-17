#!/usr/bin/env bash
# tests/nspawn/test_dns_advisor.sh — R268 (E3.M4).
# DNS provider classification + posture verdict.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/network/dns-advisor.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_dns_advisor.sh"
echo

[ -x "${SCRIPT}" ] && ok "dns-advisor.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R268\|E3.M4" "${SCRIPT}" && ok "script cites R268/E3.M4" \
  || ko "R268 missing"
grep -q "^  dns-advisor)" "${OSCTL}" \
  && ok "osctl bridges 'dns-advisor'" || ko "osctl dispatch missing"
grep -q "dns-advisor status" "${OSCTL}" \
  && ok "osctl help documents 'dns-advisor'" || ko "osctl help missing"

# ---- status --json: shape + posture enum ----
set +e
out="$(python3 "${SCRIPT}" status --json 2>/dev/null)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "status --json rc ∈ {0,1} (got ${rc})"
else
  ko "rc unexpected ${rc}"
fi
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R268', d
assert d['vector'].startswith('E3.M4'), d
for f in ('resolv_conf_nameservers', 'classified_upstreams',
          'resolved_conf', 'posture', 'advisories'):
    assert f in d, f'missing {f}'
assert d['posture'] in ('ok','attention','degraded','not-configured'), d
" \
  && ok "status --json: required fields + posture enum constrained" \
  || ko "status shape wrong"

# ---- providers --json: 12+ known providers ----
out="$(python3 "${SCRIPT}" providers --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R268', d
# 12+ entries seeded.
assert d['count'] >= 12, d
addrs = {p['address'] for p in d['providers']}
# Operator-relevant providers must be present.
for needed in ('1.1.1.1','9.9.9.9','8.8.8.8','94.140.14.14','1.1.1.2'):
    assert needed in addrs, f'missing {needed}: {sorted(addrs)}'
# Quad9 + Cloudflare-malware MUST carry malware_filtering=True.
by_addr = {p['address']: p for p in d['providers']}
assert by_addr['9.9.9.9']['malware_filtering'] is True, by_addr['9.9.9.9']
assert by_addr['1.1.1.2']['malware_filtering'] is True, by_addr['1.1.1.2']
" \
  && ok "providers --json: 12+ entries incl. Cloudflare/Quad9/Google/AdGuard" \
  || ko "providers shape wrong"

# ---- latency --json: shape stable regardless of `dig` presence ----
out="$(python3 "${SCRIPT}" latency --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R268', d
assert 'dig_available' in d and 'measurements' in d, d
assert isinstance(d['measurements'], list), d
" \
  && ok "latency --json: stable shape with/without dig" \
  || ko "latency shape wrong"

# ---- classify() heuristics ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('dns','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Known provider
c = m.classify('1.1.1.1')
assert c['name'] == 'Cloudflare', c
# RFC1918 → lan-private
c = m.classify('192.168.1.1')
assert c['name'] == 'lan-private', c
# 127.0.0.0/8 not in table → local-resolver
c = m.classify('127.0.1.1')
assert c['name'] == 'local-resolver', c
# Unknown public → unknown
c = m.classify('203.0.113.42')
assert c['name'] == 'unknown', c
" \
  && ok "classify(): cloudflare + lan-private + local-resolver + unknown" \
  || ko "classify heuristics wrong"

# ---- advisory: when only ISP/unknown upstream, surface 'no malware filtering' ----
# We can't easily mock /etc/resolv.conf here. Smoke that the live
# advisory path on this CI host emits at least the expected
# 'malware filtering' hint when no provider in the chain offers it.
out="$(python3 "${SCRIPT}" status --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
# When live nameservers include no malware-filtering provider,
# advisory mentions Quad9 / Cloudflare-malware.
if not any(c.get('malware_filtering') for c in d['classified_upstreams']):
    assert any('Quad9' in a or 'malware' in a.lower() for a in d['advisories']), d
" \
  && ok "advisory: missing malware filtering → suggest Quad9/Cloudflare-malware" \
  || ko "malware-filter advisory wrong"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r268.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" dns-advisor providers --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl dns-advisor providers rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R268', d
" \
  && ok "osctl bridge surfaces R268 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" dns-advisor nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown dns-advisor subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_dns_advisor: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
