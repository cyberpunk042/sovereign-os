#!/usr/bin/env bash
# tests/nspawn/test_selfdef_signing_audit.sh
#
# Layer 3 test for R195 — audit module-manifest signing posture
# across the operator's selfdef catalog (cross-repo mirror of
# selfdef SD-R55).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/selfdef-signing-audit.py"

echo "tests/nspawn/test_selfdef_signing_audit.sh"
echo

[ -x "${SCRIPT}" ] && ok "selfdef-signing-audit.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R195" "${SCRIPT}" \
  && ok "carries R195 marker" || ko "R195 marker missing"
grep -q "SD-R55" "${SCRIPT}" \
  && ok "cites selfdef SD-R55 (cross-repo provenance)" \
  || ko "SD-R55 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# Stage 3 modules: unsigned, signed-optional, signed-required.
mkdir -p "${WORK}/m1" "${WORK}/m2" "${WORK}/m3"
cat > "${WORK}/m1/module.toml" <<'TOML'
name = "m1"
version = "0.0.0"
summary = "unsigned baseline"
TOML
cat > "${WORK}/m2/module.toml" <<'TOML'
name = "m2"
version = "0.0.0"
summary = "informational signing"
[signing]
required = false
TOML
cat > "${WORK}/m3/module.toml" <<'TOML'
name = "m3"
version = "0.0.0"
summary = "required signed, .minisig absent"
[signing]
required = true
trust_root = "/etc/selfdef/keys/policy.pub"
TOML

# ---------- human output: counts + per-module markers ----------
set +e
out="$("${SCRIPT}" --dir "${WORK}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "rc=1 on required-missing modules" \
  || ko "expected rc=1 got ${rc}: ${out}"
grep -q "unsigned=1" <<< "${out}" \
  && ok "human: unsigned count correct" || ko "wrong unsigned count"
grep -q "optional=1" <<< "${out}" \
  && ok "human: optional count correct" || ko "wrong optional count"
grep -q "required-missing=1" <<< "${out}" \
  && ok "human: required-missing count correct" || ko "wrong missing count"
grep -q "✗ signed-required-missing.*m3" <<< "${out}" \
  && ok "human: m3 marked with ✗" || ko "m3 marker wrong"

# ---------- JSON shape ----------
set +e
out_json="$("${SCRIPT}" --dir "${WORK}" --json 2>&1)"
set -e
if python3 -c "
import json
d = json.loads('''${out_json}''')
assert d['schema_version'] == '1.0.0'
assert d['total'] == 3
assert d['counts']['signed_required_missing'] == 1
assert d['counts']['no_signing_block'] == 1
assert d['counts']['signed_optional'] == 1
" 2>/dev/null; then
  ok "--json schema + counts correct"
else
  ko "--json shape wrong: ${out_json}"
fi

# ---------- happy path: add a fake .minisig → required-valid ----------
touch "${WORK}/m3/module.toml.minisig"
set +e
"${SCRIPT}" --dir "${WORK}" >/dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "with .minisig present: rc=0 (no missing)" \
  || ko "rc should drop to 0 when .minisig present, got ${rc}"

# ---------- missing dir → rc=2 ----------
set +e
"${SCRIPT}" --dir "${WORK}/no-such" 2>/dev/null
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "missing dir → rc=2" || ko "rc=${rc}"

echo
total=$((pass + fail))
echo "test_selfdef_signing_audit: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
