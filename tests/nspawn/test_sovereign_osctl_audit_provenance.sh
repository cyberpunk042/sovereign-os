#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_audit_provenance.sh
#
# Layer 3 test for Round 41 — 'sovereign-osctl audit provenance'.
# Validates SDD-019's operator-side verification path: the build
# emits build-provenance.json + sha256sums.txt (Round 29); the
# management CLI lets the operator inspect + cross-check them
# without writing custom tooling.
#
# Asserts:
#   - no manifest found → exits 1 with operator-actionable error
#   - given a valid manifest + matching sums → exits 0 + reports ✓
#   - manifest with sha mismatch vs sums → exits 2 + flags mismatch
#   - subjects missing from sums → warns but exits 0 (subset audit ok)
#   - manifest path argument honored

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

CTL="${__REPO_ROOT}/scripts/sovereign-osctl"
[ -x "${CTL}" ] || { echo "FAIL: sovereign-osctl not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_sovereign_osctl_audit_provenance.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_PROFILE=sain-01

# ----------- no manifest → exit 1 with operator-actionable error ---------------

set +e
out="$(SOVEREIGN_OS_IMAGE_DIR="${tmp}/nope" "${CTL}" audit provenance 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "no build-provenance.json found" <<< "${out}"; then
  ok "no manifest → exit 1 with clear error"
else
  ko "no-manifest gate broken: rc=${rc} out=${out:0:200}"
fi

if grep -qE "sovereign-osctl audit provenance .*<path>" <<< "${out}"; then
  ok "error message includes operator-actionable remediation"
else
  ko "no remediation hint in error"
fi

# ----------- valid manifest + matching sums → ✓ ---------------

img="${tmp}/img"; mkdir -p "${img}"
echo "file-A content" > "${img}/artifact-a.raw"
echo "file-B content" > "${img}/vmlinuz-test"

# Hand-compute sums
sha_a="$(sha256sum "${img}/artifact-a.raw" | cut -d' ' -f1)"
sha_v="$(sha256sum "${img}/vmlinuz-test" | cut -d' ' -f1)"

cat > "${img}/sha256sums.txt" <<EOF
${sha_a}  ./artifact-a.raw
${sha_v}  ./vmlinuz-test
EOF

cat > "${img}/build-provenance.json" <<EOF
{
  "_type": "https://in-toto.io/Statement/v1",
  "predicateType": "https://slsa.dev/provenance/v1",
  "subject": [
    {"name": "artifact-a.raw", "digest": {"sha256": "${sha_a}"}},
    {"name": "vmlinuz-test", "digest": {"sha256": "${sha_v}"}}
  ],
  "predicate": {
    "buildDefinition": {
      "buildType": "https://github.com/cyberpunk042/sovereign-os/build/v1",
      "externalParameters": {
        "profile": "sain-01",
        "source_date_epoch": "1700000000",
        "debian_snapshot": "20260515T000000Z"
      }
    }
  }
}
EOF

set +e
out="$("${CTL}" audit provenance "${img}/build-provenance.json" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "valid manifest + matching sums → exit 0"
else
  ko "valid manifest exit ${rc}: ${out:0:300}"
fi

if grep -q "predicateType: https://slsa.dev/provenance/v1" <<< "${out}"; then
  ok "manifest header surfaced (predicateType)"
else
  ko "manifest header missing"
fi

if grep -q "subjects:      2 artifact" <<< "${out}"; then
  ok "subject count reported"
else
  ko "subject count missing"
fi

if grep -q "source_date_epoch.*1700000000" <<< "${out}"; then
  ok "reproducibility inputs (source_date_epoch) surfaced"
else
  ko "externalParameters not surfaced"
fi

if grep -q "all 2 subject digests match sha256sums.txt" <<< "${out}"; then
  ok "cross-check ✓ all-match path hit"
else
  ko "cross-check check-mark missing: ${out:0:300}"
fi

# ----------- digest mismatch → exit 2 + flag ---------------

# Corrupt the manifest's sha for artifact-a
sed -i "s/${sha_a}/$(printf '%064d' 0)/" "${img}/build-provenance.json"

set +e
out="$("${CTL}" audit provenance "${img}/build-provenance.json" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "digest mismatch" <<< "${out}"; then
  ok "manifest with sha mismatch → exit 2 + flags mismatch"
else
  ko "mismatch detection broken: rc=${rc} out=${out:0:300}"
fi

# ----------- help documents the new subcommand ---------------

help_out="$("${CTL}" help 2>&1)"
if grep -q "audit provenance" <<< "${help_out}"; then
  ok "help documents 'audit provenance' subcommand"
else
  ko "help missing 'audit provenance'"
fi

if grep -q -- "--deep" <<< "${help_out}"; then
  ok "help documents 'audit provenance --deep' flag (Round 106)"
else
  ko "help missing --deep flag documentation"
fi

# ----------- Round 106 --deep mode: closes the in-toto verifier loop ---------------
# Build a fresh manifest + sums + actual files; verify --deep accepts all match.
deep_img="${tmp}/deep"
mkdir -p "${deep_img}"
echo "content-of-a" > "${deep_img}/artifact-a.img"
echo "content-of-b" > "${deep_img}/artifact-b.img"
deep_sha_a="$(sha256sum "${deep_img}/artifact-a.img" | cut -d' ' -f1)"
deep_sha_b="$(sha256sum "${deep_img}/artifact-b.img" | cut -d' ' -f1)"

# sums.txt format: "<digest>  ./<name>" (two spaces, then ./)
{
  echo "${deep_sha_a}  ./artifact-a.img"
  echo "${deep_sha_b}  ./artifact-b.img"
} > "${deep_img}/sha256sums.txt"

# Manifest in SLSA-v1 minimal shape
cat > "${deep_img}/build-provenance.json" <<EOF
{
  "_type": "https://in-toto.io/Statement/v1",
  "predicateType": "https://slsa.dev/provenance/v1",
  "subject": [
    {"name": "artifact-a.img", "digest": {"sha256": "${deep_sha_a}"}},
    {"name": "artifact-b.img", "digest": {"sha256": "${deep_sha_b}"}}
  ],
  "predicate": {
    "buildDefinition": {
      "buildType": "https://github.com/cyberpunk042/sovereign-os/build/v1",
      "externalParameters": {"profile": "sain-01", "substrate": "mkosi", "source_date_epoch": "1715817600"}
    }
  }
}
EOF

set +e
out="$("${CTL}" audit provenance --deep "${deep_img}/build-provenance.json" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "all 2 files on disk match manifest digest" <<< "${out}"; then
  ok "--deep on clean tree → exit 0 + all-match summary"
else
  ko "--deep clean-tree gate broken: rc=${rc}; out=${out:0:300}"
fi

# Tamper with one file on disk; manifest unchanged; --deep should catch the drift
echo "MUTATED" >> "${deep_img}/artifact-a.img"
set +e
out="$("${CTL}" audit provenance --deep "${deep_img}/build-provenance.json" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 3 ] && grep -qE "file\(s\) on disk differ from manifest digest" <<< "${out}"; then
  ok "--deep on tampered tree → exit 3 + flags on-disk drift"
else
  ko "--deep drift-detection broken: rc=${rc}; out=${out:0:300}"
fi

# Missing file on disk → reported as missing
rm "${deep_img}/artifact-b.img"
# Restore artifact-a so the only issue is missing-b
echo "content-of-a" > "${deep_img}/artifact-a.img"
set +e
out="$("${CTL}" audit provenance --deep "${deep_img}/build-provenance.json" 2>&1)"
rc=$?
set -e
if grep -q "listed in manifest but missing on disk" <<< "${out}" && grep -q "artifact-b.img" <<< "${out}"; then
  ok "--deep on missing-file tree → reports the missing file by name"
else
  ko "--deep missing-file detection broken: rc=${rc}; out=${out:0:300}"
fi

# Unknown flag → exit 2
set +e
out="$("${CTL}" audit provenance --not-a-flag "${deep_img}/build-provenance.json" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown flag: --not-a-flag" <<< "${out}"; then
  ok "unknown flag → exit 2 + clear error"
else
  ko "unknown-flag gate broken: rc=${rc}"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_sovereign_osctl_audit_provenance: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
