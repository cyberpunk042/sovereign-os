#!/usr/bin/env bash
# R290 (E5.M6) — end-to-end fine-tune lifecycle L3 test.
#
# Operator-named (§1b mandate row): "End-to-end fine-tune lifecycle
# (operator triggers training → eval → register)". Composes R244
# fine_tune + R232 eval + R182 selfdef registry into one
# operator-pull workflow.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/models/lifecycle.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope ──────────────────────────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R290', d['round']
assert d['schema_version'] == '1.0.0'
assert d['profile_count'] == len(d['profiles'])
assert d['profile_count'] >= 1
" || fail "list envelope schema"
pass "1. list --json envelope"

# ── 2. Default profiles cover both reference workflows ───────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {p['name'] for p in d['profiles']}
for must in ('qwen2-7b-sft-helpdesk', 'llama3-1b-ternary-bench'):
    assert must in names, names
" || fail "default profiles missing"
pass "2. default profiles seed both reference workflows"

# ── 3. plan emits 5 lifecycle stages with the right names ────
out_p="$(python3 "${SCRIPT}" plan qwen2-7b-sft-helpdesk --json)"
echo "${out_p}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
stages = [s['stage'] for s in d['stages']]
assert stages == ['download', 'fine-tune', 'eval', 'register', 'run'], stages
# Every stage must have command + probe + summary.
for s in d['stages']:
    for k in ('stage', 'summary', 'command', 'probe'):
        assert k in s, f'missing {k} in stage'
    assert 'complete' in s['probe']
    assert 'detail' in s['probe']
" || fail "plan stage shape"
pass "3. plan emits 5 stages (download/fine-tune/eval/register/run)"

# ── 4. Command templates render with the profile's vars ──────
echo "${out_p}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cmds = {s['stage']: s['command'] for s in d['stages']}
# Each command must have the profile's variables substituted —
# NO unresolved {var} braces.
for st, cmd in cmds.items():
    assert '{' not in cmd, f'unrendered template in {st}: {cmd}'
# Spot-check that the right substitution happened.
assert 'Qwen/Qwen2-7B-Instruct' in cmds['download']
assert 'qwen2-helpdesk-v1' in cmds['fine-tune']
assert 'qwen2-helpdesk-v1' in cmds['eval']
assert 'qwen2-helpdesk-v1' in cmds['register']
assert 'qwen2-helpdesk-v1' in cmds['run']
" || fail "command-template substitution"
pass "4. command templates render with profile vars (no unsubstituted {placeholders})"

# ── 5. next-step identifies download as first pending stage ──
out_n="$(python3 "${SCRIPT}" next-step qwen2-7b-sft-helpdesk --json)"
echo "${out_n}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# In a fresh test environment, nothing is downloaded → 'download' is next.
assert d['next_stage'] == 'download', d
assert d['next_command'].startswith('sovereign-osctl models pull'), d
assert d['all_complete'] is False
assert d['profile_name'] == 'qwen2-7b-sft-helpdesk'
" || fail "next-step identification"
pass "5. next-step identifies download as first pending stage"

# ── 6. Unknown profile → rc=1 + error JSON on stderr ─────────
UNKNOWN_RC=0
python3 "${SCRIPT}" plan no-such-profile --json 2>/dev/null \
    || UNKNOWN_RC=$?
[[ "${UNKNOWN_RC}" == "1" ]] \
    || fail "unknown profile must exit 1; got ${UNKNOWN_RC}"
err="$(python3 "${SCRIPT}" plan no-such-profile --json 2>&1 1>/dev/null)" || true
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'unknown profile' in d['error']
assert isinstance(d['known'], list)
assert 'qwen2-7b-sft-helpdesk' in d['known']
" || fail "unknown-profile error JSON shape"
pass "6. unknown profile → rc=1 + structured error on stderr"

# ── 7. Operator overlay replaces the profile list entirely ───
overlay_file="$(mktemp --suffix=.toml)"
cat > "${overlay_file}" <<'TOML'
[[profiles]]
name        = "overlay-only-profile"
base        = "operator/custom-base"
method      = "qlora-trl"
dataset     = "operator-private-data"
adapter_id  = "operator-custom-adapter"
eval_task   = "operator-custom-eval"
TOML

out_ov="$(python3 "${SCRIPT}" list --config "${overlay_file}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [p['name'] for p in d['profiles']]
assert names == ['overlay-only-profile'], f'list-replace not honoured: {names}'
# The original defaults must NOT leak through.
assert 'qwen2-7b-sft-helpdesk' not in names
" || fail "overlay list-replace"
rm -f "${overlay_file}"
pass "7. operator overlay replaces profile list (R283/SDD-030 list-replace)"

# ── 8. Malformed overlay falls back to defaults + parse_error ──
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" list --config "${bad}" --json)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {p['name'] for p in d['profiles']}
# Defaults still apply.
assert 'qwen2-7b-sft-helpdesk' in names
# Parse error surfaced.
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "8. malformed overlay → defaults + _parse_error (no crash)"

# ── 9. sovereign-osctl lifecycle dispatch ────────────────────
out_disp="$(bash "${OSCTL}" lifecycle list --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R290'
assert d['profile_count'] >= 1
" || fail "sovereign-osctl lifecycle dispatch"
pass "9. sovereign-osctl lifecycle dispatches to the script"

# ── 10. config/lifecycle-profiles.toml.example is valid + ───
# documents both stages — mandates the example stays in sync with
# the script's surface.
example="${REPO_ROOT}/config/lifecycle-profiles.toml.example"
[[ -f "${example}" ]] || fail "missing ${example}"
python3 -c "
import sys
try:
    import tomllib as t
except ImportError:
    import tomli as t  # type: ignore
data = t.loads(open('${example}').read())
assert 'profiles' in data, 'example must show [[profiles]]'
# Every profile in the example must declare the operator-mandate
# field set (base/method/dataset/adapter_id/eval_task).
for p in data['profiles']:
    for k in ('name', 'base', 'method', 'dataset', 'adapter_id', 'eval_task'):
        assert k in p, f'example profile {p.get(\"name\")} missing {k}'
" || fail "config example schema"
pass "10. config/lifecycle-profiles.toml.example is valid + declares the full field set"

# ── 11. Stage probes are all read-only (no side-effects) ─────
# A SECOND `list --json` invocation should return byte-identical
# JSON — proves no stage probe mutated state between calls.
out2="$(python3 "${SCRIPT}" list --json)"
[[ "${out}" == "${out2}" ]] \
    || fail "list output changed across two invocations — probes mutated state"
pass "11. probes are read-only (two list --json calls return identical JSON)"

echo "ALL OK"
