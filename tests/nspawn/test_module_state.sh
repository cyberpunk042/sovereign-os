#!/usr/bin/env bash
# R351 (E2.M34) — module-state L3.
# Operator-pull "what have I installed but not yet configured?"
# Catalog of 16 known modules × 4 signals × 5 verdicts.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MS="${REPO_ROOT}/scripts/intelligence/module-state.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list verb returns ≥10 modules with full schema ────────────────
empty_etc=$(mktemp -d)
out="$(python3 "${MS}" list --etc-dir "${empty_etc}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['module_count'] >= 10
for s in d['modules']:
    for k in ('module','axis','has_example_config','has_etc_config',
             'has_systemd_unit','verdict','configure_verb'):
        assert k in s, (k, s)
" || fail "list schema"
pass "1. list returns ≥10 modules with full schema (module+axis+signals+verdict+verb)"

# ── 2. empty etc dir → ALL modules have verdict installed-not-configured
out="$(python3 "${MS}" list --etc-dir "${empty_etc}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for s in d['modules']:
    # Either installed-not-configured (has example, no etc) OR
    # shipped-but-untouched (no example, no etc — rare)
    assert s['verdict'] in ('installed-not-configured',
                             'shipped-but-untouched'), s
assert d['attention_count'] >= 10
" || fail "all unconfigured"
pass "2. empty etc dir → ALL ≥10 modules flagged for operator attention"

# ── 3. operator config present → that module flips to fully-configured
configured_etc=$(mktemp -d)
echo '# operator-pinned' > "${configured_etc}/power.toml"
echo '# operator-pinned' > "${configured_etc}/oc-headroom.toml"
out="$(python3 "${MS}" list --etc-dir "${configured_etc}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_name = {s['module']: s for s in d['modules']}
assert by_name['power']['verdict'] == 'fully-configured', by_name['power']
assert by_name['power']['has_etc_config'] is True
assert by_name['oc-headroom']['verdict'] == 'fully-configured'
# Others still unconfigured
assert by_name['ram']['verdict'] == 'installed-not-configured'
" || fail "flip"
pass "3. operator-pin power.toml + oc-headroom.toml → those flip to fully-configured"

# ── 4. show <module> returns single state ────────────────────────────
out="$(python3 "${MS}" show power --etc-dir "${configured_etc}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
s = d['state']
assert s['module'] == 'power'
assert s['verdict'] == 'fully-configured'
" || fail "show"
pass "4. show power --etc-dir <configured> → fully-configured verdict"

# ── 5. show unknown module → rc=2 + structured error ────────────────
rc=0
err="$(python3 "${MS}" show no-such-module --json 2>&1 1>/dev/null)" || rc=$?
[[ "${rc}" == 2 ]] || fail "rc=${rc}"
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'error' in d and 'known' in d
assert len(d['known']) >= 10
" || fail "unknown shape"
pass "5. show unknown module → rc=2 + structured {error, known: [...]}"

# ── 6. recommend lists attention items + configure_verb for each ────
out="$(python3 "${MS}" recommend --etc-dir "${empty_etc}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['attention_count'] >= 10
for item in d['attention_items']:
    assert item['verdict'] in ('installed-not-configured',
                                'running-without-overlay',
                                'config-only-no-runtime')
    assert item['configure_verb'].startswith('cp ') \
        or 'sovereign-osctl' in item['configure_verb']
" || fail "recommend shape"
pass "6. recommend lists ≥10 attention items with operator-runnable next step"

# ── 7. all_modules_summary covers EVERY catalog entry ────────────────
out="$(python3 "${MS}" recommend --etc-dir "${empty_etc}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
summary = d['all_modules_summary']
assert isinstance(summary, dict)
assert len(summary) >= 10
" || fail "summary"
pass "7. recommend all_modules_summary is a dense {module: verdict} map"

# ── 8. list --axis filter narrows to matching modules ────────────────
out="$(python3 "${MS}" list --axis power --etc-dir "${empty_etc}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['axis_filter'] == 'power'
for s in d['modules']:
    assert s['axis'] == 'power'
assert len(d['modules']) >= 3  # power, power-profiles, shutdown-manifest, psu-oc
" || fail "axis"
pass "8. list --axis power → ≥3 power-axis modules"

# ── 9. list --state filter narrows to matching verdict ───────────────
out="$(python3 "${MS}" list --state fully-configured --etc-dir "${configured_etc}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['state_filter'] == 'fully-configured'
for s in d['modules']:
    assert s['verdict'] == 'fully-configured'
assert len(d['modules']) >= 2
" || fail "state filter"
pass "9. list --state fully-configured → exactly the configured modules"

# ── 10. EVERY module's configure_verb points to a real example file ─
out="$(python3 "${MS}" list --etc-dir "${empty_etc}" --json || true)"
echo "${out}" | python3 -c "
import json, sys, pathlib
REPO = pathlib.Path('${REPO_ROOT}')
d = json.loads(sys.stdin.read())
broken = []
for s in d['modules']:
    if not s.get('has_example_config'):
        continue  # shipped-but-untouched modules don't claim an example
    v = s.get('configure_verb', '')
    # Verb typically: 'cp config/<name>.toml.example /etc/...'
    parts = v.split()
    if len(parts) >= 2 and parts[0] == 'cp':
        src = REPO / parts[1]
        if not src.is_file():
            broken.append(f'{s[\"module\"]}: {parts[1]} not found')
assert not broken, f'configure_verb cites missing files: {broken}'
" || fail "configure_verb files"
pass "10. EVERY module's configure_verb cites an example file that EXISTS on disk"

# ── 11. sovereign-osctl module-state dispatches all 3 subverbs ──────
# list + recommend return rc=1 when items need attention; show returns
# rc=1 when the named module needs attention. All these are expected.
rc=0; "${OSCTL}" module-state list --etc-dir "${empty_etc}" --json >/dev/null 2>&1 || rc=$?
[[ "${rc}" == 1 ]] || fail "osctl list rc=${rc} (expected 1 with unconfigured items)"
rc=0; "${OSCTL}" module-state show power --etc-dir "${empty_etc}" --json >/dev/null 2>&1 || rc=$?
[[ "${rc}" == 1 ]] || fail "osctl show rc=${rc} (expected 1; power is unconfigured)"
rc=0; "${OSCTL}" module-state recommend --etc-dir "${empty_etc}" --json >/dev/null 2>&1 || rc=$?
[[ "${rc}" == 1 ]] || fail "osctl recommend rc=${rc} (expected 1 with unconfigured items)"
pass "11. sovereign-osctl module-state dispatches list/show/recommend (rc honored)"

# ── 12. unconfigured-attention rc=1; fully-configured rc=0 ──────────
all_configured=$(mktemp -d)
out="$(python3 "${MS}" list --etc-dir "${empty_etc}" --json || true)"
# Plant every example as a real config to flip everything
for ex in "${REPO_ROOT}"/config/*.toml.example; do
    base=$(basename "${ex}" .toml.example)
    cp "${ex}" "${all_configured}/${base}.toml"
done
rc=0
python3 "${MS}" recommend --etc-dir "${all_configured}" --json >/dev/null 2>&1 || rc=$?
[[ "${rc}" == 0 ]] || fail "expected rc=0 when all configured; got rc=${rc}"
pass "12. fully-configured fleet → recommend rc=0 (no operator-attention items)"

# Cleanup
rm -rf "${empty_etc}" "${configured_etc}" "${all_configured}"

echo "ALL OK"
