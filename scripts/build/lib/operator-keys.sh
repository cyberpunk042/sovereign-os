#!/usr/bin/env bash
# scripts/build/lib/operator-keys.sh — resolve (and, when absent, MINT) the
# operator-owned secure-boot signing key.
#
# WHY THIS EXISTS (2026-07-25 operator-reported failure): the build died at
# step 05 — AFTER the 30+ minute kernel compile — with "profile posture
# secure_boot=signed needs operator keys". Three surfaces disagreed:
#
#   • 05-substrate-prepare (mkosi-emit) DISCOVERS keys at the SDD-015 default
#     path /etc/sovereign-os/keys/mok.{key,crt} and hard-fails if absent
#   • 08-image-sign DISCOVERS the same path and hard-fails if absent
#   • preflight-tpm told the operator "MOK key+cert unset — step 08 will
#     auto-generate", which was FALSE: no step ever generated anything, and
#     05 fails long before 08 would run anyway
#
# So the documented happy path could not complete: every consumer read the
# default location, no producer ever wrote it, and the operator was told to
# hand-run openssl. This library is that missing producer, shared by every
# consumer so they can never drift apart again.
#
# SDD-015 posture is preserved: the key is operator-owned, generated OUTSIDE
# the repo at /etc/sovereign-os/keys, 0600, never committed, never escrowed.
# Auto-minting matches what preflight already promised the operator.
#
# Contract locked by tests/lint/test_operator_signing_key_contract.py.

# Guard against double-sourcing (05 sources it, then 08 does too).
[ -n "${__SOVEREIGN_OS_OPERATOR_KEYS_SH:-}" ] && return 0
__SOVEREIGN_OS_OPERATOR_KEYS_SH=1

# The SDD-015 documented default location. Overridable for tests.
SOVEREIGN_OS_KEY_DIR="${SOVEREIGN_OS_KEY_DIR:-/etc/sovereign-os/keys}"

# operator_keys_resolved — 0 when a usable key+cert pair is already in the env.
operator_keys_resolved() {
  { [ -n "${SOVEREIGN_OS_PK_KEY:-}" ] && [ -n "${SOVEREIGN_OS_PK_CERT:-}" ]; } ||
  { [ -n "${SOVEREIGN_OS_MOK_KEY:-}" ] && [ -n "${SOVEREIGN_OS_MOK_CERT:-}" ]; }
}

# ensure_operator_keys [<posture>] — make a signing key available, minting one
# on first use. Exports SOVEREIGN_OS_MOK_KEY/_CERT when it resolves or mints.
#
#   0  keys available (env override, discovered on disk, or freshly minted)
#      — or the posture needs none, in which case nothing is touched
#   1  keys needed but unavailable AND un-mintable (not root / no openssl);
#      the caller reports the posture-specific error
#
# Idempotent: an existing pair is reused, never regenerated — regenerating
# would silently invalidate a cert the operator already enrolled in firmware.
ensure_operator_keys() {
  local posture="${1:-signed}"

  case "${posture}" in
    none|disabled) return 0 ;;
  esac

  # 1. explicit env override always wins (operator pointed at their own chain)
  if operator_keys_resolved; then
    return 0
  fi

  # 2. discover the documented default location
  local key="${SOVEREIGN_OS_KEY_DIR}/mok.key"
  local crt="${SOVEREIGN_OS_KEY_DIR}/mok.crt"
  if [ -f "${key}" ] && [ -f "${crt}" ]; then
    export SOVEREIGN_OS_MOK_KEY="${key}" SOVEREIGN_OS_MOK_CERT="${crt}"
    operator_keys_log "using operator MOK at ${SOVEREIGN_OS_KEY_DIR} (SDD-015 default location)"
    return 0
  fi

  # 3. mint. Needs root (writes under /etc) + openssl.
  if [ "$(id -u)" -ne 0 ]; then
    operator_keys_log "cannot mint operator keys: not root (need write access to ${SOVEREIGN_OS_KEY_DIR})"
    return 1
  fi
  if ! command -v openssl >/dev/null 2>&1; then
    operator_keys_log "cannot mint operator keys: openssl not installed"
    return 1
  fi

  operator_keys_log "no operator signing key at ${SOVEREIGN_OS_KEY_DIR} — minting one (4096-bit RSA, 10-year)"
  operator_keys_log "  SDD-015: this key is YOURS. Back it up; sovereign-os keeps no copy and no recovery path."
  mkdir -p "${SOVEREIGN_OS_KEY_DIR}"
  chmod 0700 "${SOVEREIGN_OS_KEY_DIR}"
  # umask so the key is never briefly world-readable between create and chmod.
  local prior_umask; prior_umask="$(umask)"
  umask 077
  if ! openssl req -new -x509 -newkey rsa:4096 -nodes -days 3650 \
        -subj "/CN=sovereign-os operator MOK $(hostname -s 2>/dev/null || echo host)/" \
        -keyout "${key}" -out "${crt}" >/dev/null 2>&1; then
    umask "${prior_umask}"
    rm -f "${key}" "${crt}"
    operator_keys_log "openssl failed to generate the operator key"
    return 1
  fi
  umask "${prior_umask}"
  chmod 0600 "${key}"
  chmod 0644 "${crt}"

  export SOVEREIGN_OS_MOK_KEY="${key}" SOVEREIGN_OS_MOK_CERT="${crt}"
  operator_keys_log "minted ${key} + ${crt}"
  operator_keys_log "  enroll the cert post-install:  sudo mokutil --import ${crt}"
  return 0
}

# Log through the build logger when a step sourced logging.sh; plain stderr
# otherwise (preflight hooks and tests source this standalone).
operator_keys_log() {
  if command -v log_info >/dev/null 2>&1; then
    log_info "$*"
  else
    printf 'operator-keys: %s\n' "$*" >&2
  fi
}
