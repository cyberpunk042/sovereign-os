#!/usr/bin/env bash
# tests/nspawn/test_wasm_aot_enforcer.sh — R281 (E1.M17).
# Wasm-to-AVX-512 AOT pipeline enforcer per master spec §20.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/wasm-aot-enforcer.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_wasm_aot_enforcer.sh"
echo

[ -x "${SCRIPT}" ] && ok "wasm-aot-enforcer.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R281\|E1.M17" "${SCRIPT}" && ok "script cites R281/E1.M17" \
  || ko "R281 missing"
grep -q "master spec.*20\|§20\|§ 20" "${SCRIPT}" \
  && ok "script cites master-spec §20 anchor" || ko "anchor missing"
grep -q "znver5" "${SCRIPT}" \
  && ok "script enforces target-cpu=znver5" || ko "znver5 missing"
grep -q "^  wasm-aot)" "${OSCTL}" \
  && ok "osctl bridges 'wasm-aot'" || ko "osctl dispatch missing"

# ---- status --json shape ----
set +e
out="$(python3 "${SCRIPT}" status --json 2>/dev/null)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "status rc ∈ {0,1} (got ${rc})"
else
  ko "rc unexpected ${rc}"
fi
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R281', d
for f in ('wasmtime','cranelift_target','env_state','verdict',
         'spec_target_cpu','spec_opt_level','spec_relaxed_simd'):
    assert f in d, f'missing {f}'
assert d['spec_target_cpu'] == 'znver5', d
assert d['spec_opt_level'] == '3', d
assert d['spec_relaxed_simd'] == 'true', d
assert d['verdict']['fit'] in ('ready','partial','not-supported'), d
" \
  && ok "status --json: spec constants (znver5/3/true) + verdict enum" \
  || ko "status shape wrong"

# ---- compile-cmd: emits canonical incantation ----
out="$(python3 "${SCRIPT}" compile-cmd /tmp/test.wasm --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R281', d
assert d['wasm_path'] == '/tmp/test.wasm', d
assert d['command'][0] == 'taskset', d
# Master spec §20 mandates -c 0-11
assert '0-11' in d['command'], d
assert 'wasmtime' in d['command'] and 'compile' in d['command'], d
assert '/tmp/test.wasm' in d['command'], d
# Env preamble references the spec knobs
env_text = '\\n'.join(d['env_preamble'])
assert 'target-cpu=znver5' in env_text, env_text
assert 'opt-level=3' in env_text, env_text
assert 'relaxed-simd=true' in env_text, env_text
" \
  && ok "compile-cmd: taskset -c 0-11 + wasmtime compile + znver5/3/relaxed-simd env" \
  || ko "compile-cmd shape wrong"

# ---- env-state detection in-process ----
python3 -c "
import importlib.util, os
os.environ['WASMTIME_COMPARE_OPTIONS'] = '-C target-cpu=znver5 -C opt-level=3 -C relaxed-simd=true'
spec = importlib.util.spec_from_file_location('wa','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
env = m.detect_env_state()
assert env['target_cpu_set'] is True
assert env['opt_level_set'] is True
assert env['relaxed_simd_set'] is True
" \
  && ok "detect_env_state: WASMTIME_COMPARE_OPTIONS set → all 3 conformance bools True" \
  || ko "env detection wrong"

# ---- env-state via RUSTFLAGS fallback ----
python3 -c "
import importlib.util, os
os.environ.pop('WASMTIME_COMPARE_OPTIONS', None)
os.environ['RUSTFLAGS'] = '-Ctarget-cpu=znver5 -C opt-level=3 -C relaxed-simd=true'
spec = importlib.util.spec_from_file_location('wa','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
env = m.detect_env_state()
assert env['target_cpu_set'] is True, env
assert env['opt_level_set'] is True, env
" \
  && ok "detect_env_state: RUSTFLAGS=-Ctarget-cpu=znver5 ... → conformance" \
  || ko "RUSTFLAGS fallback wrong"

# ---- env-state when nothing set → all False ----
python3 -c "
import importlib.util, os
os.environ.pop('WASMTIME_COMPARE_OPTIONS', None)
os.environ.pop('RUSTFLAGS', None)
spec = importlib.util.spec_from_file_location('wa','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
env = m.detect_env_state()
assert env['target_cpu_set'] is False, env
assert env['opt_level_set'] is False, env
assert env['relaxed_simd_set'] is False, env
" \
  && ok "detect_env_state: no envs set → all conformance False" \
  || ko "unset path wrong"

# ---- verdict trichotomy ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('wa','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# wasmtime missing → not-supported
v = m.derive_verdict({'binary_path': None, 'version': None, 'supports_compile': False},
                      {'target_listing_available': False, 'znver5_explicit': False},
                      {'target_cpu_set': False, 'opt_level_set': False, 'relaxed_simd_set': False})
assert v['fit'] == 'not-supported', v
# wasmtime present but compile subcommand missing → partial
v = m.derive_verdict({'binary_path': '/usr/bin/wasmtime', 'version': '0.20', 'supports_compile': False},
                      {'target_listing_available': True, 'znver5_explicit': False},
                      {'target_cpu_set': False, 'opt_level_set': False, 'relaxed_simd_set': False})
assert v['fit'] == 'partial', v
# wasmtime + compile + env-knobs set → ready
v = m.derive_verdict({'binary_path': '/usr/bin/wasmtime', 'version': '20.0', 'supports_compile': True},
                      {'target_listing_available': True, 'znver5_explicit': True},
                      {'target_cpu_set': True, 'opt_level_set': True, 'relaxed_simd_set': True})
assert v['fit'] == 'ready', v
# wasmtime + compile + missing env → partial (with env hint)
v = m.derive_verdict({'binary_path': '/usr/bin/wasmtime', 'version': '20.0', 'supports_compile': True},
                      {'target_listing_available': True, 'znver5_explicit': True},
                      {'target_cpu_set': False, 'opt_level_set': True, 'relaxed_simd_set': True})
assert v['fit'] == 'partial', v
assert 'target-cpu' in v['reason'], v
" \
  && ok "derive_verdict: 4 cases (no-wasmtime / no-compile / ready / missing-env-knob)" \
  || ko "verdict logic wrong"

# ---- advisory shape ----
out="$(python3 "${SCRIPT}" advisory --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R281', d
assert d['fit'] in ('ready','partial','not-supported'), d
" \
  && ok "advisory --json shape" \
  || ko "advisory shape wrong"

# ---- human render banner ----
out_h="$(python3 "${SCRIPT}" status 2>&1 || true)"
echo "${out_h}" | grep -q "R281 sovereign-os wasm-aot-enforcer" \
  && ok "human banner present" || ko "banner missing"
echo "${out_h}" | grep -q "master spec § 20" \
  && ok "human render cites master spec §20" || ko "spec anchor missing"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r281.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" wasm-aot status --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl wasm-aot status rc ∈ {0,1}"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R281', d
" \
  && ok "osctl bridge surfaces R281 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" wasm-aot nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown wasm-aot subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_wasm_aot_enforcer: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
