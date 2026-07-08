#!/usr/bin/env bash
# tests/nspawn/test_gpu_remediate.sh — R249 (SDD-026 Z-5 closure).
# Auto-apply R219 gpu-watch fix commands. DRY-RUN-default.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/gpu-remediate.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_gpu_remediate.sh"
echo

[ -x "${SCRIPT}" ] && ok "gpu-remediate.py executable" \
  || { ko "missing gpu-remediate.py"; exit 1; }
grep -q "R249" "${SCRIPT}" && ok "gpu-remediate.py cites R249" || ko "R249 missing"
grep -q "^  gpu-remediate)" "${OSCTL}" \
  && ok "osctl bridges 'gpu-remediate'" || ko "osctl dispatch missing"
grep -q "gpu-remediate " "${OSCTL}" \
  && ok "osctl help documents 'gpu-remediate'" || ko "osctl help missing"

# ---- JSON shape: no-GPUs path emits stable schema ----
set +e
out="$(python3 "${SCRIPT}" --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "no-GPU path → rc=0" || ko "no-GPU rc=${rc}"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R249', d
assert d['dry_run'] is True, d
for f in ('to_fix_count','results','summary'):
    assert f in d, f'missing {f}'
" \
  && ok "JSON shape: round + dry_run + to_fix_count + results + summary" \
  || ko "JSON shape wrong"

# ---- human render: banner + 'no deviance' message ----
out_h="$(python3 "${SCRIPT}" 2>&1 || true)"
echo "${out_h}" | grep -q "R249 sovereign-os gpu-remediate" \
  && ok "human render carries R249 banner" || ko "banner missing"

# ---- --apply without root + with nvidia-smi missing → rc=2 ----
# On CI (no nvidia-smi), --apply path takes the early-return on
# nvidia-smi-missing — but only if there are GPUs to fix. With 0
# GPUs the script short-circuits with rc=0. So we synthesize one
# fix via a fake gpu-watch shim.
TMP="$(mktemp -d -t r249.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
cat > "${TMP}/gpu-watch.py" <<'PY'
#!/usr/bin/env python3
import json, sys
print(json.dumps({
    "gpus": [
        {
            "idx": 0, "name": "FakeGPU-4090",
            "power_limit_watts": 350.0, "power_draw_watts": 250.0,
            "policed": True, "policy_hint": "4090",
            "deviance_watts": 50.0, "sustained_draw_warning": False,
            "flags": ["power_limit 350W is above safe_limit 300W"],
            "fix_command": "nvidia-smi -i 0 -pl 300",
        }
    ],
    "any_deviance": True,
}))
sys.exit(1)
PY
chmod +x "${TMP}/gpu-watch.py"
# Build a shim that puts our fake gpu-watch.py at the expected path.
SHIM_REPO="${TMP}/repo"
mkdir -p "${SHIM_REPO}/scripts/hardware"
cp "${TMP}/gpu-watch.py" "${SHIM_REPO}/scripts/hardware/gpu-watch.py"
cp "${SCRIPT}" "${SHIM_REPO}/scripts/hardware/gpu-remediate.py"
chmod +x "${SHIM_REPO}/scripts/hardware/gpu-remediate.py"

# ---- dry-run with fake gpu-watch → 1 fix planned, rc=0 ----
set +e
out="$(python3 "${SHIM_REPO}/scripts/hardware/gpu-remediate.py" --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "fake deviance dry-run rc=0" || ko "dry-run rc=${rc}"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['to_fix_count']==1, d
assert d['dry_run'] is True, d
r=d['results'][0]
assert r['outcome']=='dry-run', r
assert r['command']=='nvidia-smi -i 0 -pl 300', r
assert r['idx']==0, r
" \
  && ok "dry-run plan: 1 fix from fake gpu-watch" \
  || ko "dry-run shape wrong"

# ---- --apply without nvidia-smi → rc=2 (when GPUs to fix exist) ----
if [ "$(id -u)" -ne 0 ] && ! command -v nvidia-smi >/dev/null 2>&1; then
  set +e
  out_apply="$(python3 "${SHIM_REPO}/scripts/hardware/gpu-remediate.py" --apply 2>&1)"
  rc_apply=$?
  set -e
  [ "${rc_apply}" -eq 2 ] && ok "--apply without nvidia-smi → rc=2" \
    || ko "expected rc=2, got ${rc_apply}"
  echo "${out_apply}" | grep -qi "nvidia-smi" \
    && ok "error message cites nvidia-smi" || ko "no nvidia-smi hint"
fi

# ---- human render shows the planned fix command ----
out_h="$(python3 "${SHIM_REPO}/scripts/hardware/gpu-remediate.py" 2>&1 || true)"
echo "${out_h}" | grep -q "nvidia-smi -i 0 -pl 300" \
  && ok "human render lists planned fix command" \
  || ko "fix command missing from render"
echo "${out_h}" | grep -q "DRY" \
  && ok "human render marks DRY-run outcome" || ko "DRY marker missing"

# ---- osctl bridge ----
set +e
"${OSCTL}" gpu-remediate --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl gpu-remediate rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R249', d
" \
  && ok "osctl bridge surfaces R249 JSON" \
  || ko "osctl JSON wrong"

echo
total=$((pass + fail))
echo "test_gpu_remediate: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
