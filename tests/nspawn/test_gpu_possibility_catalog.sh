#!/usr/bin/env bash
# R295 (E1.M23) — GPU possibility catalog L3.
#
# Operator-named (§1b mandate row): "RTX 4090 details and possibilities
# established and non-established, same for the RTX Pro 6000 and the
# CPU and AVX512".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/gpu-possibility-catalog.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope ─────────────────────────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R295'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M23'
assert d['total_count'] >= 10
" || fail "list envelope"
pass "1. list --json envelope"

# ── 2. ALL operator-named subjects present ──────────────────
# §1b verbatim names four: "RTX 4090 ... the RTX Pro 6000 and the CPU
# and AVX512". Anchoring only the two GPUs would itself minimize the
# operator's named set — lock all four (the CPU/AVX-512 card covers the
# 'CPU and AVX512' subjects).
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cards = set(d['cards'])
for card in ('RTX 4090', 'RTX PRO 6000', 'CPU (AVX-512)'):
    assert card in cards, (card, cards)
" || fail "operator-named subjects missing"
pass "2. RTX 4090 + RTX PRO 6000 + CPU (AVX-512) all present (4 operator-named subjects)"

# ── 3. Entries partitioned by status (established + non-established) ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
statuses = {e['status'] for e in d['entries']}
assert statuses == {'established', 'non-established'}, statuses
# Each entry has the operator-required fields.
for e in d['entries']:
    for k in ('card', 'capability', 'status', 'evidence'):
        assert k in e, (k, e)
" || fail "entry shape"
pass "3. entries partitioned into established / non-established with full shape"

# ── 4. --card filter narrows to one card ────────────────────
out_4090="$(python3 "${SCRIPT}" list --card 'RTX 4090' --json)"
echo "${out_4090}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for e in d['entries']:
    assert e['card'] == 'RTX 4090', e
" || fail "--card filter"
pass "4. --card filter narrows to RTX 4090 only"

# ── 5. --status filter narrows to one status ────────────────
out_est="$(python3 "${SCRIPT}" list --status established --json)"
echo "${out_est}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for e in d['entries']:
    assert e['status'] == 'established', e
assert len(d['entries']) >= 4  # 2 cards × ≥2 established each
" || fail "--status filter"
pass "5. --status established filter narrows correctly"

# ── 6. show <card> renders per-card detail with counts ──────
out_show="$(python3 "${SCRIPT}" show 'RTX PRO 6000' --json)"
echo "${out_show}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['card'] == 'RTX PRO 6000'
# PRO 6000 has multiple established + multiple non-established.
assert d['established_count'] >= 3
assert d['non_established_count'] >= 2
for e in d['entries']:
    assert e['card'] == 'RTX PRO 6000'
" || fail "show shape"
pass "6. show <card> renders per-card detail + counts"

# ── 7. gaps verb lists every non-established capability ────
out_gaps="$(python3 "${SCRIPT}" gaps --json)"
echo "${out_gaps}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['gap_count'] >= 5  # both cards have multiple gaps
for e in d['entries']:
    assert e['status'] == 'non-established', e
" || fail "gaps shape"
pass "7. gaps verb lists every non-established capability"

# ── 8. Operator overlay replaces catalog entirely ────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[entries]]
card        = "Operator-Custom-GPU"
capability  = "operator-pull custom probe"
status      = "established"
evidence    = "for test purposes only"
TOML

out_ov="$(python3 "${SCRIPT}" list --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['cards'] == ['Operator-Custom-GPU'], d['cards']
assert d['total_count'] == 1
" || fail "overlay list-replace"
rm -f "${overlay}"
pass "8. operator overlay (R283/SDD-030) replaces catalog entirely"

# ── 9. Malformed overlay → defaults + _parse_error ──────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" list --config "${bad}" --json)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'RTX 4090' in d['cards']
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "9. malformed overlay → defaults + _parse_error"

# ── 10. sovereign-osctl gpu-possibility dispatch + read-only invariant ──
out_disp="$(bash "${OSCTL}" gpu-possibility list --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R295'
" || fail "sovereign-osctl gpu-possibility dispatch"
# Two list calls byte-identical.
out2="$(python3 "${SCRIPT}" list --json)"
[[ "${out}" == "${out2}" ]] || fail "list output changed between calls"
pass "10. sovereign-osctl gpu-possibility dispatches + read-only invariant"

echo "ALL OK"
