#!/usr/bin/env bash
# Apply GPU proxy routing to sovereign-gatewayd.
#
# WHY THIS IS A SCRIPT AND NOT JUST A CONVERGE MODULE
#   gatewayd's proxy registry is IN-MEMORY. Every restart empties it, and the
#   tiers keep serving perfectly while nothing can reach them. Module 84 used to
#   be the only thing that repopulated it, so routing survived exactly until the
#   next reboot — at which point the box came back with two GPUs serving 268 and
#   107 tok/s and every caller silently back on a 1.7B CPU model at ~1 tok/s.
#   Nothing failed, nothing logged, the units were all green. It was found by
#   noticing a 12-second reply.
#
#   The module's own comment called that "inherent to an in-memory registry, not
#   a bug introduced here". Inherent to the registry, yes; but a machine that
#   does not come back up in its converged state is a gap in the IaC, not a
#   property to accept. So the logic lives here, where systemd can re-run it:
#     - at boot                       (WantedBy=multi-user.target)
#     - whenever gatewayd restarts    (PartOf=sovereign-gatewayd.service)
#     - during converge               (module 84 runs this same file)
#   One implementation, three triggers, rather than a converge-only fixup.
#
# CONTRACT WITH MODULE 84
#   Reads /etc/sovereign-os/gpu-route.env (written by the module) and emits one
#   status line per assertion on stdout:
#       OK|CHANGED|SKIP|FAIL <text>
#   so converge can report it with the same ok/changed/skip/fail counters it uses
#   everywhere else. Exit is non-zero only when a FAIL was emitted — a tier that
#   is down is a SKIP, because a re-runnable applier should not fail over a card
#   that is still loading a 58 GiB checkpoint.
#
# shellcheck shell=bash
set -uo pipefail

ENV_FILE="${GPU_ROUTE_ENV:-/etc/sovereign-os/gpu-route.env}"
# shellcheck disable=SC1090
[ -r "${ENV_FILE}" ] && . "${ENV_FILE}"

GW="${GPU_ROUTE_GATEWAY:-http://127.0.0.1:8787}"
TIERS="${GPU_ROUTE_TIERS:-}"
WANT_DEFAULT="${GPU_ROUTE_DEFAULT:-}"
WANT_BG="${GPU_ROUTE_BACKGROUND:-}"
SET_DEFAULT="${GPU_ROUTE_SET_DEFAULT:-1}"
SET_BG="${GPU_ROUTE_SET_BACKGROUND:-1}"
GW_TRIES="${GPU_ROUTE_GATEWAY_TRIES:-30}"
TIER_TRIES="${GPU_ROUTE_TIER_TRIES:-45}"
NAP="${GPU_ROUTE_SLEEP:-2}"
DRY="${GPU_ROUTE_DRY_RUN:-0}"

_rc=0
say_ok()      { printf 'OK %s\n' "$*"; }
say_changed() { printf 'CHANGED %s\n' "$*"; }
say_skip()    { printf 'SKIP %s\n' "$*"; }
say_fail()    { printf 'FAIL %s\n' "$*"; _rc=1; }

# One fetch, three answers. Reading /v1/models once and pulling the registered
# ids, the default and the background out of the same document keeps the three
# decisions below consistent with each other.
gw_state() {
  curl -fsS --max-time 5 "${GW}/v1/models" 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
print(" ".join(m.get("id", "") for m in d.get("data", [])))
print(d.get("default") or "")
print(d.get("background") or "")
' 2>/dev/null
}

wait_for() {  # wait_for <url> <tries>
  local url="$1" left="$2"
  while [ "${left}" -gt 0 ]; do
    curl -fsS --max-time 3 "${url}" >/dev/null 2>&1 && return 0
    left=$(( left - 1 ))
    sleep "${NAP}"
  done
  return 1
}

if [ -z "${TIERS}" ]; then
  say_skip "no tiers configured in ${ENV_FILE} — nothing to route"
  exit 0
fi

# gatewayd loads its primary model BEFORE it listens, so at boot and after any
# restart there is a window where the socket is simply not there yet. Probing
# once loses a race it is guaranteed to enter.
if ! wait_for "${GW}/health" "${GW_TRIES}"; then
  say_fail "sovereign-gatewayd not reachable at ${GW} after $(( GW_TRIES * NAP ))s — proxies unregistered"
  exit 1
fi

_state="$(gw_state)"
if [ -z "${_state}" ]; then
  say_fail "sovereign-gatewayd answered /health but not /v1/models — cannot read routing state"
  exit 1
fi
_registered=" $(printf '%s' "${_state}" | sed -n 1p) "
_cur_default="$(printf '%s' "${_state}" | sed -n 2p)"
_cur_bg="$(printf '%s' "${_state}" | sed -n 3p)"

