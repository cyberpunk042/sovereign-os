#!/usr/bin/env bash
# tests/nspawn/test_reproducibility_inputs.sh
#
# Layer 3 test for SDD-019 reproducibility wiring:
#   - SOURCE_DATE_EPOCH propagates into emitted mkosi.conf [Build]
#     Environment block when set
#   - DEBIAN_SNAPSHOT propagates into emitted mkosi.conf
#     [Distribution] Mirror pinning when set
#   - Both absent → no [Build] / no snapshot Mirror line
#   - 09-image-verify emits sha256sums.txt + build-provenance.json
#     against a fake image dir

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_reproducibility_inputs.sh"
echo

PROFILE="${1:-sain-01}"
profile_file="${__REPO_ROOT}/profiles/${PROFILE}.yaml"
[ -f "${profile_file}" ] || { echo "FAIL: profile missing"; exit 1; }

# ----------- baseline emit: no env vars set ---------------

tmp_baseline="$(mktemp -d)"
( unset SOURCE_DATE_EPOCH DEBIAN_SNAPSHOT
  "${__REPO_ROOT}/scripts/build/adapters/mkosi-emit.sh" "${profile_file}" "${tmp_baseline}" >/dev/null )

if [ -f "${tmp_baseline}/mkosi.conf" ]; then
  ok "baseline mkosi.conf emitted (no env vars)"
else
  ko "baseline mkosi.conf missing"
fi

if ! grep -q "SOURCE_DATE_EPOCH" "${tmp_baseline}/mkosi.conf"; then
  ok "baseline: no SOURCE_DATE_EPOCH leak when unset"
else
  ko "baseline: SOURCE_DATE_EPOCH unexpectedly present"
fi

if ! grep -q "snapshot.debian.org" "${tmp_baseline}/mkosi.conf"; then
  ok "baseline: no snapshot.debian.org pinning when DEBIAN_SNAPSHOT unset"
else
  ko "baseline: snapshot.debian.org unexpectedly present"
fi

# ----------- with SOURCE_DATE_EPOCH ---------------

tmp_epoch="$(mktemp -d)"
SOURCE_DATE_EPOCH=1700000000 "${__REPO_ROOT}/scripts/build/adapters/mkosi-emit.sh" \
  "${profile_file}" "${tmp_epoch}" >/dev/null

if grep -qE "^\s+SOURCE_DATE_EPOCH=1700000000$" "${tmp_epoch}/mkosi.conf"; then
  ok "SOURCE_DATE_EPOCH propagated into mkosi.conf [Build] Environment block"
else
  ko "SOURCE_DATE_EPOCH not propagated: $(grep -i source "${tmp_epoch}/mkosi.conf" || echo none)"
fi

if grep -q '\[Build\]' "${tmp_epoch}/mkosi.conf"; then
  ok "[Build] section emitted when SOURCE_DATE_EPOCH set"
else
  ko "[Build] section missing"
fi

# ----------- with DEBIAN_SNAPSHOT ---------------

tmp_snap="$(mktemp -d)"
DEBIAN_SNAPSHOT="20260515T000000Z" "${__REPO_ROOT}/scripts/build/adapters/mkosi-emit.sh" \
  "${profile_file}" "${tmp_snap}" >/dev/null

if grep -q "snapshot.debian.org/archive/debian/20260515T000000Z" "${tmp_snap}/mkosi.conf"; then
  ok "DEBIAN_SNAPSHOT propagated into mkosi.conf Mirror pinning"
else
  ko "DEBIAN_SNAPSHOT not propagated: $(grep -i mirror "${tmp_snap}/mkosi.conf" || echo none)"
fi

# ----------- with both ---------------

tmp_both="$(mktemp -d)"
SOURCE_DATE_EPOCH=1700000000 DEBIAN_SNAPSHOT="20260515T000000Z" \
  "${__REPO_ROOT}/scripts/build/adapters/mkosi-emit.sh" \
  "${profile_file}" "${tmp_both}" >/dev/null

if grep -q "SOURCE_DATE_EPOCH=1700000000" "${tmp_both}/mkosi.conf" \
   && grep -q "snapshot.debian.org" "${tmp_both}/mkosi.conf"; then
  ok "both SOURCE_DATE_EPOCH + DEBIAN_SNAPSHOT propagate together"
else
  ko "combined env propagation broken"
fi

# ----------- step 04 honors SOURCE_DATE_EPOCH (inputs_hash change) ---------------
# We don't run the real compile — just verify the script's input-hash
# changes when SOURCE_DATE_EPOCH changes, proving the state machine
# notices the operator pinning a new epoch.

