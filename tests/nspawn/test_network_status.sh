#!/usr/bin/env bash
# tests/nspawn/test_network_status.sh — R220 (SDD-026 Z-7) network
# state surface. CI runners typically have internet + DNS but lack
# cloudflared/tailscale/traefik/docker; the test pins the operator-
# readable shape across the present/absent matrix.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/network-status.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_network_status.sh"
echo

[ -x "${SCRIPT}" ] && ok "network-status.py executable" \
  || { ko "missing network-status.py"; exit 1; }
grep -q "network)" "${OSCTL}" \
  && ok "osctl bridges 'network'" || ko "osctl bridge missing"
grep -q "R220" "${OSCTL}" \
  && ok "osctl cites R220" || ko "R220 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ---- All-component banner ----
set +e
python3 "${SCRIPT}" > "${WORK}/all.txt" 2>&1
rc=$?
set -e
# rc may be 0 or 1 depending on which services CI happens to have.
# The structural assertions are what's pinned.
grep -q "R220 sovereign-os network status" "${WORK}/all.txt" \
  && ok "R220 banner emitted" || ko "no banner"

for component in internet dns cloudflared tailscale traefik docker; do
  # Card line shape: `  <glyph> <component>     [<status>] ...`
  # Match operator-meaningfully on the column name + status bracket,
  # bypassing locale/regex quirks around the unicode status glyph.
  grep -qE "^ +[^ ]+ ${component} +\[" "${WORK}/all.txt" \
    && ok "card present: ${component}" \
    || ko "missing card: ${component}"
done

# ---- --component filter ----
set +e
python3 "${SCRIPT}" --component internet > "${WORK}/internet.txt" 2>&1
set -e
grep -qE "^ +[^ ]+ internet +\[" "${WORK}/internet.txt" \
  && ok "single-component filter renders internet card" \
  || ko "filtered card wrong"
! grep -qE "^ +[^ ]+ docker +\[" "${WORK}/internet.txt" \
  && ok "single-component filter excludes others" \
  || ko "single-component filter leaked"

# ---- --json shape ----
set +e
python3 "${SCRIPT}" --json > "${WORK}/all.json" 2>&1
set -e
python3 - "${WORK}/all.json" <<'PY' 2>/dev/null \
  && ok "JSON shape: components array of 6 cards, each with status + detail" \
  || ko "JSON shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
comps = d["components"]
assert len(comps) == 6, comps
names = {c["component"] for c in comps}
assert names == {"internet", "dns", "cloudflared", "tailscale", "traefik", "docker"}, names
for c in comps:
    assert c["status"] in {"ok", "warn", "down", "not-installed"}, c
    assert isinstance(c["detail"], str) and c["detail"], c
PY

# ---- Specific components: cloudflared/tailscale/traefik are NOT
#      installed on CI → status `not-installed` + alternative text ----
set +e
python3 "${SCRIPT}" --component cloudflared > "${WORK}/cf.txt" 2>&1
set -e
grep -q "not-installed" "${WORK}/cf.txt" \
  && ok "cloudflared absent on CI → not-installed" \
  || ko "cloudflared wrong status on CI"
grep -q "tailscale" "${WORK}/cf.txt" \
  && ok "cloudflared 'not-installed' suggests tailscale alternative" \
  || ko "alternative not surfaced"

set +e
python3 "${SCRIPT}" --component tailscale > "${WORK}/ts.txt" 2>&1
set -e
grep -q "not-installed" "${WORK}/ts.txt" \
  && ok "tailscale absent on CI → not-installed" \
  || ko "tailscale wrong status on CI"
grep -q "alternative:" "${WORK}/ts.txt" \
  && ok "tailscale not-installed surfaces alternative" \
  || ko "tailscale alternative missing"

# ---- osctl bridge ----
set +e
"${OSCTL}" network status --component internet > "${WORK}/osctl.txt" 2>&1
set -e
grep -q "R220" "${WORK}/osctl.txt" \
  && ok "osctl bridge surfaces R220 banner" \
  || ko "osctl bridge wrong"

# ---- Unknown subverb → rc=2 ----
set +e
"${OSCTL}" network unknown > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown network subverb → rc=2" \
  || ko "expected rc=2 on unknown subverb, got ${rc}"

echo
total=$((pass + fail))
echo "test_network_status: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
