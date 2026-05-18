#!/usr/bin/env bash
# R366 (E2.M21 close) — multi-level REPL L3.
# Operator-named hook drop verbatim "Python, System and GPU and LLM
# and multiple level and REPL". Closes A-14 partial → ✓.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RP="${REPO_ROOT}/scripts/intelligence/repl.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"
CM="${REPO_ROOT}/scripts/intelligence/coverage-map.py"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. modes returns 4 operator-named modes ─────────────────────────
out="$(python3 "${RP}" modes --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['mode_count'] == 4
names = {m['mode'] for m in d['modes']}
# Operator-verbatim mode names from hook drop
for must in ('python', 'system', 'gpu', 'llm'):
    assert must in names, f'missing mode: {must}'
" || fail "modes"
pass "1. modes returns 4 operator-named modes: python / system / gpu / llm"

# ── 2. show python preserves SDD-032 helper pre-import contract ────
out="$(python3 "${RP}" show python --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['mode_detail']
preamble = '\n'.join(m['preamble_lines'])
# SDD-032 helper library trio + R348 inventory_consult pre-imported
assert 'from operator_overlay import load_with_overlay' in preamble
assert 'import apply_audit' in preamble
assert 'from safe_apply import run_apply_safe' in preamble
assert 'from inventory_consult import find_advisor_caveats' in preamble
" || fail "python preamble"
pass "2. show python — SDD-032 trio + R348 inventory_consult pre-imported"

# ── 3. show system has lspci / nvidia-smi / zpool / ip / journalctl
out="$(python3 "${RP}" show system --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['mode_detail']
refs = ' '.join(m['reference_commands'])
must = ['lspci', 'nvidia-smi', 'zpool status', 'ip -j', 'journalctl', 'systemctl']
for cmd in must:
    assert cmd in refs, f'system mode missing {cmd}'
" || fail "system reference"
pass "3. show system — lspci + nvidia-smi + zpool status + ip + journalctl + systemctl pre-arms"

# ── 4. show gpu cites operator's sovereign-osctl gpu-* verbs ────────
out="$(python3 "${RP}" show gpu --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['mode_detail']
refs = ' '.join(m['reference_commands'])
must = ['gpu-card-advisor', 'gpu-wattage', 'gpu-mode', 'xmp-oc-room',
        'thermal-oc-budget', 'nvidia-smi']
for cmd in must:
    assert cmd in refs, f'gpu mode missing {cmd}'
" || fail "gpu reference"
pass "4. show gpu — gpu-card-advisor + gpu-wattage + gpu-mode + xmp-oc-room + thermal + nvidia-smi"

# ── 5. show llm cites trinity profile + inference + model-lifecycle
out="$(python3 "${RP}" show llm --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['mode_detail']
refs = ' '.join(m['reference_commands'])
must = ['inference status', 'inference query', 'models list',
        'models adapt', 'models build', 'models eval',
        'trinity profile show']
for cmd in must:
    assert cmd in refs, f'llm mode missing {cmd}'
# Operator-named 3 runtime profiles cross-link
assert 'ultra-sovereign-efficiency' in refs
assert 'high-concurrency-burst' in refs
assert 'deep-context-synthesis' in refs
" || fail "llm reference"
pass "5. show llm — inference/models/trinity verbs + 3 operator-named runtime profiles cross-linked"

# ── 6. exec system runs one-shot command + captures stdout ──────────
out="$(python3 "${RP}" exec system 'echo R366-test' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['rc'] == 0
assert 'R366-test' in d['stdout']
assert d['mode'] == 'system'
assert d['command'] == 'echo R366-test'
" || fail "exec one-shot"
pass "6. exec system 'echo R366-test' → rc=0 + stdout contains 'R366-test'"

# ── 7. exec python passes preamble env to subprocess ───────────────
out="$(python3 "${RP}" exec python 'printenv PYTHONPATH' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# PYTHONPATH env var should include scripts/lib
assert 'scripts/lib' in d['stdout'], d
" || fail "python env"
pass "7. exec python carries PYTHONPATH=scripts/lib env (SDD-032 helper discovery)"

# ── 8. exec NEVER-raises — bad command rc≠0 + stderr captured ──────
out="$(python3 "${RP}" exec system 'false' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['rc'] == 1
" || fail "exec bad cmd"
# Real raise scenarios: timeout
out="$(python3 "${RP}" exec system 'sleep 1' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['rc'] == 0  # 1s < 30s timeout
" || fail "exec slow ok"
pass "8. exec NEVER-raises — false → rc=1; sleep 1 → rc=0 (under 30s timeout)"

# ── 9. show unknown mode → rc=1 + known_modes list ─────────────────
rc=0; err="$(python3 "${RP}" show no-such-mode --json 2>&1 1>/dev/null)" || rc=$?
[[ "${rc}" == 1 ]] || fail "rc=${rc}"
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'known_modes' in d
assert set(d['known_modes']) >= {'python','system','gpu','llm'}
" || fail "show unknown"
pass "9. show unknown mode → rc=1 + known_modes list contains 4 modes"

# ── 10. operator-overlay extends modes (R283/SDD-030) ──────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
[[modes]]
mode = "test-mode"
title = "Operator-overlay test mode"
rationale = "test"
spawn_command = "/bin/sh"
preamble_lines = ["# test"]
reference_commands = ["echo test"]
[modes.env_vars]
TEST = "1"
TOML
out="$(python3 "${RP}" modes --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {m['mode'] for m in d['modes']}
assert 'test-mode' in names
" || fail "overlay"
rm -f "${cfg}"
pass "10. operator-overlay extends modes list (R283/SDD-030 lists-replace)"

# ── 11. sovereign-osctl repl dispatches modes/show/exec ─────────────
"${OSCTL}" repl modes --json >/dev/null 2>&1 || fail "osctl modes"
"${OSCTL}" repl show gpu --json >/dev/null 2>&1 || fail "osctl show"
"${OSCTL}" repl exec system 'echo ok' --json >/dev/null 2>&1 || fail "osctl exec"
pass "11. sovereign-osctl repl dispatches modes/show/exec (shell is interactive-only, untested)"

# ── 12. coverage-map A-14 now ✓ shipped (was partial) ──────────────
out="$(python3 "${CM}" show A-14 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
a = d['axis']
assert a['status'] == '✓ shipped', a['status']
verbs = ' '.join(a['implementing_verbs'])
assert 'repl modes' in verbs
assert 'repl show python' in verbs
assert 'repl exec' in verbs
" || fail "A-14 flip"
pass "12. coverage-map A-14 multi-level REPL flipped partial → ✓ shipped (R366 verbs cited)"

# ── 13. coverage audit now rc=0 with 0 TODO + 0 partial ────────────
rc=0; out="$(python3 "${CM}" audit --json 2>&1)" || rc=$?
[[ "${rc}" == 0 ]] || fail "audit rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# After R366 closes A-14, partial should drop to 0
assert d['todo_count'] == 0
assert d['partial_count'] == 0, f'expected 0 partial; got {d[\"partial_count\"]}'
assert d['shipped_count'] >= 30
" || fail "audit count"
pass "13. coverage audit: 0 TODO + 0 partial + ≥30 ✓ shipped (full operator-demand coverage)"

echo "ALL OK"
