#!/usr/bin/env bash
# tests/nspawn/test_models_info.sh — R231 (SDD-026 Z-2): rich detail
# surface for one catalog model. LM-Studio-equivalent.

set -euo pipefail

PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3=/usr/bin/python3
  fi
fi

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/models/info.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
CATALOG="${__REPO_ROOT}/models/catalog.yaml"

echo "tests/nspawn/test_models_info.sh"
echo

[ -x "${SCRIPT}" ] && ok "info.py executable" \
  || { ko "missing info.py"; exit 1; }
grep -q "R231" "${SCRIPT}" && ok "info.py cites R231" || ko "R231 missing"
grep -q "models info" "${OSCTL}" \
  && ok "osctl help documents 'models info'" || ko "osctl help missing"
grep -q "    info)" "${OSCTL}" \
  && ok "osctl dispatches 'models info'" || ko "osctl dispatch missing"

# Pick a known slug from the catalog.
SLUG="BitNet-b1.58-2B-4T"

# ---- human render carries every required section ----
out="$("${PYTHON3}" "${SCRIPT}" "${SLUG}")"
for needle in \
    "R231 sovereign-os models info" \
    "IDENTITY" \
    "CLASSIFICATION" \
    "FOOTPRINT" \
    "RUNTIME" \
    "ACTIONS" \
    "class:" \
    "quantization:" \
    "size_class:" \
    "parameters:" \
    "vram_gib_min:" \
    "context_tokens:" \
    "engine:"; do
  echo "${out}" | grep -q "${needle}" \
    && ok "human render carries '${needle}'" \
    || ko "missing section: ${needle}"
done

# ---- JSON shape matches the dashboard contract ----
json="$("${PYTHON3}" "${SCRIPT}" "${SLUG}" --json)"
echo "${json}" | "${PYTHON3}" -c "
import json,sys
d = json.load(sys.stdin)
assert d['round'] == 'R231', d
assert d['vector'].startswith('SDD-026 Z-2'), d
m = d['model']
for k in ('id','hf_repo_id','class','quantization','size_class','tier',
         'purpose','engine','parameters_millions','vram_gib_min',
         'context_window_tokens','runtime_profile_bindings',
         'master_spec_section','operator_note','status','license'):
    assert k in m, f'missing key {k}'
assert m['id'] == '${SLUG}', m
assert m['class'] == 'ternary-lm', m
assert m['quantization'] == 'ternary-1.58bit', m
assert isinstance(d['variants'], list)
assert isinstance(d['lora_adapters'], list)
assert 'pull' in d['actions']
assert d['actions']['pull'].endswith('${SLUG}')
" \
  && ok "JSON shape: round + model + variants + lora_adapters + actions" \
  || ko "JSON shape wrong"

# ---- hf_repo_id fragment match resolves the slug ----
out="$("${PYTHON3}" "${SCRIPT}" "bitnet-b1.58-2b" --json)"
echo "${out}" | "${PYTHON3}" -c "
import json,sys
d=json.load(sys.stdin)
# Fragment matches the verified-real entry.
assert d['model']['id'] == '${SLUG}', d['model']
" \
  && ok "hf_repo_id substring resolves to canonical id" \
  || ko "fragment resolve wrong"

# ---- variants surfaced when purpose tags overlap ----
echo "${json}" | "${PYTHON3}" -c "
import json,sys
d=json.load(sys.stdin)
v=d['variants']
assert len(v) >= 1, v
for x in v:
    assert x['shared_purpose'], x
" \
  && ok "variants list non-empty + each shares ≥1 purpose tag" \
  || ko "variants empty / missing shared_purpose"

# ---- unknown slug → rc=2 with operator-readable hint ----
set +e
out_bad="$("${PYTHON3}" "${SCRIPT}" definitely-not-a-real-slug-xxx 2>&1)"
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "unknown slug → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"
echo "${out_bad}" | grep -q "first 10 known ids" \
  && ok "error lists known slugs as a hint" \
  || ko "no operator hint on unknown slug"

# ---- osctl bridge: human ----
set +e
"${OSCTL}" models info "${SLUG}" > /tmp/r231-osctl.out 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl models info <slug> rc=0" \
  || ko "osctl bridge rc=${rc}: $(cat /tmp/r231-osctl.out)"
grep -q "R231 sovereign-os models info" /tmp/r231-osctl.out \
  && ok "osctl bridge surfaces R231 banner" \
  || ko "osctl HTML/banner missing"

# ---- osctl bridge: JSON ----
set +e
"${OSCTL}" models info "${SLUG}" --json > /tmp/r231-osctl.json 2>&1
rc=$?
set -e
"${PYTHON3}" -c "
import json
d=json.load(open('/tmp/r231-osctl.json'))
assert d['round']=='R231', d
assert d['model']['id']=='${SLUG}', d
" \
  && ok "osctl bridge surfaces R231 JSON" \
  || ko "osctl JSON wrong"

# ---- catalog override path works ----
TMP="$(mktemp -t r231-cat.XXXXXX.yaml)"
trap 'rm -f "${TMP}" /tmp/r231-osctl.out /tmp/r231-osctl.json' EXIT
cat > "${TMP}" <<'YAML'
schema_version: "1.0.0"
catalog:
  version: "test"
  models:
    - id: tiny-test
      hf_repo_id: nobody/tiny-test
      class: llm
      quantization: fp16
      size_class: xs
      tier: pulse
      purpose: [chat]
      engine: vllm
      parameters_millions: 1.0
      vram_gib_min: 0.5
      context_window_tokens: 1024
      status: verified-real
      license: mit
      runtime_profile_bindings: []
YAML
out="$("${PYTHON3}" "${SCRIPT}" tiny-test --catalog "${TMP}" --json)"
echo "${out}" | "${PYTHON3}" -c "
import json,sys
d=json.load(sys.stdin)
assert d['model']['id']=='tiny-test', d
assert d['variants']==[], d
" \
  && ok "--catalog override loads alternate file" \
  || ko "catalog override wrong"

echo
total=$((pass + fail))
echo "test_models_info: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
