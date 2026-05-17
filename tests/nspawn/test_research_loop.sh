#!/usr/bin/env bash
# R287 (E1.M19) — hardware-exploit-to-the-max research loop L3 test.
#
# Operator-named (§1b mandate row): "Hardware-exploit-to-the-max
# research loop (continuously evolving SDD + TDD as new BitNet /
# DFlash / VPDPBUSD findings land; 'research mode' verb that surfaces
# upstream changes from bitnet.cpp + transformers + vllm)".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/research/loop.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope ─────────────────────────────────
out="$(python3 "${SCRIPT}" status --json)" || true
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R287', d['round']
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M19'
assert isinstance(d['tracked'], list)
assert d['tracked_count'] == len(d['tracked'])
assert isinstance(d['stale'], bool)
" || fail "status envelope schema"
pass "1. status --json envelope"

# ── 2. Each tracked row has the expected shape ────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
required_verdicts = {
    'matches-baseline', 'drift', 'not-installed', 'baseline-unset',
    'probe-error', 'probe-unavailable', 'version-unknown',
}
for r in d['tracked']:
    for k in ('name', 'kind', 'id', 'baseline', 'probe', 'verdict'):
        assert k in r, f'missing {k} in row: {r}'
    assert r['verdict'] in required_verdicts, r['verdict']
    assert r['kind'] in ('pip', 'binary', 'apt', 'git')
" || fail "tracked-row shape"
pass "2. tracked-row shape + verdict vocabulary"

# ── 3. Default DEFAULT_TRACK covers the operator-named axes ───
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {r['name'] for r in d['tracked']}
must_have = {
    'bitnet-cpp',         # ternary VPDPBUSD fast path
    'wasmtime',           # Wasm-AOT pipeline
    'transformers',       # HF reference runtime
    'vllm',               # Oracle-tier serving
    'trl',                # SFT/DPO training
    'huggingface_hub',    # model fetcher
    'lm-eval',            # eval harness
    'selfdef-cli',        # selfdef control plane
}
missing = must_have - names
if missing:
    print(f'MISSING DEFAULTS: {sorted(missing)}', file=sys.stderr)
    sys.exit(1)
" || fail "default-track operator-axis coverage"
pass "3. default track covers 8 operator-named axes"

# ── 4. topics --json envelope + per-topic shape ───────────────
out_t="$(python3 "${SCRIPT}" topics --json)"
echo "${out_t}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R287'
assert d['topic_count'] == len(d['topics'])
assert d['topic_count'] >= 6
for t in d['topics']:
    for k in ('name', 'mandate_anchor', 'sdd_anchor', 'question', 'signal'):
        assert k in t, f'missing {k} in topic: {t}'
" || fail "topics shape"
pass "4. topics --json shape (≥6 topics, every key required)"

# ── 5. topics anchor mandate Modules + SDDs the operator named ──
echo "${out_t}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
anchors = ' '.join(t['mandate_anchor'] + ' ' + t['sdd_anchor'] for t in d['topics'])
# Each of these mandate Modules / SDDs should appear in ≥1 topic.
must_appear = [
    'E1.M18', 'E1.M17', 'E1.M14', 'E1.M13', 'E1.M5', 'E1.M2',
    'SDD-027', 'SDD-029',
]
missing = [a for a in must_appear if a not in anchors]
if missing:
    print(f'MISSING ANCHORS: {missing}', file=sys.stderr)
    sys.exit(1)
" || fail "topic-anchor coverage"
pass "5. topic anchors cover the operator-named mandate Modules + SDDs"

# ── 6. Operator overlay (REPLACE-on-list semantics) ───────────
overlay_file="$(mktemp --suffix=.toml)"
cat > "${overlay_file}" <<'TOML'
[[track]]
name     = "only-this-via-overlay"
kind     = "binary"
id       = "definitely-not-installed-xyzzy"
baseline = "9.9.9"
notes    = "operator-pull lone track entry to test list-replace"

[[topics]]
name           = "only-this-topic"
mandate_anchor = "E1.M19 (research loop itself)"
sdd_anchor     = "(this overlay's source file)"
question       = "Does the overlay actually replace the default list?"
signal         = "this assertion."
TOML

out_ov_s="$(python3 "${SCRIPT}" status --config "${overlay_file}" --json)" || true
echo "${out_ov_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [r['name'] for r in d['tracked']]
assert names == ['only-this-via-overlay'], f'list-replace not honoured: {names}'
# Operator overlay metadata surfaced.
assert 'track' in d['overlay']['_overlay_keys'] or any(
    k.startswith('track') for k in d['overlay']['_overlay_keys']
), d['overlay']
# Verdict for an absent binary is 'not-installed'.
assert d['tracked'][0]['verdict'] == 'not-installed', d['tracked'][0]
" || fail "overlay track list-replace"
out_ov_t="$(python3 "${SCRIPT}" topics --config "${overlay_file}" --json)"
echo "${out_ov_t}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [t['name'] for t in d['topics']]
assert names == ['only-this-topic'], f'topic list-replace not honoured: {names}'
" || fail "overlay topics list-replace"
rm -f "${overlay_file}"
pass "6. operator overlay (R283/SDD-030) honoured — track + topics REPLACE"

# ── 7. Malformed overlay falls back to defaults without crashing ──
bad_overlay="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}}" > "${bad_overlay}"
out_bad="$(python3 "${SCRIPT}" status --config "${bad_overlay}" --json)" || true
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Defaults still apply.
names = [r['name'] for r in d['tracked']]
assert 'bitnet-cpp' in names, names
# Operator gets a parse_error to investigate.
assert '_parse_error' in d['overlay'], d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad_overlay}"
pass "7. malformed overlay → defaults + _parse_error (no crash)"

# ── 8. sovereign-osctl dispatch ────────────────────────────────
out_disp="$(bash "${OSCTL}" research-loop status --json)" || true
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R287'
assert d['sdd_vector'] == 'E1.M19'
" || fail "sovereign-osctl research-loop dispatch"
pass "8. sovereign-osctl research-loop status dispatches"

# ── 9. status exits 1 when a tracked component is in drift ────
drift_overlay="$(mktemp --suffix=.toml)"
cat > "${drift_overlay}" <<'TOML'
[[track]]
name     = "drift-test"
kind     = "binary"
id       = "sh"
baseline = "definitely-not-the-real-sh-version"
notes    = "Forces a drift verdict — sh is always installed."
TOML
DRIFT_RC=0
python3 "${SCRIPT}" status --config "${drift_overlay}" --json >/dev/null || DRIFT_RC=$?
[[ "${DRIFT_RC}" == "1" ]] \
    || fail "drift must exit 1; got ${DRIFT_RC}"
rm -f "${drift_overlay}"
pass "9. status exits 1 when ≥1 tracked component drifts"

# ── 10. config example exists + is operator-readable TOML ─────
example="${REPO_ROOT}/config/research-loop.toml.example"
[[ -f "${example}" ]] || fail "missing ${example}"
python3 -c "
import sys
try:
    import tomllib as t
except ImportError:
    import tomli as t  # type: ignore
data = t.loads(open('${example}').read())
# It must contain a 'track' and 'topics' array — even if commented
# out in the future, the example header must demonstrate the surface.
assert 'track' in data, 'example must show [[track]] surface'
assert 'topics' in data, 'example must show [[topics]] surface'
" || fail "config example schema"
pass "10. config/research-loop.toml.example is valid TOML demonstrating both surfaces"

echo "ALL OK"
