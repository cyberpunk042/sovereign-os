#!/usr/bin/env bash
# deployed-payload patches — carry committed fixes until a new package ships
# gate: IAC_ENABLE_PAYLOAD_PATCHES
#
# THE PROBLEM THIS SOLVES
#   The runtime reads /opt/sovereign-os — the dpkg payload — not the git
#   checkout. So a fix committed to the repo is inert on this machine until a
#   new sovereign-os-cockpit package is built and installed. Six real fixes
#   are currently in that state, each one a bug that actively misbehaves here.
#
#   There is a second, distinct gap: files the package never shipped AT ALL, so
#   there is nothing to patch. Those are handled by _add_files near the bottom.
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
#
# scripts/intelligence/fetch-model.sh               (commit 99926459)
#   Fetched only config.json + tokenizer.json + model.safetensors, omitting
#   tokenizer_config.json — which is where chat_template and eos_token live, and
#   which sovereign-gatewayd reads straight out of the model dir (lib.rs:1312).
#   Without it an instruction-tuned model never sees the markers it was trained
#   on, never emits its end-of-turn token, and runs past its own answer.
#
# scripts/hooks/recurrent/root-modules-verify.sh    (commit f4658e3e)
# scripts/hooks/recurrent/selfdef-sync.sh           (commit f4658e3e)
#   Both default a checkout path to ${HOME}/… under `set -u`, but systemd starts
#   a root service with NO HOME (it only sets it when User= is given, and neither
#   unit does). Both died with "HOME: unbound variable" on every scheduled fire —
#   weekly, silently — ~30 lines above the absent-checkout handling each was
#   deliberately written to have. Found by test-firing the timers that had never
#   run, rather than waiting for 03:00.
#
# scripts/operator/build-configurator-api.py
#   The cockpit hub's _proxy cleared its 30s read timeout via `conn.sock`, which
#   http.client has already set to None for a streaming (no Content-Length)
#   response — so the AttributeError was swallowed by a bare except and the
#   ceiling stayed armed. /api/code-console/chat needs ~40s+ before its first
#   token on CPU, so read1() raised TimeoutError at exactly 30s and the OSError
#   handler counted it as a clean end of stream: the browser got HTTP 200 with
#   an EMPTY body and the console rendered "(no response)". Direct to :8140 the
#   same request streamed fine — only the browser's hop through :8100 failed.
#
# scripts/inference/prompt.py                       (with the gatewayd fix below)
# webapp/code-console/index.html
#   Chat sent no max_tokens, so every answer took the gateway's 96-token default
#   and stopped mid-sentence; the gateway then reported finish_reason "stop" for
#   it, so nothing downstream could tell a capped answer from a finished one and
#   it read as a freeze. prompt.py now asks for a real budget
#   (SOVEREIGN_OS_MAX_NEW_TOKENS, default 512; the gateway clamps at 1024) and
#   carries finish_reason into its done event; the console renders an explicit
#   "truncated at N tokens" note instead of a sentence that simply ends.
#
# scripts/inference/start-logic-engine.sh
#   The vllm_host branch had no way to select an attention backend. vLLM removed
#   VLLM_ATTENTION_BACKEND (0.26 references the name nowhere), leaving
#   --attention-backend as the only mechanism, so a host without nvcc could not
#   tell vLLM to avoid flashinfer's JIT-only kernels. Adds a LOGIC_ATTENTION_BACKEND
#   passthrough.
#
# scripts/inference/start-oracle-core.sh
#   Same gap on the Oracle tier: VllmBackend already appends config.extra_args,
#   but the launcher never populated it, so any flag the backend class does not
#   model was unreachable. The Logic tier needed three of them. Adds
#   ORACLE_EXTRA_ARGS.
_files="
scripts/lib/ms003.py
scripts/sovereign-osctl
scripts/hooks/post-install/open-computer-install.sh
scripts/intelligence/fetch-model.sh
scripts/hooks/recurrent/root-modules-verify.sh
scripts/hooks/recurrent/selfdef-sync.sh
scripts/operator/build-configurator-api.py
scripts/inference/prompt.py
scripts/operator/code-console-api.py
webapp/code-console/index.html
scripts/inference/start-logic-engine.sh
scripts/inference/start-oracle-core.sh
scripts/inference/model-health.py
scripts/operator/lm-orchestration-api.py
webapp/d-03-model-health/index.html
scripts/operator/agent-backend.py
scripts/hooks/post-install/openclaw-install.sh
profiles/sain-01.yaml
"

