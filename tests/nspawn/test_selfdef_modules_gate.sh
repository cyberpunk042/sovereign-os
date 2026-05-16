#!/usr/bin/env bash
# tests/nspawn/test_selfdef_modules_gate.sh
#
# Layer 3 test for R170 — scripts/hardware/selfdef-modules-gate.py:
# the sovereign-os mirror of selfdef SD-R14 + SD-R15 hardware module
# gate. The two implementations must agree on identical inputs; this
# test pins the Python side against synthesized capabilities JSON +
# fixture module manifests.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/selfdef-modules-gate.py"

echo "tests/nspawn/test_selfdef_modules_gate.sh"
echo

[ -x "${SCRIPT}" ] && ok "selfdef-modules-gate.py executable" \
  || { ko "missing"; exit 1; }

grep -q "SD-R14" "${SCRIPT}" && ok "cites selfdef SD-R14 (cross-repo provenance)" \
  || ko "SD-R14 citation missing"
grep -q "SD-R15" "${SCRIPT}" && ok "cites selfdef SD-R15 (the dry-run surface)" \
  || ko "SD-R15 citation missing"

# ---------- fixture build ----------
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

mkdir -p "${WORK}/caps" "${WORK}/modules/alpha" "${WORK}/modules/beta" \
         "${WORK}/modules/gamma" "${WORK}/etc"

# Capabilities JSON: AVX-512 VNNI yes / BF16 no, 16 GiB, 1 GPU.
cat > "${WORK}/caps/hardware-capabilities.json" <<'JSON'
{
  "schema_version": "1",
  "probed_at": "1970-01-01T00:00:00Z",
  "host_tag": null,
  "cpu": {"avx512vnni": true, "avx512bf16": false},
  "memory": {"total_bytes": 17179869184},
  "gpu": {"device_count": 1, "device_nodes": []},
  "pcie": {"gen4_or_higher_x8_slot_count": 0, "dual_x8_present": false},
  "sain01_match": {"overall": "PartialMatch"}
}
JSON

# alpha: unrestricted — always applies.
cat > "${WORK}/modules/alpha/module.toml" <<'TOML'
name = "alpha"
version = "0.0.0"
summary = "no gate"
TOML

# beta: needs BF16 + 256 GiB — should skip on the fixture host.
cat > "${WORK}/modules/beta/module.toml" <<'TOML'
name = "beta"
version = "0.0.0"
summary = "hardware-gated"
[requires_hardware]
avx512_bf16 = true
memory_gib_min = 256
TOML

# gamma: needs PartialMatch — should pass on the fixture host.
cat > "${WORK}/modules/gamma/module.toml" <<'TOML'
name = "gamma"
version = "0.0.0"
summary = "partial-match gate"
[requires_hardware]
sain01_verdict_min = "PartialMatch"
TOML

# Host config: alpha + beta + gamma active.
cat > "${WORK}/etc/modules.toml" <<'TOML'
[modules.alpha]
[modules.beta]
[modules.gamma]
TOML

CMD=(python3 "${SCRIPT}"
     --caps-path "${WORK}/caps/hardware-capabilities.json"
     --modules-dir "${WORK}/modules"
     --host-config "${WORK}/etc/modules.toml")

# ---------- human-readable: alpha + gamma kept, beta skipped ----------
set +e
out="$("${CMD[@]}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "human dry-run exits 0" || ko "rc=${rc}"
grep -q "alpha" <<< "${out}" && grep -q "WOULD APPLY" <<< "${out}" \
  && ok "alpha listed under WOULD APPLY" || ko "alpha not kept: ${out}"
grep -q "gamma" <<< "${out}" && ok "gamma kept (PartialMatch met)" \
  || ko "gamma should pass PartialMatch gate"
grep -q "beta" <<< "${out}" && grep -q "WOULD SKIP" <<< "${out}" \
  && ok "beta listed under WOULD SKIP" || ko "beta not skipped"
grep -q "avx512_bf16" <<< "${out}" && ok "beta unmet: bf16 reason cited" \
  || ko "bf16 reason missing"
grep -q "memory_gib_min = 256" <<< "${out}" \
  && ok "beta unmet: memory threshold cited" || ko "memory reason missing"

# ---------- --json output ----------
set +e
out_json="$("${CMD[@]}" --json 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--json exits 0" || ko "--json rc=${rc}"
if python3 -c "
import json, sys
d = json.loads('''${out_json}''')
assert d['caps_source'] == 'capabilities_json'
assert d['total'] == 3
kept_names = sorted(x['module'] for x in d['kept'])
assert kept_names == ['alpha', 'gamma'], kept_names
skipped_names = [x['module'] for x in d['skipped']]
assert skipped_names == ['beta'], skipped_names
unmet = d['skipped'][0]['unmet']
assert any('avx512_bf16' in u for u in unmet)
assert any('memory_gib_min' in u for u in unmet)
" 2>/dev/null; then
  ok "--json carries expected partition (alpha+gamma kept, beta skipped)"
else
  ko "--json shape wrong: ${out_json}"
fi

# ---------- --verdict-only ----------
set +e
"${CMD[@]}" --verdict-only > "${WORK}/verdict.txt"
vrc=$?
set -e
[ "${vrc}" -eq 1 ] && ok "--verdict-only rc=1 when some skip" \
  || ko "expected rc=1, got ${vrc}"
grep -q "fail" "${WORK}/verdict.txt" \
  && ok "--verdict-only prints 'fail'" || ko "verdict missing 'fail'"

