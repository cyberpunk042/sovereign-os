#!/usr/bin/env bash
# tests/nspawn/test_dashboard_grid.sh — R248 (SDD-026 Z-1 terminal view).
# 1-line-per-card terminal rollup of every dashboard card.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/dashboard/grid.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_dashboard_grid.sh"
echo

[ -x "${SCRIPT}" ] && ok "grid.py executable" \
  || { ko "missing grid.py"; exit 1; }
grep -q "R248" "${SCRIPT}" && ok "grid.py cites R248" || ko "R248 missing"
grep -q "dashboard grid" "${OSCTL}" \
  && ok "osctl help documents 'dashboard grid'" || ko "osctl help missing"
grep -q "      grid)" "${OSCTL}" \
  && ok "osctl dispatches 'grid'" || ko "osctl dispatch missing"

TMP="$(mktemp -d -t r248.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

# ---- JSON shape: 15 cards from CARDS list ----
set +e
out="$(python3 "${SCRIPT}" --json 2>/dev/null)"
rc=$?
set -e
# rc ∈ {0,1} depending on whether any card needs attention on this host.
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "grid --json rc ∈ {0,1} (got ${rc})"
else
  ko "unexpected rc=${rc}"
fi
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R248', d
assert d['card_count']==18, d  # 13 + R247 (fine_tune+events) + R254 (power+bios) + R261 (virt)
# Every card has required summary shape.
for c in d['cards']:
    for f in ('id','title','summary','needs_attention'):
        assert f in c, f'card {c.get(\"id\")} missing {f}'
    assert isinstance(c['needs_attention'], bool)
" \
  && ok "grid --json: 15 cards with id/title/summary/needs_attention" \
  || ko "grid shape wrong"

# ---- needs_attention_count matches glyph count ----
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
nc=sum(1 for c in d['cards'] if c['needs_attention'])
assert nc==d['needs_attention_count'], (nc, d['needs_attention_count'])
" \
  && ok "needs_attention_count matches per-card sum" \
  || ko "count mismatch"

# ---- human render carries banner + headers + every card id ----
out_h="$(python3 "${SCRIPT}" 2>&1 || true)"
echo "${out_h}" | grep -q "R248 sovereign-os status grid" \
  && ok "human render carries R248 banner" || ko "banner missing"
echo "${out_h}" | grep -q "GLYPH" \
  && ok "human render has GLYPH column header" || ko "header missing"
# Spot-check a few card ids surface.
for cid in gpu network cpu health insights services kernel toolchains fine_tune events; do
  echo "${out_h}" | grep -qE "  ${cid}[[:space:]]" \
    && ok "grid lists card ${cid}" || ko "card ${cid} missing"
done

# ---- osctl bridge ----
set +e
"${OSCTL}" dashboard grid --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl dashboard grid rc ∈ {0,1} (got ${rc})"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R248', d
" \
  && ok "osctl bridge surfaces R248 JSON" \
  || ko "osctl JSON wrong"

echo
total=$((pass + fail))
echo "test_dashboard_grid: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
