#!/usr/bin/env bash
# tests/nspawn/test_models_toolchains.sh — R242 (SDD-026 Z-2 expansion).
# Inference + fine-tune toolchain catalog with live per-toolchain
# detection. Operator-named "LM Studio / LM Link / Unsloth".

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/models/toolchains.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_models_toolchains.sh"
echo

[ -x "${SCRIPT}" ] && ok "toolchains.py executable" \
  || { ko "missing toolchains.py"; exit 1; }
grep -q "R242" "${SCRIPT}" && ok "toolchains.py cites R242" || ko "R242 missing"
grep -q "models toolchains" "${OSCTL}" \
  && ok "osctl help documents 'models toolchains'" || ko "osctl help missing"
grep -q "    toolchains)" "${OSCTL}" \
  && ok "osctl dispatches 'toolchains'" || ko "osctl dispatch missing"

# ---- list --json: catalog shape + 12 entries minimum ----
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R242', d
assert d['vector'].startswith('SDD-026 Z-2'), d
# 12+ toolchains shipped in cycle 8.
assert d['counts']['total']>=12, d
# Every toolchain has required fields.
for t in d['toolchains']:
    for f in ('name','kind','summary','operator_role','install_hint',
             'license','hardware_fit','installed','detect'):
        assert f in t, f'{t[\"name\"]} missing {f}'
    assert t['kind'] in ('inference','fine-tune','eval','both'), t
    assert isinstance(t['installed'], bool)
" \
  && ok "list --json: 12+ toolchains with required fields" \
  || ko "list shape wrong"

# ---- specific operator-named toolchains must be present ----
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
names={t['name'] for t in d['toolchains']}
for required in ('llama.cpp','bitnet.cpp','vllm','ollama','lm-studio',
                 'unsloth','transformers','trl','huggingface-cli',
                 'lm-eval-harness','mteb','dflash'):
    assert required in names, f'missing {required} from catalog: {names}'
" \
  && ok "catalog contains every operator-named toolchain" \
  || ko "operator-named toolchain missing"

# ---- list --kind filter ----
for kind in inference fine-tune eval; do
  set +e
  out="$(python3 "${SCRIPT}" list --kind "${kind}" --json 2>/dev/null)"
  rc=$?
  set -e
  [ "${rc}" -eq 0 ] && ok "list --kind ${kind} rc=0" \
    || ko "list --kind ${kind} rc=${rc}"
done

# ---- list --kind bogus → rc=2 (argparse) ----
set +e
python3 "${SCRIPT}" list --kind nope > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "list --kind bogus → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- list --installed-only ----
set +e
out="$(python3 "${SCRIPT}" list --installed-only --json 2>/dev/null)"
set -e
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for t in d['toolchains']:
    assert t['installed'] is True, t
" \
  && ok "list --installed-only filters to installed entries only" \
  || ko "installed-only filter wrong"

# ---- info on a known toolchain ----
set +e
out="$(python3 "${SCRIPT}" info unsloth --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "info unsloth rc=0" || ko "info unsloth rc=${rc}"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R242', d
assert d['name']=='unsloth', d
assert d['kind']=='fine-tune', d
assert 'detect' in d, d
" \
  && ok "info unsloth surfaces operator-named LoRA fine-tuner" \
  || ko "info shape wrong"

# ---- info on unknown toolchain → rc=2 ----
set +e
out_bad="$(python3 "${SCRIPT}" info nope 2>&1)"
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "info unknown → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"
echo "${out_bad}" | grep -q "unknown toolchain" \
  && ok "info error cites unknown toolchain" || ko "no hint"

# ---- human render: banner + glyphs ----
out_h="$(python3 "${SCRIPT}" list 2>/dev/null)"
echo "${out_h}" | grep -q "R242 sovereign-os models toolchains" \
  && ok "list human render carries R242 banner" || ko "banner missing"
echo "${out_h}" | grep -qE "totals:" \
  && ok "human render has totals" || ko "totals missing"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r242.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" models toolchains list --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl models toolchains list rc=0" \
  || ko "osctl bridge rc=${rc}: $(cat ${TMP}/osctl.err)"
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R242', d
" \
  && ok "osctl bridge surfaces R242 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" models toolchains nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown toolchains subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_models_toolchains: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