_patched=0
_changed_files=""
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
    _changed_files="${_changed_files:-} ${rel}"
  else
    fail "could not install ${rel} into the payload"
  fi
done <<< "${_files}"

# ─── payload ADDITIONS — in the repo, never packaged at all ──────────────────
#
# The loop above patches files present in BOTH trees. These are a different
# failure: the file exists in the checkout and is absent from the payload
# entirely, so the old loop reported `skip "not in payload"` and moved on. That
# skip was hiding a real outage.
#
# The package ships scripts/, webapp/, config/, profiles/ and systemd/ but no
# data trees. Most of that is correct — docs/, backlog/, schemas/, assets/ and
# crates/ are referenced only by build-time `gen-*`/`render-*` generators that
# never run on a serving host. models/ is the exception: it is read by NINE
# daemons at request time, which is why a single missing file degraded panels
# all over the cockpit rather than just one.
#
# models/catalog.yaml
#   The canonical model registry, 79 entries across the four SRP tiers
#   (pulse 29, logic 25, oracle 20, router 5). Resolved as
#   _REPO_ROOT/"models"/"catalog.yaml" by scripts/inference/model-health.py,
#   overridable with SOVEREIGN_OS_MODEL_CATALOG. Its load_catalog() is
#   documented "absent/unreadable catalog → empty list (never raises)", so every
#   consumer degraded silently to zero instead of erroring:
#     D-23 Model Catalog ....... "0 models · catalog empty or unreadable"
#     sovereign-brain-api, sovereign-lm-orchestration-api,
#     sovereign-lm-status-operability-api, sovereign-master-dashboard-api,
#     model-health-api, adapters-api, and gatewayd's prompt.py
#   Reported by the operator from the D-23 panel; found by resolving the path
#   the panel itself printed. Verified before shipping: the payload's own
#   hand-rolled stdlib parser (NOT PyYAML — it expects 4-space list entries and
#   6-space scalar fields) reads this exact file as 79 models, so the format
#   contract holds and the copy is sufficient.
#
# tools/__init__.py + tools/notifykit/*.py
#   control-exec-api.py does `sys.path.insert(parents[2])` then
#       from tools.notifykit import cli
#   and on ImportError degrades to
#       503 {"error": "notifykit module unavailable"}
#   which is what every panel's 🔔 overlay has been showing. tools/ is another
#   data/code tree the Architecture:all package omitted.
#
#   Missed by the earlier sweep that found models/catalog.yaml: that one looked
#   for `REPO_ROOT / "dir"` path literals, and this is a PYTHON IMPORT. Two
#   different ways for the payload to reference something it does not ship, and
#   only one of them greps as a path.
#
#   Listed file-by-file rather than as a tree, keeping this module a manifest of
#   known-needed files instead of a directory sync.
_add_files="
models/catalog.yaml
tools/__init__.py
tools/notifykit/__init__.py
tools/notifykit/cli.py
tools/notifykit/config.py
tools/notifykit/channels.py
tools/notifykit/event.py
tools/notifykit/registry.py
"

