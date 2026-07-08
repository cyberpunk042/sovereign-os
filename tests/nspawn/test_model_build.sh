#!/usr/bin/env bash
# R353 (E5.M18) — model-build planner L3.
# Fills the "build" verb in the §1b 9-verb AI tools pipeline.
# Composes with R350 adapt → R244 fine-tune → R353 build → R232 eval.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="${REPO_ROOT}/scripts/models/build.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. recipes verb returns ≥4 build recipes with full schema ───────
out="$(python3 "${BUILD}" recipes --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['recipe_count'] >= 4
for r in d['recipes']:
    for k in ('recipe_id','name','artifact_kind','needs_adapter',
             'command_template','min_vram_gib','cost_estimate',
             'output_extension','rationale'):
        assert k in r, (k, r)
" || fail "recipes schema"
pass "1. recipes returns ≥4 build recipes with full schema"

# ── 2. Each recipe is one of the 4 expected artifact kinds ──────────
out="$(python3 "${BUILD}" recipes --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
kinds = {r['artifact_kind'] for r in d['recipes']}
expected = {'merged-weights','gguf-quantized','awq-quantized','fp16-safetensors'}
missing = expected - kinds
assert not missing, f'missing artifact kinds: {missing}'
" || fail "kinds"
pass "2. recipes cover all 4 artifact kinds (merged/gguf/awq/fp16)"

# ── 3. plan merge-lora-into-base requires --adapter ─────────────────
rc=0
out="$(python3 "${BUILD}" plan qwen2.5-7b --recipe merge-lora-into-base --json 2>&1)" || rc=$?
[[ "${rc}" == 1 ]] || fail "rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['ok'] is False
assert 'adapter' in d['error'].lower()
" || fail "adapter required"
pass "3. plan merge-lora-into-base WITHOUT --adapter → rc=1 + error"

# ── 4. plan merge-lora-into-base WITH --adapter succeeds ────────────
out="$(python3 "${BUILD}" plan qwen2.5-7b --recipe merge-lora-into-base \
    --adapter /var/lib/sovereign-os/finetunes/qwen-coder --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['ok'] is True
assert d['recipe_id'] == 'merge-lora-into-base'
assert d['adapter'] == '/var/lib/sovereign-os/finetunes/qwen-coder'
assert 'peft merge_and_unload' in d['command']
assert d['fits_on_gpu_model']  # gpu auto-picked
assert d['output_path'].startswith('/var/lib/sovereign-os/model-builds/')
" || fail "merge with adapter"
pass "4. plan merge-lora-into-base WITH --adapter → ok, command + output_path resolved"

# ── 5. plan quantize-gguf is CPU-only (min_vram_gib=0) ──────────────
out="$(python3 "${BUILD}" plan llama-3-7b --recipe quantize-gguf-q4-k-m --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['ok'] is True
assert d['min_vram_gib'] == 0
# command should mention llama.cpp convert + quantize
assert 'llama.cpp' in d['command'].lower()
assert 'q4_k_m' in d['command'].lower()
" || fail "gguf cpu-only"
pass "5. plan quantize-gguf-q4-k-m → CPU-only (min_vram_gib=0) + llama.cpp command"

# ── 6. plan quantize-awq-int4 → fits PRO 6000 (needs 24 GiB) ────────
out="$(python3 "${BUILD}" plan qwen2.5-7b --recipe quantize-awq-int4 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['ok'] is True
assert d['min_vram_gib'] >= 24
# Either RTX 4090 (exactly 24) or PRO 6000 (>24) — both fit
assert d['fits_on_gpu_index'] in (0, 1)
assert 'autoawq' in d['command'].lower()
" || fail "awq"
pass "6. plan quantize-awq-int4 → fits a 24+ GiB GPU + autoawq command"

# ── 7. plan with --target-gpu N enforces explicit GPU choice ────────
# AWQ needs 24 GiB; declared GPU 0 is RTX 4090 (24 GiB, fits exactly).
out="$(python3 "${BUILD}" plan qwen2.5-7b --recipe quantize-awq-int4 \
    --target-gpu 0 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['ok'] is True
assert d['fits_on_gpu_index'] == 0
assert 'RTX 4090' in d['fits_on_gpu_model']
" || fail "target gpu 0"
pass "7. plan --target-gpu 0 → AWQ INT4 fits the 4090 (exact 24 GiB)"

# ── 8. plan unknown recipe → rc=1 + structured error ────────────────
rc=0
err="$(python3 "${BUILD}" plan llama-7b --recipe no-such --json 2>&1 1>/dev/null)" || rc=$?
[[ "${rc}" == 1 ]] || fail "rc=${rc}"
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'error' in d and 'known' in d
assert len(d['known']) >= 4
" || fail "unknown recipe"
pass "8. plan with unknown recipe → rc=1 + structured {error, known}"

# ── 9. show <recipe> returns recipe details ─────────────────────────
out="$(python3 "${BUILD}" show export-safetensors --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
r = d['recipe']
assert r['recipe_id'] == 'export-safetensors'
assert r['artifact_kind'] == 'fp16-safetensors'
assert r['needs_adapter'] is False
" || fail "show"
pass "9. show export-safetensors → full schema with needs_adapter=False"

# ── 10. downstream_verbs hand off to R232 eval + router wire ────────
out="$(python3 "${BUILD}" plan llama-7b --recipe export-safetensors --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
verbs = ' '.join(d['downstream_verbs'])
assert 'model-eval plan' in verbs or 'eval plan' in verbs
assert 'router' in verbs.lower() or 'inference' in verbs.lower()
" || fail "downstream"
pass "10. downstream_verbs hand off to eval plan + router-wire (composes pipeline)"

# ── 11. history verb reads jsonl (NEVER raises on missing file) ─────
out="$(python3 "${BUILD}" history --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'entry_count' in d
assert 'entries' in d
assert isinstance(d['entries'], list)
" || fail "history"
pass "11. history NEVER-raises on missing JSONL; returns entry_count=0"

# ── 12. operator-overlay replaces recipes + build_dir ───────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
build_dir = "/tmp/test-builds"
[[gpus]]
index = 0
model = "Test GPU 64 GiB"
vram_gib = 64
TOML
out="$(python3 "${BUILD}" plan tinyllama --recipe quantize-awq-int4 \
    --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['ok'] is True
assert d['fits_on_gpu_model'] == 'Test GPU 64 GiB'
assert d['output_path'].startswith('/tmp/test-builds/')
" || fail "overlay"
rm -f "${cfg}"
pass "12. operator-overlay replaces gpus + build_dir (R283/SDD-030)"

# ── 13. sovereign-osctl model-build dispatches all 4 subverbs ───────
"${OSCTL}" model-build recipes --json >/dev/null 2>&1 || fail "osctl recipes"
"${OSCTL}" model-build show merge-lora-into-base --json >/dev/null 2>&1 || fail "osctl show"
"${OSCTL}" model-build history --json >/dev/null 2>&1 || fail "osctl history"
# plan returns rc=0 on success
"${OSCTL}" model-build plan llama-7b --recipe export-safetensors --json >/dev/null 2>&1 || fail "osctl plan"
pass "13. sovereign-osctl model-build dispatches recipes/show/history/plan"

echo "ALL OK"
