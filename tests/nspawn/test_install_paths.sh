#!/usr/bin/env bash
# tests/nspawn/test_install_paths.sh — R237 (SDD-026 Z-8). Per-feature
# install-layer matrix with live network-status cross-reference + grey-out.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/install/paths.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
EXAMPLE="${__REPO_ROOT}/config/install-layers.toml.example"

echo "tests/nspawn/test_install_paths.sh"
echo

[ -x "${SCRIPT}" ] && ok "paths.py executable" \
  || { ko "missing paths.py"; exit 1; }
[ -f "${EXAMPLE}" ] && ok "config/install-layers.toml.example shipped" \
  || ko "example config missing"
grep -q "R237" "${SCRIPT}" && ok "paths.py cites R237" || ko "R237 missing"
grep -q "^  install-paths)" "${OSCTL}" \
  && ok "osctl bridges 'install-paths'" || ko "osctl dispatch missing"
grep -q "install-paths show" "${OSCTL}" \
  && ok "osctl help documents install-paths" || ko "osctl help missing"

TMP="$(mktemp -d -t r237.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

# ---- isolated config: 3 features with contrasting layer setups ----
cat > "${TMP}/cfg.toml" <<'TOML'
[features.alpha]
summary = "alpha — system only"
layers = ["system"]
default = "system"
[features.alpha.layers_meta.system]
requires = []
warns    = []

[features.beta]
summary = "beta — container preferred, system fallback"
layers  = ["container", "system"]
default = "container"
[features.beta.layers_meta.container]
requires = ["docker"]
warns    = []
[features.beta.layers_meta.system]
requires = []
warns    = ["systemd unit only"]

[features.gamma]
summary = "gamma — container only, blocked if docker missing"
layers  = ["container"]
default = "container"
[features.gamma.layers_meta.container]
requires = ["docker"]
warns    = []
TOML
export SOVEREIGN_OS_INSTALL_LAYERS="${TMP}/cfg.toml"

# ---- show --json: per-feature verdicts using live network-status ----
set +e
out="$(python3 "${SCRIPT}" show --json 2>/dev/null)"
rc=$?
set -e
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R237', d
feats={f['feature']: f for f in d['features']}
assert set(feats.keys())=={'alpha','beta','gamma'}, feats.keys()
# alpha has no deps → always installable
assert feats['alpha']['verdict']=='installable', feats['alpha']
# beta: container needs docker; if docker down → verdict='alternative' (system)
# gamma: container-only; if docker down → verdict='blocked'
assert feats['beta']['verdict'] in ('installable','alternative'), feats['beta']
assert feats['gamma']['verdict'] in ('installable','blocked'), feats['gamma']
# Counts present + accurate
c=d['counts']
assert c['total']==3, c
assert c['installable']+c['alternative']+c['blocked']==3, c
" \
  && ok "show --json: 3 features classified into installable/alternative/blocked" \
  || ko "show shape wrong: ${out:0:300}"

# ---- show --feature filters to one ----
set +e
out="$(python3 "${SCRIPT}" show --feature alpha --json 2>/dev/null)"
set -e
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert len(d['features'])==1, d
assert d['features'][0]['feature']=='alpha', d
" \
  && ok "show --feature alpha filters to one row" \
  || ko "feature filter wrong"

# ---- show --feature with unknown name → rc=2 ----
set +e
out_bad="$(python3 "${SCRIPT}" show --feature never-existed 2>&1)"
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "unknown --feature → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- choose: alpha/system always available ----
set +e
out="$(python3 "${SCRIPT}" choose alpha --layer system --json 2>/dev/null)"
rc_ch=$?
set -e
[ "${rc_ch}" -eq 0 ] && ok "choose alpha --layer system rc=0" \
  || ko "choose alpha rc=${rc_ch}"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['available'] is True, d
" \
  && ok "choose JSON: available=True for alpha system" \
  || ko "choose JSON wrong"

# ---- choose: unknown feature → rc=2 ----
set +e
python3 "${SCRIPT}" choose never --layer system > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "choose unknown feature → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- choose: unknown layer for known feature → rc=2 ----
set +e
python3 "${SCRIPT}" choose alpha --layer container > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "choose unknown layer for feature → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- grey-out --json: lists only blocked features ----
set +e
out="$(python3 "${SCRIPT}" grey-out --json 2>/dev/null)"
rc=$?
set -e
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R237', d
# All entries must be verdict=blocked.
for r in d['blocked']:
    assert r['verdict']=='blocked', r
assert d['blocked_count']==len(d['blocked']), d
" \
  && ok "grey-out lists only blocked features" \
  || ko "grey-out shape wrong"

# ---- human render: banner + glyphs ----
set +e
out="$(python3 "${SCRIPT}" show 2>/dev/null)"
set -e
echo "${out}" | grep -q "R237 sovereign-os install-paths show" \
  && ok "human render carries R237 banner" || ko "banner missing"
echo "${out}" | grep -qE "installable=|alternative=|blocked=" \
  && ok "human render shows totals line" || ko "totals missing"

# ---- osctl bridge ----
set +e
"${OSCTL}" install-paths show --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl install-paths show rc ∈ {0,1} (got ${rc})"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R237', d
" \
  && ok "osctl bridge surfaces R237 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" install-paths nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown install-paths subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_install_paths: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