# ─── register every tier that is actually serving ────────────────────────────
# Records are COMMA-separated, fields @-separated. Not space-separated: this file
# is sourced by bash, and an unquoted `GPU_ROUTE_TIERS=a b` runs `b` as a command.
# Quoting in the writer would fix it too, but a separator that cannot break is
# better than a rule the next writer has to remember.
_live=""
for _rec in ${TIERS//,/ }; do
  IFS='@' read -r _id _ep _dev _vram <<<"${_rec}"
  [ -n "${_id:-}" ] && [ -n "${_ep:-}" ] || { say_fail "malformed tier record '${_rec}'"; continue; }

  if ! wait_for "http://${_ep}/v1/models" "${TIER_TRIES}"; then
    say_skip "tier ${_id} not serving at ${_ep} — nothing to route to"
    continue
  fi

  # The relay forwards the client's model field verbatim; there is no
  # upstream-rewrite field in models_register. So the tier MUST serve under the
  # id it is registered as, or the first proxied request 404s at the backend.
  _served="$(curl -fsS --max-time 5 "http://${_ep}/v1/models" 2>/dev/null \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"][0]["id"])' 2>/dev/null)"
  if [ "${_served}" != "${_id}" ]; then
    say_fail "tier at ${_ep} serves '${_served}' but is registered as '${_id}' — set --served-model-name"
    continue
  fi

  _live="${_live} ${_id}"
  case "${_registered}" in
    *" ${_id} "*) say_ok "proxy ${_id} already registered (${_ep})"; continue ;;
  esac
  if [ "${DRY}" = 1 ]; then
    say_changed "would register ${_id} → ${_ep}"
    continue
  fi
  _body="$(printf '{"id":"%s","endpoint":"%s","device":"%s","vram_gb":%s,"dialect":"openai"}' \
    "${_id}" "${_ep}" "${_dev:-gpu}" "${_vram:-0}")"
  _resp="$(curl -fsS --max-time 10 -X POST "${GW}/v1/models/register" \
    -H 'Content-Type: application/json' -d "${_body}" 2>&1)"
  case "${_resp}" in
    *'"registered"'*) say_changed "registered ${_id} → ${_ep} (${_dev:-gpu}, ${_vram:-0}GB)" ;;
    *)                say_fail "gatewayd refused ${_id}: ${_resp}" ;;
  esac
done
_live="${_live} "

# ─── designate an alias, honestly ─────────────────────────────────────────────
# Shared by "auto" (what every caller with no preference sends) and "background"
# (deliberation and CoAT expansion). Both had the same two bugs before: pointing
# at an id that never registered — which reads green in the report while
# gatewayd, whose resolver only returns a LOADED backend, quietly falls back to
# the CPU primary — and reporting a fixed verdict regardless of what changed.
# So: only ever designate something in ${_live}, and compare against the CURRENT
# designation before claiming anything.
designate() {  # designate <alias> <endpoint-path> <preferred-id> <current> <enabled>
  local alias="$1" path="$2" want="$3" cur="$4" enabled="$5" target="" resp=""
  [ "${enabled}" = 1 ] || return 0

  case "${_live}" in
    *" ${want} "*) target="${want}" ;;
    *) # fall back to any live tier rather than stranding the alias
       target="$(printf '%s' "${_live}" | awk '{print $NF}')"
       [ -n "${want}" ] && [ -n "${target}" ] \
         && say_skip "preferred ${alias} target ${want} is not serving — using ${target}"
       ;;
  esac
  [ -n "${target}" ] || { say_skip "no live tier to point ${alias} at"; return 0; }

  if [ "${cur}" = "${target}" ]; then say_ok "${alias} → ${target}"; return 0; fi
  if [ "${DRY}" = 1 ]; then say_changed "would set ${alias} → ${target} (currently ${cur:-primary})"; return 0; fi

  resp="$(curl -fsS --max-time 10 -X POST "${GW}${path}" \
    -H 'Content-Type: application/json' -d "{\"id\":\"${target}\"}" 2>&1)"
  # The reply reports both what was ASKED and what is ACTIVE. Only "active"
  # means routing actually moved.
  case "${resp}" in
    *'"active":"'"${target}"'"'*) say_changed "${alias} → ${target}" ;;
    *) say_fail "gatewayd recorded ${alias} but it is not active: ${resp}" ;;
  esac
}

designate auto       /v1/models/default    "${WANT_DEFAULT}" "${_cur_default}" "${SET_DEFAULT}"
designate background /v1/models/background "${WANT_BG}"      "${_cur_bg}"      "${SET_BG}"

exit "${_rc}"
