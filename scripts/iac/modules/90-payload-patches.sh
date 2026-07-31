#!/usr/bin/env bash
# deployed-payload patches — carry committed fixes until a new package ships
# gate: IAC_ENABLE_PAYLOAD_PATCHES
#
# THE PROBLEM THIS SOLVES
#   The runtime reads /opt/sovereign-os — the dpkg payload — not the git
#   checkout. So a fix committed to the repo is inert on this machine until a
#   new sovereign-os-cockpit package is built and installed. Three real fixes
#   are currently in that state, each one a bug that actively misbehaves here.
#
#   This module copies those specific files from the checkout into the payload,
#   idempotently, and only those files. It is not a general sync: a blanket
#   rsync would silently ship every uncommitted experiment into the runtime.
#
# YES, THIS EDITS PACKAGE-OWNED FILES
#   Deliberately, and it is the same bargain module 30 already makes with the
#   profile: `apt upgrade` will revert these, and converge puts them back.
#   `dpkg --verify sovereign-os-cockpit` will list them as modified — that is
#   expected and is the honest signal that the payload is ahead of the package.
#   Each entry names the commit that fixed it, so this list can be emptied as
#   soon as a package carrying those commits is installed.
#
# shellcheck shell=bash

_src="${IAC_SOURCE_RESOLVED_DIR:-${IAC_SOURCE_DIR:-}}"
if [ -z "${_src}" ] || [ ! -d "${_src}/.git" ]; then
  skip "no source checkout — module 15 must succeed first"
  return 0 2>/dev/null || exit 0
fi
_dst=/opt/sovereign-os

# repo-relative path : why it must be live now
#
# scripts/lib/ms003.py                              (commit 74113bc0)
#   sweep() treats "every dict carrying a signature key" as a ledger record, so
#   the BPE vocabulary in models/smollm-135m/tokenizer.json ("signature": 30181)
#   was classified invalid-signature and raised
#       MS003 INTEGRITY FAILURE: invalid=1
#   Until this lands, sovereign-ms003-verify.service fails daily and holds the
#   whole system 'degraded' over a tamper alarm that is not real.
#
# scripts/sovereign-osctl                           (commit d6970b59)
#   `open-computer install` / `openclaw install` ran `systemctl start` on a
#   ConditionFirstBoot=yes unit. systemd SKIPS those after first boot and a
#   skipped unit reports SUCCESS — so the command its own status output tells
#   operators to run has been a silent no-op on every established system.
#
# scripts/hooks/post-install/open-computer-install.sh   (commit 7e0ff05a)
#   The ~3GB base image extracted even when its sha256 sidecar failed to
#   download, so a truncated image would install silently. Fails closed now.
_files="
scripts/lib/ms003.py
scripts/sovereign-osctl
scripts/hooks/post-install/open-computer-install.sh
"

_patched=0
while read -r rel; do
  [ -n "${rel}" ] || continue
  _a="${_src}/${rel}"
  _b="${_dst}/${rel}"

  if [ ! -f "${_a}" ]; then
    skip "not in checkout: ${rel}"
    continue
  fi
  if [ ! -f "${_b}" ]; then
    skip "not in payload: ${rel}"
    continue
  fi
  if cmp -s "${_a}" "${_b}"; then
    ok "payload current: ${rel}"
    continue
  fi
  if [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "payload ← checkout: ${rel}"
    _patched=1
    continue
  fi
  # Preserve the packaged original once, so the pre-patch state is recoverable
  # without reinstalling the package.
  [ -f "${_b}.dpkg-orig" ] || cp -a "${_b}" "${_b}.dpkg-orig" 2>/dev/null || true
  if install -m "$(stat -c '%a' "${_b}")" "${_a}" "${_b}" 2>/dev/null; then
    changed "payload ← checkout: ${rel}"
    _patched=1
  else
    fail "could not install ${rel} into the payload"
  fi
done <<< "${_files}"

# ms003-verify is a timer-driven oneshot: once the fix is live, clear the stale
# failure so `systemctl is-system-running` stops reporting degraded over it.
if [ "${_patched}" = 1 ] && [ "${IAC_DRY_RUN}" != 1 ]; then
  if systemctl is-failed --quiet sovereign-ms003-verify.service 2>/dev/null; then
    if run "verify-ms003" systemctl start sovereign-ms003-verify.service; then
      changed "re-ran sovereign-ms003-verify with the patched ms003.py"
    else
      # Still failing means a REAL integrity finding, not the tokenizer
      # false positive — leave it failed and say so.
      fail "sovereign-ms003-verify still fails after the patch — investigate: journalctl -u sovereign-ms003-verify"
    fi
  fi
fi
