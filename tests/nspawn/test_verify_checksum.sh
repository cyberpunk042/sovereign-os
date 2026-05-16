#!/usr/bin/env bash
# tests/nspawn/test_verify_checksum.sh
#
# Layer 3 test for R190 — scripts/models/verify-checksum.py verifies
# a model artifact's sha256 against its manifest declaration.
# Partial closure of SDD-019 T-3 (full models-fetch deferred to
# cycle 3).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/models/verify-checksum.py"

echo "tests/nspawn/test_verify_checksum.sh"
echo

[ -x "${SCRIPT}" ] && ok "verify-checksum.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R190" "${SCRIPT}" \
  && ok "script carries R190 marker" || ko "R190 marker missing"
grep -q "SDD-019 T-3" "${SCRIPT}" \
  && ok "cites SDD-019 T-3 (provenance)" || ko "T-3 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# Stage an artifact + manifest with matching sha256.
echo "test artifact content" > "${WORK}/model.gguf"
EXPECTED="$(sha256sum "${WORK}/model.gguf" | awk '{print $1}')"
cat > "${WORK}/model.toml" <<EOF
[model]
name = "test-model"
weight_format = "ternary"
artifact_sha256 = "${EXPECTED}"
EOF

# ---------- happy path: digest matches → rc=0 ----------
set +e
out="$(python3 "${SCRIPT}" \
  --manifest "${WORK}/model.toml" \
  --artifact "${WORK}/model.gguf" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "matching digest → rc=0" || ko "rc=${rc}: ${out}"
grep -q "✓" <<< "${out}" && ok "human output: green checkmark" \
  || ko "no checkmark: ${out}"
grep -q "(match)" <<< "${out}" && ok "human output: '(match)' label" \
  || ko "no match label"

# ---------- mismatch: artifact mutated → rc=1 ----------
echo "tampered content" > "${WORK}/model.gguf"
set +e
out="$(python3 "${SCRIPT}" \
  --manifest "${WORK}/model.toml" \
  --artifact "${WORK}/model.gguf" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "mismatch digest → rc=1" || ko "rc=${rc}"
grep -q "MISMATCH" <<< "${out}" \
  && ok "human output: MISMATCH label cited" || ko "no MISMATCH"

# ---------- manifest without artifact_sha256 → rc=2 ----------
cat > "${WORK}/model-noverify.toml" <<'EOF'
[model]
name = "test-no-sha"
EOF
set +e
python3 "${SCRIPT}" \
  --manifest "${WORK}/model-noverify.toml" \
  --artifact "${WORK}/model.gguf" --quiet 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "missing artifact_sha256 → rc=2" || ko "rc=${rc}"

# ---------- manifest missing → rc=3 ----------
set +e
python3 "${SCRIPT}" \
  --manifest "${WORK}/no-such.toml" \
  --artifact "${WORK}/model.gguf" --quiet 2>&1
rc=$?
set -e
[ "${rc}" -eq 3 ] && ok "missing manifest → rc=3" || ko "rc=${rc}"

# ---------- artifact missing → rc=3 ----------
set +e
python3 "${SCRIPT}" \
  --manifest "${WORK}/model.toml" \
  --artifact "${WORK}/no-such-file.gguf" --quiet 2>&1
rc=$?
set -e
[ "${rc}" -eq 3 ] && ok "missing artifact → rc=3" || ko "rc=${rc}"

# ---------- --quiet suppresses output ----------
echo "test artifact content" > "${WORK}/model.gguf"
set +e
out_q="$(python3 "${SCRIPT}" \
  --manifest "${WORK}/model.toml" \
  --artifact "${WORK}/model.gguf" --quiet 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && [ -z "${out_q}" ] \
  && ok "--quiet on match: no output, rc=0" \
  || ko "--quiet failed: rc=${rc} out=${out_q}"

# ---------- works on a large-ish artifact (streaming, not in-memory) ----------
dd if=/dev/urandom of="${WORK}/large.bin" bs=1M count=4 2>/dev/null
LARGE_SHA="$(sha256sum "${WORK}/large.bin" | awk '{print $1}')"
cat > "${WORK}/large.toml" <<EOF
[model]
name = "large-test"
artifact_sha256 = "${LARGE_SHA}"
EOF
set +e
python3 "${SCRIPT}" \
  --manifest "${WORK}/large.toml" \
  --artifact "${WORK}/large.bin" --quiet 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "verifies 4 MiB artifact via streaming read" \
  || ko "large artifact rc=${rc}"

echo
total=$((pass + fail))
echo "test_verify_checksum: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
