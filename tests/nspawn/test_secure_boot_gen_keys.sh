#!/usr/bin/env bash
# tests/nspawn/test_secure_boot_gen_keys.sh
#
# Layer 3 test for sovereign-osctl secure-boot (R143; F-05 MED closure).
# Verifies key triple generation + in-repo refusal gate + status verb.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_secure_boot_gen_keys.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

# ---------- gate: --out under repo root REFUSED ----------
set +e
out="$("${OSCTL}" secure-boot gen-keys --out "${__REPO_ROOT}/secret-keys" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "HARD REFUSAL" <<< "${out}" \
                     && grep -q "under the sovereign-os repo root" <<< "${out}"; then
  ok "--out under repo root → HARD REFUSAL exit 1"
else
  ko "in-repo refusal gate broken (rc=${rc})"
fi
if [ ! -d "${__REPO_ROOT}/secret-keys" ]; then
  ok "no key dir created when refused"
else
  ko "key dir created despite refusal"
  rm -rf "${__REPO_ROOT}/secret-keys"
fi

# ---------- gate: --out required ----------
set +e
out="$("${OSCTL}" secure-boot gen-keys 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "usage:" <<< "${out}"; then
  ok "no --out → exit 2 + usage"
else
  ko "no-out gate broken (rc=${rc})"
fi

# ---------- happy path: outside repo ----------
out_dir="${tmp}/sb-keys"
set +e
out="$("${OSCTL}" secure-boot gen-keys --out "${out_dir}" --cn test-suite-host 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "gen-keys outside repo → exit 0"
else
  ko "gen-keys broken (rc=${rc}): ${out:0:200}"
fi

# All 3 key types created (.key + .crt + .cer)
for k in PK KEK db; do
  for ext in key crt cer; do
    if [ -f "${out_dir}/${k}.${ext}" ]; then
      ok "${k}.${ext} present"
    else
      ko "${k}.${ext} MISSING"
    fi
  done
done

# .key files have 0600 perms (private)
for k in PK KEK db; do
  mode="$(stat -c '%a' "${out_dir}/${k}.key" 2>/dev/null)"
  if [ "${mode}" = "600" ]; then
    ok "${k}.key mode is 0600 (private)"
  else
    ko "${k}.key wrong mode: ${mode}"
  fi
done

# README explains the contract
if [ -f "${out_dir}/README.md" ]; then
  ok "README.md generated"
  if grep -q "SDD-015" "${out_dir}/README.md" \
     && grep -q "Back these files up" "${out_dir}/README.md" \
     && grep -q "efi-updatevar" "${out_dir}/README.md"; then
    ok "README contains SDD-015 reference + backup contract + enrollment commands"
  else
    ko "README content incomplete"
  fi
else
  ko "README.md missing"
fi

# Output emphasizes backup
if grep -q "BACK THESE UP NOW" <<< "${out}"; then
  ok "stdout includes BACK THESE UP NOW warning"
else
  ko "backup warning missing"
fi

# CN ended up in the certificate Subject
if openssl x509 -in "${out_dir}/PK.crt" -noout -subject 2>/dev/null | grep -q "test-suite-host"; then
  ok "PK.crt Subject reflects --cn"
else
  ko "PK.crt subject doesn't reflect --cn"
fi

# ---------- status subverb ----------
set +e
out="$("${OSCTL}" secure-boot status 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "secure-boot status:" <<< "${out}"; then
  ok "status → exit 0 + header"
else
  ko "status broken (rc=${rc})"
fi
if grep -q "UEFI:" <<< "${out}" && grep -q "SecureBoot:" <<< "${out}" && grep -q "MOK:" <<< "${out}"; then
  ok "status emits UEFI + SecureBoot + MOK lines"
else
  ko "status fields missing"
fi

# ---------- unknown subverb ----------
set +e
out="$("${OSCTL}" secure-boot bogus 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown secure-boot subcommand" <<< "${out}"; then
  ok "unknown subverb → exit 2"
else
  ko "unknown-subverb gate broken (rc=${rc})"
fi

# ---------- help mentions ----------
help_out="$("${OSCTL}" help 2>&1)"
for kw in "secure-boot gen-keys" "secure-boot status"; do
  if grep -q "${kw}" <<< "${help_out}"; then
    ok "help documents: ${kw}"
  else
    ko "help missing: ${kw}"
  fi
done

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_secure_boot_gen_keys: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
