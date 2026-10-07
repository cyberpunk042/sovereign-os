#!/usr/bin/env bash
# upstream git checkout — profiles.provisioning.bake.repo
# gate: IAC_ENABLE_SOURCE_REPO
#
# WHY: profiles.provisioning.bake.repo is true and operator.home_repo names
# "sovereign-os", so the installer was meant to leave a real checkout on the
# box. There is none — `find / -name .git -path '*sovereign*'` returns nothing.
#
# IMPORTANT: /opt/sovereign-os is NOT that checkout and must never be turned
# into one. It is a dpkg-deployed PAYLOAD SUBSET — it has config/ profiles/
# scripts/ share/ systemd/ webapp/ but no README.md, Makefile, Cargo.toml,
# crates/, docs/, schemas/ or tests/. Pointing a git remote at it would make
# every absent path look like a staged deletion, and `git checkout` would then
# fight dpkg over 1135 package-owned files.
#
# The checkout also unblocks the two binaries that are simply missing on this
# install — sovereign-gatewayd and guardian-core live in crates/ and cannot be
# built from the payload alone.
#
# shellcheck shell=bash

_repo_want="$(profile_get provisioning.bake.repo true)"
if [ "${_repo_want}" != "true" ]; then
  skip "provisioning.bake.repo is not true — no checkout requested"
  return 0 2>/dev/null || exit 0
fi

_remote="${IAC_SOURCE_REMOTE:-https://github.com/cyberpunk042/sovereign-os.git}"
_ref="${IAC_SOURCE_REF:-main}"
_owner="${IAC_OPERATOR_USER:-operator}"
_dir="${IAC_SOURCE_DIR:-}"
[ -n "${_dir}" ] || _dir="${IAC_OPERATOR_HOME:-/var/lib/sovereign-os/operator}/${IAC_OPERATOR_HOME_REPO:-sovereign-os}"

iac_info "remote=${_remote}"
iac_info "dir=${_dir} ref=${_ref}"

if ! command -v git >/dev/null 2>&1; then
  fail "git not installed — cannot manage the source checkout"
  return 0 2>/dev/null || exit 0
fi

# ---- guard: never adopt the dpkg payload as a checkout ----
case "${_dir}" in
  /opt/sovereign-os|/opt/sovereign-os/*|/usr/local/lib/sovereign-os|/usr/local/lib/sovereign-os/*)
    fail "refusing to make a git checkout at ${_dir} — that tree is dpkg-owned payload, not the repo"
    return 0 2>/dev/null || exit 0
    ;;
esac

if [ -d "${_dir}/.git" ]; then
  cur="$(git -C "${_dir}" remote get-url origin 2>/dev/null || true)"
  if [ "${cur}" = "${_remote}" ]; then
    ok "checkout ${_dir} (origin correct)"
  else
    iac_info "origin is '${cur:-none}', want '${_remote}'"
    if run "set-url" git -C "${_dir}" remote set-url origin "${_remote}"; then
      changed "checkout ${_dir} origin → ${_remote}"
    else
      # No origin at all → add it rather than fail.
      if run "add-origin" git -C "${_dir}" remote add origin "${_remote}"; then
        changed "checkout ${_dir} origin added"
      else fail "checkout ${_dir} — could not set origin"; fi
    fi
  fi
elif [ -e "${_dir}" ] && [ -n "$(ls -A "${_dir}" 2>/dev/null)" ]; then
  # Non-empty and not a repo. Cloning would clobber; converge never destroys.
  fail "${_dir} exists, is non-empty, and is not a git repo — refusing to clone over it"
else
  if [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "clone ${_remote} → ${_dir}"
  else
    install -d -o "${_owner}" -g "${_owner}" "$(dirname "${_dir}")" 2>/dev/null || true
    if sudo -u "${_owner}" git clone --branch "${_ref}" "${_remote}" "${_dir}" >/dev/null 2>&1 \
       || git clone --branch "${_ref}" "${_remote}" "${_dir}" >/dev/null 2>&1; then
      chown -R "${_owner}:${_owner}" "${_dir}" 2>/dev/null || true
      changed "cloned ${_remote} → ${_dir}"
    else
      # Offline or private repo — a normal condition on an air-gapped box.
      fail "clone failed (network or credentials) — ${_remote}"
    fi
  fi
fi

# Record where the source lives so operators and later modules agree.
if [ -d "${_dir}/.git" ] || [ "${IAC_DRY_RUN}" = 1 ]; then
  ensure_file /etc/sovereign-os/source-checkout.env 0644 root:root <<EOF
# Written by scripts/iac/modules/15-source-repo.sh — do not edit by hand.
# The upstream checkout. /opt/sovereign-os is dpkg payload, NOT this.
SOVEREIGN_OS_SOURCE_DIR=${_dir}
SOVEREIGN_OS_SOURCE_REMOTE=${_remote}
SOVEREIGN_OS_SOURCE_REF=${_ref}
EOF
fi

export IAC_SOURCE_RESOLVED_DIR="${_dir}"
