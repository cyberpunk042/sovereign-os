#!/usr/bin/env bash
# R316 (E1.M36) — wattage+heat trend watcher L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/wattage-heat-trend-watcher.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

mk_cfg() {
    local state="$1"
    local cfg
    cfg=$(mktemp --suffix=.toml)
    printf 'state_path = "%s"\n' "${state}" > "${cfg}"
    echo "${cfg}"
}

# ── 1. tick --json envelope ────────────────────────────────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
out="$(python3 "${SCRIPT}" tick --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R316'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M36'
for k in ('tick_at', 'tick_at_epoch', 'signals', 'trends',
          'verdict', 'rc', 'history_count'):
    assert k in d, k
" || fail "envelope"
rm -f "${cfg}" "${state}"
pass "1. tick --json envelope"

# ── 2. signals cover wattage_w / cpu_temp_c / gpu_temp_c ───
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
out="$(python3 "${SCRIPT}" tick --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
sig = d['signals']
for k in ('wattage_w', 'cpu_temp_c', 'gpu_temp_c'):
    assert k in sig, k
" || fail "signals"
rm -f "${cfg}" "${state}"
pass "2. signals cover wattage_w / cpu_temp_c / gpu_temp_c"

# ── 3. State persists across ticks ─────────────────────────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
python3 "${SCRIPT}" tick --config "${cfg}" --json >/dev/null || true
python3 "${SCRIPT}" tick --config "${cfg}" --json >/dev/null || true
python3 "${SCRIPT}" tick --config "${cfg}" --json >/dev/null || true
[[ "$(wc -l < "${state}")" -eq 3 ]] || fail "expected 3 rows"
rm -f "${cfg}" "${state}"
pass "3. state JSONL persists (3 ticks → 3 rows)"

# ── 4. classify_trend unit ─────────────────────────────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('w', 'scripts/hardware/wattage-heat-trend-watcher.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# 100 → 110 = +10% → climbing (warn=10)
assert m.classify_trend(100.0, 110.0, 10.0, 25.0) == 'climbing'
# 100 → 130 = +30% → climbing-fast (crit=25)
assert m.classify_trend(100.0, 130.0, 10.0, 25.0) == 'climbing-fast'
# 100 → 102 = +2% → stable
assert m.classify_trend(100.0, 102.0, 10.0, 25.0) == 'stable'
# 100 → 85 = -15% → dropping (warn threshold inverted)
assert m.classify_trend(100.0, 85.0, 10.0, 25.0) == 'dropping'
# Insufficient data
assert m.classify_trend(None, 100.0, 10.0, 25.0) == 'no-data'
print('PASS')
" || fail "classify"
pass "4. classify_trend: climbing / climbing-fast / stable / dropping / no-data"

# ── 5. derive_trends with synthetic history ─────────────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('w', 'scripts/hardware/wattage-heat-trend-watcher.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
cfg = dict(m.DEFAULTS)
cfg['window_size'] = 2

# 4 ticks: prior window avg 100, last window avg 130 → climbing-fast
history = [
    {'signals': {'wattage_w': 100, 'cpu_temp_c': 50, 'gpu_temp_c': 60}},
    {'signals': {'wattage_w': 100, 'cpu_temp_c': 50, 'gpu_temp_c': 60}},
    {'signals': {'wattage_w': 130, 'cpu_temp_c': 50, 'gpu_temp_c': 60}},
    {'signals': {'wattage_w': 130, 'cpu_temp_c': 50, 'gpu_temp_c': 60}},
]
trends = m.derive_trends(history, cfg)
assert trends['wattage_w']['trend'] == 'climbing-fast', trends['wattage_w']
assert trends['cpu_temp_c']['trend'] == 'stable'
assert trends['gpu_temp_c']['trend'] == 'stable'
v, rc = m.aggregate_verdict(trends)
assert v == 'climbing-fast' and rc == 2, (v, rc)
print('PASS')
" || fail "derive_trends"
pass "5. derive_trends: wattage +30% in last window → climbing-fast (rc=2)"

# ── 6. Insufficient history → all signals insufficient-data ──
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('w', 'scripts/hardware/wattage-heat-trend-watcher.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
trends = m.derive_trends([], dict(m.DEFAULTS))
for s in ('wattage_w', 'cpu_temp_c', 'gpu_temp_c'):
    assert trends[s]['trend'] == 'insufficient-data', s
print('PASS')
" || fail "insufficient"
pass "6. insufficient history → all signals = insufficient-data"

# ── 7. history verb returns recent ticks ───────────────────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
for _ in 1 2 3 4 5; do
    python3 "${SCRIPT}" tick --config "${cfg}" --json >/dev/null || true
done
out_h="$(python3 "${SCRIPT}" history --limit 3 --config "${cfg}" --json || true)"
echo "${out_h}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R316'
assert d['total_rows'] == 5
assert d['returned_rows'] == 3
" || fail "history shape"
rm -f "${cfg}" "${state}"
pass "7. history --limit 3 returns 3 of 5 recorded ticks"

# ── 8. status verb returns last-tick + trends ─────────────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
for _ in 1 2 3; do
    python3 "${SCRIPT}" tick --config "${cfg}" --json >/dev/null || true
done
out_s="$(python3 "${SCRIPT}" status --config "${cfg}" --json || true)"
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R316'
assert d['history_count'] == 3
assert d['last_tick'] is not None
assert 'trends' in d
" || fail "status shape"
rm -f "${cfg}" "${state}"
pass "8. status verb returns last_tick + trends"

# ── 9. Operator overlay controls window + climb thresholds ──
state=$(mktemp -u)
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
state_path = "${state}"
window_size = 3
climb_pct_warn = 5.0
climb_pct_crit = 15.0
TOML
out_ov="$(python3 "${SCRIPT}" tick --config "${cfg}" --json || true)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['config']
assert c['window_size'] == 3
assert c['climb_pct_warn'] == 5.0
assert c['climb_pct_crit'] == 15.0
" || fail "overlay knobs"
rm -f "${cfg}" "${state}"
pass "9. operator overlay (R283/SDD-030) controls window + climb thresholds"

# ── 10. sovereign-osctl wattage-heat-trend dispatch ────────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
out_disp="$(bash "${OSCTL}" wattage-heat-trend tick --config "${cfg}" --json 2>/dev/null || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R316'
" || fail "sovereign-osctl dispatch"
rm -f "${cfg}" "${state}"
pass "10. sovereign-osctl wattage-heat-trend dispatches"

echo "ALL OK"
