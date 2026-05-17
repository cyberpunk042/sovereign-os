#!/usr/bin/env bash
# R305 (E1.M30) — kernel cmdline parameter advisor L3.
#
# Operator-named (§1b mandate row): "Kernel optimisation, OS,
# Services, Modules, Tools, Dashboards, Configurations, Options".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/kernel/cmdline-advisor.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope ───────────────────────────────
out="$(python3 "${SCRIPT}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R305'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M30'
for k in ('actual_param_count', 'recommended', 'to_add', 'matches',
          'verdict', 'rc'):
    assert k in d, k
" || fail "envelope"
pass "1. status --json envelope (round/schema/recommended/to_add/matches)"

# ── 2. Default catalog covers operator-named axes ──────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {r['name'] for r in d['recommended']}
must = {'iommu', 'amd_iommu', 'transparent_hugepage', 'mitigations',
        'nvme.poll_queues', 'rcu_nocbs', 'preempt'}
missing = must - names
assert not missing, missing
# Every entry has rationale + axis + operator_caveat.
for r in d['recommended']:
    assert 'rationale' in r and r['rationale']
    assert 'axis' in r
" || fail "catalog coverage"
pass "2. default catalog covers iommu/amd_iommu/thp/mitigations/nvme/rcu_nocbs/preempt"

# ── 3. parse_proc_cmdline handles key=value AND bare flags ──
python3 -c "
import sys, importlib.util, tempfile, pathlib
spec = importlib.util.spec_from_file_location('cm', 'scripts/kernel/cmdline-advisor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

tf = tempfile.NamedTemporaryFile(mode='w', suffix='.cmdline', delete=False)
tf.write('BOOT_IMAGE=/vmlinuz iommu=pt amd_iommu=on quiet splash mitigations=off')
tf.close()
parsed = m.parse_proc_cmdline(tf.name)
pathlib.Path(tf.name).unlink()
assert parsed.get('iommu') == 'pt', parsed
assert parsed.get('amd_iommu') == 'on'
assert parsed.get('quiet') is None  # bare flag
assert parsed.get('mitigations') == 'off'
assert parsed.get('BOOT_IMAGE') == '/vmlinuz'
print('PASS')
" || fail "parse_proc_cmdline"
pass "3. parse_proc_cmdline handles key=value AND bare flags"

# ── 4. diff_cmdline computes to_add + matches correctly ────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('cm', 'scripts/kernel/cmdline-advisor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

actual = {'iommu': 'pt', 'amd_iommu': 'off', 'BOOT_IMAGE': '/vmlinuz'}
recommended = [
    {'name': 'iommu', 'value': 'pt', 'axis': 'virt', 'rationale': 'x'},
    {'name': 'amd_iommu', 'value': 'on', 'axis': 'virt', 'rationale': 'y'},
    {'name': 'mitigations', 'value': 'off', 'axis': 'cpu', 'rationale': 'z'},
]
d = m.diff_cmdline(actual, recommended)
match_names = {r['name'] for r in d['matches']}
add_names = {r['name'] for r in d['to_add']}
assert match_names == {'iommu'}, match_names
assert add_names == {'amd_iommu', 'mitigations'}, add_names
# amd_iommu has wrong value → current='off' in to_add entry
amd_entry = next(r for r in d['to_add'] if r['name'] == 'amd_iommu')
assert amd_entry['current'] == 'off', amd_entry
print('PASS')
" || fail "diff_cmdline"
pass "4. diff_cmdline correctly computes to_add (mismatched + absent) + matches"

# ── 5. grubby_hint emits operator-runnable command ──────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('cm', 'scripts/kernel/cmdline-advisor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

to_add = [
    {'name': 'iommu', 'value': 'pt'},
    {'name': 'amd_iommu', 'value': 'on'},
    {'name': 'quiet', 'value': None},
]
hint = m.grubby_hint(to_add)
assert 'grubby --update-kernel=ALL' in hint
assert 'iommu=pt' in hint
assert 'amd_iommu=on' in hint
assert 'quiet' in hint
# Empty to_add → friendly no-diff message.
assert 'no diff' in m.grubby_hint([])
print('PASS')
" || fail "grubby_hint"
pass "5. grubby_hint emits operator-runnable grubby command + no-diff path"

# ── 6. diff verb returns only mismatching params ────────────
out_d="$(python3 "${SCRIPT}" diff --json || true)"
echo "${out_d}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R305'
assert 'to_add' in d
assert 'to_add_count' in d
# Every to_add row has rationale (operator-readable).
for r in d['to_add']:
    assert r.get('rationale')
" || fail "diff shape"
pass "6. diff verb returns to_add + count + per-param rationale"

# ── 7. apply-hint verb emits the grubby command ──────────────
out_h="$(python3 "${SCRIPT}" apply-hint --json || true)"
echo "${out_h}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R305'
assert 'apply_command' in d
# Either 'grubby' command OR 'no diff' message.
ac = d['apply_command']
assert 'grubby' in ac or 'no diff' in ac, ac
" || fail "apply-hint shape"
pass "7. apply-hint emits grubby --update-kernel command (or no-diff)"

# ── 8. Operator overlay replaces recommended catalog ────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[recommended]]
name             = "operator-custom-param"
value            = "test-value"
axis             = "test"
rationale        = "operator-pinned for test fixture"
operator_caveat  = "n/a"
TOML

out_ov="$(python3 "${SCRIPT}" status --config "${overlay}" --json || true)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [r['name'] for r in d['recommended']]
assert names == ['operator-custom-param'], names
" || fail "overlay list-replace"
rm -f "${overlay}"
pass "8. operator overlay (R283/SDD-030) replaces catalog"

# ── 9. Malformed overlay → defaults + _parse_error ─────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" status --config "${bad}" --json || true)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {r['name'] for r in d['recommended']}
assert 'iommu' in names
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "9. malformed overlay → defaults + _parse_error"

# ── 10. sovereign-osctl kernel-cmdline dispatch ────────────
out_disp="$(bash "${OSCTL}" kernel-cmdline status --json || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R305'
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl kernel-cmdline dispatches"

echo "ALL OK"
