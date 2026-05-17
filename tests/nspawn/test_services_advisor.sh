#!/usr/bin/env bash
# tests/nspawn/test_services_advisor.sh — R263 (SDD-026 Z-7 expansion).
# Cloudflared / Tailscale / Traefik posture advisor.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/network/services-advisor.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_services_advisor.sh"
echo

[ -x "${SCRIPT}" ] && ok "services-advisor.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R263" "${SCRIPT}" && ok "script cites R263" || ko "R263 missing"
grep -q "^  services-advisor)" "${OSCTL}" \
  && ok "osctl bridges 'services-advisor'" || ko "osctl dispatch missing"
grep -q "services-advisor cloudflared" "${OSCTL}" \
  && ok "osctl help documents 'services-advisor'" || ko "osctl help missing"

# ---- show --json: aggregates 3 services ----
set +e
out="$(python3 "${SCRIPT}" show --json 2>/dev/null)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "show --json rc ∈ {0,1} (got ${rc})"
else
  ko "unexpected rc=${rc}"
fi
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R263', d
assert d['vector'].startswith('SDD-026 Z-7'), d
assert 'results' in d and 'summary' in d, d
for svc in ('cloudflared','tailscale','traefik'):
    assert svc in d['results'], d
    assert 'posture' in d['results'][svc]
    assert d['results'][svc]['posture'] in (
        'ok','attention','degraded','not-installed'), d['results'][svc]
" \
  && ok "show --json: 3 services with constrained posture enum" \
  || ko "show shape wrong"

# ---- per-service: each verb works ----
for svc in cloudflared tailscale traefik; do
  set +e
  out="$(python3 "${SCRIPT}" "${svc}" --json 2>/dev/null)"
  rc=$?
  set -e
  if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
    ok "${svc} --json rc ∈ {0,1}"
  else
    ko "${svc} rc unexpected ${rc}"
  fi
  echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R263', d
assert d['service'] == '${svc}', d
for f in ('installed','posture','advisory'):
    assert f in d, f'{f} missing'
" \
    && ok "${svc}: required fields present" \
    || ko "${svc} shape wrong"
done

# ---- not-installed posture carries actionable advisory on CI ----
out="$(python3 "${SCRIPT}" cloudflared --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
# On CI cloudflared is typically absent.
if d['posture'] == 'not-installed':
    assert d['advisory'] is not None, d
    assert 'cloudflared' in d['advisory'].lower(), d
" \
  && ok "not-installed posture carries operator-pull install hint" \
  || ko "not-installed advisory missing"

# ---- human render: banner + glyph ----
out_h="$(python3 "${SCRIPT}" show 2>&1 || true)"
echo "${out_h}" | grep -q "R263 sovereign-os services-advisor show" \
  && ok "human banner present" || ko "banner missing"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r263.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" services-advisor tailscale --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl services-advisor tailscale rc ∈ {0,1}"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R263', d
" \
  && ok "osctl bridge surfaces R263 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" services-advisor nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_services_advisor: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