while read -r rel; do
  [ -n "${rel}" ] || continue
  _a="${_src}/${rel}"
  _b="${_dst}/${rel}"

  if [ ! -f "${_a}" ]; then
    skip "not in checkout: ${rel}"
    continue
  fi
  if [ -f "${_b}" ] && cmp -s "${_a}" "${_b}"; then
    ok "payload current: ${rel}"
    continue
  fi
  if [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "payload += checkout: ${rel}"
    continue
  fi
  # -D creates the parent directory; the package never made /opt/sovereign-os/models.
  # Data, not an executable: 0644, unlike the 0755 scripts patched above.
  if install -D -m 0644 "${_a}" "${_b}" 2>/dev/null; then
    changed "payload += checkout: ${rel}"
    _changed_files="${_changed_files:-} ${rel}"
  else
    fail "could not install ${rel} into the payload"
  fi
done <<< "${_add_files}"

# ─── restart whatever is RUNNING the code we just replaced ────────────────────
#
# The same gap module 80 closed for binaries, still open here for scripts:
# copying a file into the payload does nothing to a process already executing
# the previous version. Caught live — module 72 configured and STARTED
# sovereign-logic-engine, then this module patched the very launcher that unit
# runs. The tier only picked up the fix because it happened to be in a restart
# loop and re-executed the script 15s later. On a healthy unit, converge would
# have reported success while the service kept running stale code.
#
# Ordering alone would not fix it. Even with this module running first, a unit
# already active from a previous boot holds the old copy, so the restart has to
# be driven by "did this file change", not by module order.
_restart_for_script() {
  case "$1" in
    scripts/inference/start-logic-engine.sh) echo "sovereign-logic-engine.service" ;;
    scripts/inference/start-oracle-core.sh)  echo "sovereign-oracle-core.service" ;;
    scripts/operator/build-configurator-api.py) echo "sovereign-dashboards.service" ;;
    scripts/operator/code-console-api.py)    echo "sovereign-code-console-api.service" ;;
    # control-exec-api imports tools.notifykit ONCE at module load and caches the
    # failure as _notifykit_cli = None, so shipping the package is not enough —
    # the daemon has to be restarted to retry the import.
    tools/__init__.py|tools/notifykit/*)     echo "sovereign-control-exec-api.service" ;;
    # prompt.py is imported at request time by the console API, which also holds
    # it via _load(); restart so a patched engine is actually the one running.
    scripts/inference/prompt.py)             echo "sovereign-code-console-api.service" ;;
    # model-health.py is imported ONCE at daemon start by every API that reads the
    # SRP snapshot (importlib exec_module at module scope), so a patched file on
    # disk is not the code answering requests until each consumer restarts.
    # Every consumer, not just the panel that prompted the change: all four
    # daemons exec_module it at start, so patching the file and restarting one of
    # them would leave the other three serving the old snapshot shape — the same
    # answer differing by which port you asked.
    scripts/inference/model-health.py)       echo "sovereign-lm-orchestration-api.service sovereign-model-health-api.service sovereign-models-catalog-api.service sovereign-lm-status-operability-api.service" ;;
    scripts/operator/lm-orchestration-api.py) echo "sovereign-lm-orchestration-api.service" ;;
    # The profile is read per-invocation by the hooks and per-request by the
    # panel APIs, and the OpenClaw installer + agent-backend renderer are run on
    # demand — nothing long-lived caches them. Module 30 re-asserts the GPU cap
    # against this same file, and now agrees with it: the checkout said
    # tdp_watts 350 for the 5090, which that SKU rejects outright, so 30 patched
    # the deployed copy to 400 on EVERY converge. Shipping the checkout without
    # correcting it would have made 90 and 30 flap against each other forever.
    profiles/sain-01.yaml)                   echo "" ;;
    # Timer-driven oneshots re-exec from disk on their next fire, and the webapp
    # + catalog are read per request. Nothing long-lived to restart.
    *)                                       echo "" ;;
  esac
}

# Collect the units FIRST, then restart each exactly once.
#
# Restarting inside the per-file loop meant one restart per changed file: seven
# notifykit files mapped to the same daemon produced seven restarts in a few
# seconds and tripped systemd's start limit —
#     Job for sovereign-control-exec-api.service failed because start of the
#     service was attempted too often.
# — so the module bricked the very daemon it was repairing, and reported five
# successful restarts on the way there. The unit was fine; the loop was wrong.
_units=""
_why=""
for _rel in ${_changed_files:-}; do
  for _u in $(_restart_for_script "${_rel}"); do
    case " ${_units} " in
      *" ${_u} "*) continue ;;   # already queued
    esac
    _units="${_units} ${_u}"
    _why="${_why} ${_u}=${_rel}"
  done
done

for _u in ${_units}; do
  systemctl list-unit-files "${_u}" --no-legend >/dev/null 2>&1 || continue
  systemctl is-active --quiet "${_u}" 2>/dev/null || continue
  # Name one representative file rather than all of them; the point is which
  # unit was restarted and why, not an inventory.
  _rel="$(printf '%s\n' ${_why} | sed -n "s|^${_u}=||p" | head -1)"
  if [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "would restart ${_u} onto the patched ${_rel}"
    continue
  fi
  # A unit already in start-limit lockout (from an earlier buggy run, or its own
  # crash loop) refuses `restart` until the counter is cleared. Clearing it is
  # safe: the limit exists to stop runaway respawns, and this is one deliberate
  # restart, not a loop.
  systemctl reset-failed "${_u}" >/dev/null 2>&1 || true
  if run "restart-consumer" systemctl restart "${_u}"; then
    changed "restarted ${_u} onto the patched payload (${_rel})"
  else
    fail "patched ${_rel} but could not restart ${_u}"
  fi
done

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