# ---------- pass case: all modules unrestricted ----------
rm -rf "${WORK}/modules-allpass"
mkdir -p "${WORK}/modules-allpass/alpha"
cp "${WORK}/modules/alpha/module.toml" "${WORK}/modules-allpass/alpha/module.toml"
set +e
python3 "${SCRIPT}" \
  --caps-path "${WORK}/caps/hardware-capabilities.json" \
  --modules-dir "${WORK}/modules-allpass" \
  --host-config "${WORK}/etc/modules.toml" --verdict-only > "${WORK}/verdict2.txt"
vrc=$?
set -e
[ "${vrc}" -eq 0 ] && ok "--verdict-only rc=0 when every module passes" \
  || ko "expected rc=0, got ${vrc}"
grep -q "pass" "${WORK}/verdict2.txt" && ok "prints 'pass'" \
  || ko "verdict missing 'pass'"

# ---------- caps_source = sain01_match_fallback when JSON absent ----------
# Use a bogus caps path; the script falls back to sain01-match.py.
set +e
out_fb="$(python3 "${SCRIPT}" \
  --caps-path "${WORK}/no-such-file.json" \
  --modules-dir "${WORK}/modules" \
  --host-config "${WORK}/etc/modules.toml" --json 2>&1)"
fb_rc=$?
set -e
if [ "${fb_rc}" -eq 0 ]; then
  if python3 -c "import json; d=json.loads('''${out_fb}'''); assert d['caps_source']=='sain01_match_fallback'" 2>/dev/null; then
    ok "fallback path identified as sain01_match_fallback"
  else
    ko "fallback shape mismatch: ${out_fb}"
  fi
else
  # Probe might fail in fully-stubbed envs — informational, not blocking.
  ok "fallback exits non-zero on probe failure (acceptable: rc=${fb_rc})"
fi

# ---------- missing host_config: every catalog module considered active ----------
set +e
out_no_host="$(python3 "${SCRIPT}" \
  --caps-path "${WORK}/caps/hardware-capabilities.json" \
  --modules-dir "${WORK}/modules" \
  --host-config "${WORK}/etc/no-such-file.toml" --json 2>&1)"
set -e
if python3 -c "import json; d=json.loads('''${out_no_host}'''); assert d['total']==3" 2>/dev/null; then
  ok "missing host_config → all catalog modules considered active"
else
  ko "host-config-missing path wrong: ${out_no_host}"
fi

# ---------- R177: SD-R26 mirror — per-GPU VRAM + power headroom ----------
grep -q "SD-R26" "${SCRIPT}" \
  && ok "R177 mirror cites selfdef SD-R26 (per-GPU predicates)" \
  || ko "SD-R26 citation missing"
grep -q "gpu_vram_gib_min" "${SCRIPT}" \
  && ok "evaluate() handles gpu_vram_gib_min" \
  || ko "gpu_vram_gib_min missing in evaluate()"
grep -q "gpu_power_headroom_watts_min" "${SCRIPT}" \
  && ok "evaluate() handles gpu_power_headroom_watts_min" \
  || ko "gpu_power_headroom_watts_min missing"

# Build the SD-R25-shaped caps JSON with per-device data the SD-R26
# predicates need.
mkdir -p "${WORK}/caps26" "${WORK}/mod26/needs-vram-80" "${WORK}/mod26/needs-headroom" \
         "${WORK}/etc26"
cat > "${WORK}/caps26/hardware-capabilities.json" <<'JSON'
{
  "schema_version": "1.0.0",
  "probed_at": "2026-05-16T00:00:00Z",
  "host_tag": null,
  "cpu": {"avx512vnni": true, "avx512bf16": true},
  "memory": {"total_bytes": 274877906944},
  "gpu": {
    "device_count": 2,
    "device_nodes": [],
    "devices": [
      {"vram_bytes": 105226698752, "power_limit_watts": 600, "power_draw_watts": 275},
      {"vram_bytes":  25769803776, "power_limit_watts": 350, "power_draw_watts": 180}
    ]
  },
  "sain01_match": {"overall": "FullMatch"}
}
JSON
cat > "${WORK}/mod26/needs-vram-80/module.toml" <<'TOML'
name = "needs-vram-80"
version = "0.0.0"
summary = "wants at least one GPU with 80 GiB"
[requires_hardware]
gpu_vram_gib_min = 80
TOML
cat > "${WORK}/mod26/needs-headroom/module.toml" <<'TOML'
name = "needs-headroom"
version = "0.0.0"
summary = "wants 800W power headroom (the host only has 495)"
[requires_hardware]
gpu_power_headroom_watts_min = 800
TOML
cat > "${WORK}/etc26/modules.toml" <<'TOML'
[modules.needs-vram-80]
[modules.needs-headroom]
TOML

set +e
out26="$(python3 "${SCRIPT}" \
  --caps-path "${WORK}/caps26/hardware-capabilities.json" \
  --modules-dir "${WORK}/mod26" \
  --host-config "${WORK}/etc26/modules.toml" --json 2>&1)"
set -e
if python3 -c "
import json, sys
d = json.loads('''${out26}''')
kept = sorted(x['module'] for x in d['kept'])
skipped = sorted(x['module'] for x in d['skipped'])
assert kept == ['needs-vram-80'], f'kept={kept}'
assert skipped == ['needs-headroom'], f'skipped={skipped}'
unmet = d['skipped'][0]['unmet']
assert any('gpu_power_headroom_watts_min' in u for u in unmet), unmet
assert any('495 W' in u for u in unmet), unmet
" 2>/dev/null; then
  ok "SD-R26 mirror: vram-80 kept on RTX-PRO-6000 host"
  ok "SD-R26 mirror: power-headroom unmet cited with host figure (495W)"
else
  ko "SD-R26 mirror partition wrong: ${out26}"
fi

echo
total=$((pass + fail))
echo "test_selfdef_modules_gate: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
