#!/usr/bin/env bash
# R291 (E5.M9) — operator-mutable 9-stage workflow profile L3 test.
#
# Operator-named (§1b mandate row, verbatim): "Operator-mutable
# flexible profile (download / fine-tune / parameters / build / run /
# use / train / adapt / eval workflow)". Sibling to R290 lifecycle.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/models/workflow.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope + 9-stage order advertised ────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R291'
assert d['schema_version'] == '1.0.0'
assert d['profile_count'] >= 1
stages = d['stage_names_in_order']
# Operator-named §1b verbatim sequence — the order matters.
want = ['download', 'fine-tune', 'parameters', 'build',
        'run', 'use', 'train', 'adapt', 'eval']
assert stages == want, f'order broken: {stages}'
" || fail "list envelope or 9-stage order"
pass "1. list emits 9 stages in operator-named order"

# ── 2. plan walks the 9 stages with operator-readable details ──
out_p="$(python3 "${SCRIPT}" plan operator-flagship-9-stage --json)"
echo "${out_p}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
got = [s['stage'] for s in d['stages']]
want = ['download', 'fine-tune', 'parameters', 'build',
        'run', 'use', 'train', 'adapt', 'eval']
assert got == want, got
for s in d['stages']:
    for k in ('stage', 'summary', 'command', 'probe'):
        assert k in s
    assert 'complete' in s['probe']
    assert 'detail' in s['probe']
" || fail "plan stage shape"
pass "2. plan walks all 9 stages with command + probe per stage"

# ── 3. Commands render with profile vars (no {placeholders}) ──
echo "${out_p}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for s in d['stages']:
    assert '{' not in s['command'], f'unrendered placeholder in {s[\"stage\"]}: {s[\"command\"]}'
" || fail "unrendered template placeholders"
pass "3. command templates render cleanly (no {placeholders})"

# ── 4. parameters + use probes read structural data from profile ──
echo "${out_p}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_stage = {s['stage']: s for s in d['stages']}
# parameters stage: profile carries non-empty parameters table → complete=true.
assert by_stage['parameters']['probe']['complete'] is True, by_stage['parameters']
# use stage: profile carries non-empty use table → complete=true.
assert by_stage['use']['probe']['complete'] is True, by_stage['use']
" || fail "structural probes"
pass "4. parameters + use stages read structural profile data"

# ── 5. Other stages (no local state) → not-complete ────────────
echo "${out_p}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_stage = {s['stage']: s for s in d['stages']}
# Fresh test env: nothing downloaded / trained / built / online.
for st in ('download', 'fine-tune', 'build', 'train', 'eval'):
    assert by_stage[st]['probe']['complete'] is False, (st, by_stage[st])
# Stages that depend on selfdefctl may report complete=None (probe-
# unavailable) when selfdefctl isn't on PATH — accept either False
# or None for those.
for st in ('run', 'adapt'):
    c = by_stage[st]['probe']['complete']
    assert c in (False, None), (st, by_stage[st])
" || fail "stage state in fresh env"
pass "5. fresh-env stages correctly report incomplete or probe-unavailable"

# ── 6. next-step skips structural stages already complete ────
out_n="$(python3 "${SCRIPT}" next-step operator-flagship-9-stage --json)"
echo "${out_n}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Fresh env: download is first to fail (parameters comes AFTER
# fine-tune in operator order, so download is the gating step).
assert d['next_stage'] == 'download', d
assert d['next_command'].startswith('sovereign-osctl models pull'), d
" || fail "next-step identification"
pass "6. next-step identifies download as gating stage"

# ── 7. Unknown profile → rc=1 + structured error JSON ────────
RC=0
python3 "${SCRIPT}" plan no-such-profile --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "unknown profile must exit 1; got ${RC}"
err="$(python3 "${SCRIPT}" plan no-such-profile --json 2>&1 1>/dev/null)" || true
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'unknown profile' in d['error']
assert isinstance(d['known'], list)
" || fail "unknown-profile error JSON"
pass "7. unknown profile → rc=1 + structured error"

# ── 8. Operator overlay replaces the profile list ────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[profiles]]
name        = "minimal-overlay-profile"
base        = "operator/minimal-base"
method      = "lora-unsloth"
dataset     = "operator-tiny"
adapter_id  = "minimal-adapter"
eval_task   = "minimal-eval"
dpo_dataset = "minimal-prefs"
TOML

out_ov="$(python3 "${SCRIPT}" list --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [p['name'] for p in d['profiles']]
assert names == ['minimal-overlay-profile'], names
assert 'operator-flagship-9-stage' not in names
" || fail "overlay list-replace"
# Plan with overlay must also work + parameters probe → False because
# the overlay omits the parameters table.
out_ov_p="$(python3 "${SCRIPT}" plan minimal-overlay-profile --config "${overlay}" --json)"
echo "${out_ov_p}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_stage = {s['stage']: s for s in d['stages']}
assert by_stage['parameters']['probe']['complete'] is False, by_stage['parameters']
assert by_stage['use']['probe']['complete'] is False, by_stage['use']
" || fail "overlay structural probes reflect missing tables"
rm -f "${overlay}"
pass "8. operator overlay (R283/SDD-030) replaces profile list + structural probes follow"

# ── 9. sovereign-osctl workflow dispatch ─────────────────────
out_disp="$(bash "${OSCTL}" workflow list --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R291'
assert d['sdd_vector'] == 'E5.M9'
" || fail "sovereign-osctl workflow dispatch"
pass "9. sovereign-osctl workflow dispatches to the script"

# ── 10. Probes are read-only (two list calls byte-identical) ──
out2="$(python3 "${SCRIPT}" list --json)"
[[ "${out}" == "${out2}" ]] \
    || fail "list output changed across two invocations — probes mutated state"
pass "10. probes are read-only (two list calls byte-identical)"

# ── 11. config example valid + declares full 9-stage shape ───
example="${REPO_ROOT}/config/workflow-profiles.toml.example"
[[ -f "${example}" ]] || fail "missing ${example}"
python3 -c "
import sys
try:
    import tomllib as t
except ImportError:
    import tomli as t  # type: ignore
data = t.loads(open('${example}').read())
assert 'profiles' in data
for p in data['profiles']:
    for k in ('name', 'base', 'method', 'dataset', 'adapter_id',
              'eval_task', 'dpo_dataset', 'parameters', 'use'):
        assert k in p, f'example profile {p.get(\"name\")} missing {k}'
" || fail "config example must declare full 9-stage field set"
pass "11. config example declares full 9-stage shape (parameters + use + dpo_dataset)"

echo "ALL OK"