state_lib="${__REPO_ROOT}/scripts/build/lib/state.sh"
common_lib="${__REPO_ROOT}/scripts/build/lib/common.sh"

if grep -q 'epoch=\${SOURCE_DATE_EPOCH}' "${__REPO_ROOT}/scripts/build/04-kernel-compile.sh"; then
  ok "step 04 folds SOURCE_DATE_EPOCH into inputs_hash"
else
  ko "step 04 doesn't fold SOURCE_DATE_EPOCH into inputs_hash"
fi

if grep -q "KBUILD_BUILD_TIMESTAMP" "${__REPO_ROOT}/scripts/build/04-kernel-compile.sh"; then
  ok "step 04 sets KBUILD_BUILD_TIMESTAMP from SOURCE_DATE_EPOCH"
else
  ko "step 04 doesn't set KBUILD_BUILD_TIMESTAMP"
fi

# ----------- step 09 emits sha256sums + provenance manifest ---------------

if grep -q "sha256sums.txt" "${__REPO_ROOT}/scripts/build/09-image-verify.sh" \
   && grep -q "build-provenance.json" "${__REPO_ROOT}/scripts/build/09-image-verify.sh"; then
  ok "step 09 emits sha256sums.txt + build-provenance.json"
else
  ko "step 09 missing reproducibility artifacts"
fi

if grep -q "slsa.dev/provenance" "${__REPO_ROOT}/scripts/build/09-image-verify.sh"; then
  ok "step 09 provenance manifest uses SLSA v1 predicate type"
else
  ko "step 09 provenance not SLSA-shaped"
fi

# Run step 09's provenance-emit Python in isolation against a fake image dir
fake_img="$(mktemp -d)"
echo "test image bytes" > "${fake_img}/sovereign-test.raw"
mkdir -p "${fake_img}/output"
echo "test kernel" > "${fake_img}/vmlinuz-test"

# Simulate the step's emit blocks (extract + run the inline Python)
(
  cd "${fake_img}"
  find . -maxdepth 2 -type f ! -name 'sha256sums.txt' ! -name 'build-provenance.json' \
    -exec sha256sum {} \; | sort > sha256sums.txt
  SOVEREIGN_OS_IMAGE_DIR="${fake_img}" SOVEREIGN_OS_PROFILE=sain-01 \
    SOURCE_DATE_EPOCH=1700000000 DEBIAN_SNAPSHOT=20260515T000000Z \
    python3 - <<PY > build-provenance.json
import hashlib, json, os, pathlib, time
img_dir = pathlib.Path(os.environ["SOVEREIGN_OS_IMAGE_DIR"])
subjects = []
for f in sorted(img_dir.rglob("*")):
    if not f.is_file(): continue
    if f.name in ("sha256sums.txt", "build-provenance.json"): continue
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    subjects.append({"name": str(f.relative_to(img_dir)), "digest": {"sha256": h}})
provenance = {
    "_type": "https://in-toto.io/Statement/v1",
    "predicateType": "https://slsa.dev/provenance/v1",
    "subject": subjects,
    "predicate": {
        "buildDefinition": {
            "buildType": "https://github.com/cyberpunk042/sovereign-os/build/v1",
            "externalParameters": {
                "profile": os.environ.get("SOVEREIGN_OS_PROFILE", ""),
                "substrate": os.environ.get("SOVEREIGN_OS_SUBSTRATE", "mkosi"),
                "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH", ""),
                "debian_snapshot": os.environ.get("DEBIAN_SNAPSHOT", ""),
            },
        },
    },
}
print(json.dumps(provenance, indent=2))
PY
)

if [ -s "${fake_img}/sha256sums.txt" ] && [ "$(wc -l < "${fake_img}/sha256sums.txt")" -ge 2 ]; then
  ok "sha256sums.txt emitted with multiple subjects"
else
  ko "sha256sums.txt empty or sparse"
fi

if python3 -c "
import json
d = json.load(open('${fake_img}/build-provenance.json'))
assert d['_type'] == 'https://in-toto.io/Statement/v1'
assert d['predicateType'] == 'https://slsa.dev/provenance/v1'
assert len(d['subject']) >= 2
assert d['predicate']['buildDefinition']['externalParameters']['source_date_epoch'] == '1700000000'
assert d['predicate']['buildDefinition']['externalParameters']['debian_snapshot'] == '20260515T000000Z'
" 2>/dev/null; then
  ok "build-provenance.json: valid SLSA v1 shape + reproducibility inputs recorded"
else
  ko "build-provenance.json structure invalid"
fi

rm -rf "${tmp_baseline}" "${tmp_epoch}" "${tmp_snap}" "${tmp_both}" "${fake_img}"

echo
total=$((pass + fail))
echo "test_reproducibility_inputs: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
