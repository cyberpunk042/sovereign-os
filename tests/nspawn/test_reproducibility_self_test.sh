#!/usr/bin/env bash
# tests/nspawn/test_reproducibility_self_test.sh
#
# Layer 3 reproducibility self-test. Closes the SDD-019 'CI
# reproducibility self-test' gap by gating that the substrate adapter
# emits byte-identical output when given identical inputs.
#
# Asserts:
#   - mkosi-emit run TWICE with same profile + SOURCE_DATE_EPOCH +
#     DEBIAN_SNAPSHOT → byte-identical mkosi.conf across runs
#   - live-build-emit run twice → byte-identical config tree
#   - changing SOURCE_DATE_EPOCH → at-least-one file changes
#     (proves the input flows through, not silent-ignored)
#   - changing DEBIAN_SNAPSHOT → at-least-one file changes

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_reproducibility_self_test.sh"
echo

PROFILE="${1:-sain-01}"
profile_file="${__REPO_ROOT}/profiles/${PROFILE}.yaml"
[ -f "${profile_file}" ] || { echo "FAIL: profile missing"; exit 1; }

mkosi_emit="${__REPO_ROOT}/scripts/build/adapters/mkosi-emit.sh"
lb_emit="${__REPO_ROOT}/scripts/build/adapters/live-build-emit.sh"

# The profile's secure_boot=signed posture makes mkosi-emit require operator
# key env vars (SDD-015: real keys are NEVER in the repo/CI). Placeholder
# files satisfy the presence gate — the adapter embeds only the key *paths*,
# and every invocation below uses the SAME path, so the reproducibility hash
# comparisons are unaffected. Same pattern as test_image_sign_gates.sh.
__keydir="$(mktemp -d)"
trap 'rm -rf "${__keydir}"' EXIT
export SOVEREIGN_OS_MOK_KEY="${__keydir}/ci-mok.key"
export SOVEREIGN_OS_MOK_CERT="${__keydir}/ci-mok.crt"
touch "${SOVEREIGN_OS_MOK_KEY}" "${SOVEREIGN_OS_MOK_CERT}"

# Hash a directory tree (sorted by relative path; canonical)
hash_tree() {
  (cd "$1" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum) \
    | sha256sum | cut -d' ' -f1
}

# ----------- mkosi-emit reproducibility ---------------

epoch=1700000000
snapshot="20260515T000000Z"

a="$(mktemp -d)"; b="$(mktemp -d)"
SOURCE_DATE_EPOCH=${epoch} DEBIAN_SNAPSHOT=${snapshot} "${mkosi_emit}" "${profile_file}" "${a}" >/dev/null
SOURCE_DATE_EPOCH=${epoch} DEBIAN_SNAPSHOT=${snapshot} "${mkosi_emit}" "${profile_file}" "${b}" >/dev/null

hash_a="$(hash_tree "${a}")"
hash_b="$(hash_tree "${b}")"

if [ "${hash_a}" = "${hash_b}" ]; then
  ok "mkosi-emit: identical env → identical tree hash (${hash_a:0:12}…)"
else
  ko "mkosi-emit: identical env → DIFFERENT hashes (a=${hash_a:0:12} b=${hash_b:0:12})"
  diff -r "${a}" "${b}" 2>&1 | head -10
fi

# ----------- mkosi-emit: SOURCE_DATE_EPOCH change → output changes ---------------

c="$(mktemp -d)"
SOURCE_DATE_EPOCH=$((epoch + 1)) DEBIAN_SNAPSHOT=${snapshot} "${mkosi_emit}" "${profile_file}" "${c}" >/dev/null
hash_c="$(hash_tree "${c}")"
if [ "${hash_a}" != "${hash_c}" ]; then
  ok "mkosi-emit: changing SOURCE_DATE_EPOCH → tree hash changes (input flows through)"
else
  ko "mkosi-emit: SOURCE_DATE_EPOCH change had NO effect — input silently ignored"
fi

# ----------- mkosi-emit: DEBIAN_SNAPSHOT change → output changes ---------------

d="$(mktemp -d)"
SOURCE_DATE_EPOCH=${epoch} DEBIAN_SNAPSHOT="20260601T000000Z" "${mkosi_emit}" "${profile_file}" "${d}" >/dev/null
hash_d="$(hash_tree "${d}")"
if [ "${hash_a}" != "${hash_d}" ]; then
  ok "mkosi-emit: changing DEBIAN_SNAPSHOT → tree hash changes (input flows through)"
else
  ko "mkosi-emit: DEBIAN_SNAPSHOT change had NO effect — input silently ignored"
fi

# ----------- live-build-emit reproducibility ---------------

e="$(mktemp -d)"; f="$(mktemp -d)"
SOURCE_DATE_EPOCH=${epoch} DEBIAN_SNAPSHOT=${snapshot} "${lb_emit}" "${profile_file}" "${e}" >/dev/null
SOURCE_DATE_EPOCH=${epoch} DEBIAN_SNAPSHOT=${snapshot} "${lb_emit}" "${profile_file}" "${f}" >/dev/null

hash_e="$(hash_tree "${e}")"
hash_f="$(hash_tree "${f}")"

if [ "${hash_e}" = "${hash_f}" ]; then
  ok "live-build-emit: identical env → identical tree hash (${hash_e:0:12}…)"
else
  ko "live-build-emit: identical env → DIFFERENT hashes (e=${hash_e:0:12} f=${hash_f:0:12})"
fi

# ----------- baseline: no env-overrides → still reproducible ---------------

g="$(mktemp -d)"; h="$(mktemp -d)"
( unset SOURCE_DATE_EPOCH DEBIAN_SNAPSHOT
  "${mkosi_emit}" "${profile_file}" "${g}" >/dev/null
  "${mkosi_emit}" "${profile_file}" "${h}" >/dev/null
)
hash_g="$(hash_tree "${g}")"
hash_h="$(hash_tree "${h}")"
if [ "${hash_g}" = "${hash_h}" ]; then
  ok "mkosi-emit: baseline (no env overrides) is also reproducible"
else
  ko "mkosi-emit: baseline non-reproducible — env-independent reproducibility broken"
fi

rm -rf "${a}" "${b}" "${c}" "${d}" "${e}" "${f}" "${g}" "${h}"

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_reproducibility_self_test: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
