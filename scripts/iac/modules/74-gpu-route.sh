#!/usr/bin/env bash
# route sovereign-gatewayd at the GPU tier
# gate: IAC_ENABLE_GPU_ROUTE
#
# WHY
#   Module 72 puts a 30B model on the RTX 5090 serving at ~268 tok/s, but the
#   cockpit, the Code Console and every /v1/* caller still reach
#   sovereign-gatewayd, which decodes SmolLM2-1.7B on the CPU at ~1 tok/s. The
#   fast engine is unreachable from everything an operator actually uses.
#
#   gatewayd already has the mechanism: POST /v1/models/register attaches an
#   openai-dialect backend as a GPU proxy, and stream_proxy_chat_completions
#   relays its SSE verbatim. Nothing needs to be written — the two halves simply
#   were never introduced.
#
# WHY NOT JUST REPOINT THE CONSOLE AT :8082
#   Because gatewayd is not a passthrough. It carries the safety spine (prompt
#   secret/PII screening, output redaction), the durable memory, the agentic
#   tool loop, the ledger and the completion cache. Bypassing it to reach the
#   GPU would trade every one of those for throughput. Registering the tier as a
#   proxy keeps the spine and moves only generation.
#
# shellcheck shell=bash

_gw="${IAC_GATEWAY_URL:-http://127.0.0.1:8787}"

# One row per GPU tier: "<proxy-id> <endpoint> <device> <vram_gb>". The proxy id
# must equal what the tier serves under (--served-model-name), because gatewayd's
# relay forwards the client's model field verbatim with no rewrite.
_TIERS="
${IAC_GPU_PROXY_ID:-gpu-logic} ${IAC_GPU_TIER_ENDPOINT:-127.0.0.1:8082} ${IAC_GPU_PROXY_DEVICE:-logic} ${IAC_GPU_PROXY_VRAM:-32}
${IAC_ORACLE_PROXY_ID:-gpu-oracle} 127.0.0.1:${IAC_ORACLE_PORT:-8083} oracle ${IAC_ORACLE_PROXY_VRAM:-96}
"

# ─── register every tier that is actually serving ────────────────────────────
# Registering a dead endpoint would leave gatewayd holding an id that resolves to
# nothing, so each tier is probed first and simply skipped when down. A tier that
# is still loading is not an error — converge is re-runnable.
if ! curl -fsS --max-time 5 "${_gw}/health" >/dev/null 2>&1; then
  skip "sovereign-gatewayd not reachable at ${_gw} — cannot register proxies"
  return 0 2>/dev/null || exit 0
fi

# Narrow the SSRF allowlist to exactly the endpoints this box has.
# proxy_endpoint_allowed() permits loopback and LAN by default and only NARROWS
# when this is set, so registration works without it — but /v1/models/register
# lets a caller point the daemon's outbound connections somewhere, and pinning it
# costs two lines.
_allow="$(printf '%s\n' "${_TIERS}" | awk 'NF{printf "%s%s", sep, $2; sep=","}')"
ensure_dropin sovereign-gatewayd.service 30-proxy-allow <<EOF
# Managed by scripts/iac — do not edit by hand.
[Service]
Environment=SOVEREIGN_GATEWAY_PROXY_ALLOW=${_allow}
EOF

_registered="$(curl -fsS --max-time 5 "${_gw}/v1/models" 2>/dev/null \
  | python3 -c "
import sys, json
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
print(' '.join(m.get('id','') for m in d.get('data', [])))
" 2>/dev/null)"

_last_ok=""
while read -r _id _ep _dev _vram; do
  [ -n "${_id}" ] || continue
  if ! curl -fsS --max-time 5 "http://${_ep}/v1/models" >/dev/null 2>&1; then
    skip "tier ${_id} not serving at ${_ep} — nothing to route to"
    continue
  fi
  _served="$(curl -fsS --max-time 5 "http://${_ep}/v1/models" 2>/dev/null \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"][0]["id"])' 2>/dev/null)"
  if [ "${_served}" != "${_id}" ]; then
    # Not fatal, but it WILL 404 on the first proxied request: the relay forwards
    # the client's model field unchanged, so the tier must serve under this id.
    fail "tier at ${_ep} serves '${_served}' but is registered as '${_id}' — set --served-model-name"
    continue
  fi
  _last_ok="${_id}"
  _registered_now="${_registered_now:-} ${_id}"

  case " ${_registered} " in
    *" ${_id} "*) ok "proxy ${_id} already registered (${_ep})"; continue ;;
  esac
  if [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "would register ${_id} → ${_ep}"
    continue
  fi
  # Only id/endpoint/device/vram_gb/dialect are read by models_register — there
  # is no upstream-model-rewrite field, which is why the ids must match above.
  _body="$(printf '{"id":"%s","endpoint":"%s","device":"%s","vram_gb":%s,"dialect":"openai"}' \
    "${_id}" "${_ep}" "${_dev}" "${_vram}")"
  _resp="$(curl -fsS --max-time 10 -X POST "${_gw}/v1/models/register" \
    -H 'Content-Type: application/json' -d "${_body}" 2>&1)"
  case "${_resp}" in
    *'"registered"'*) changed "registered ${_id} → ${_ep} (${_dev}, ${_vram}GB)" ;;
    *)                fail "gatewayd refused ${_id}: ${_resp}" ;;
  esac
done <<< "${_TIERS}"

# ─── designate a background model ────────────────────────────────────────────
# The reserved "background" alias routes deliberation and CoAT expansion off the
# primary. Prefer the ORACLE tier when it is up — it is the larger card and the
# more capable model — else whichever tier registered. Either beats a 1 tok/s CPU
# primary for every caller already using the alias.
# Only designate a tier that actually registered. The configured preference is
# honoured just when it is among them: pointing the alias at an absent id looked
# fine in the report ("background alias → gpu-oracle") while gatewayd, whose
# background_id() resolves only a LOADED backend, silently fell back to the
# 1 tok/s CPU primary. A green line for a routing decision that did not happen.
_bg_target=""
case " ${_registered_now:-} " in
  *" ${IAC_GPU_BACKGROUND_ID:-} "*) _bg_target="${IAC_GPU_BACKGROUND_ID}" ;;
  *) _bg_target="${_last_ok}" ;;
esac
if [ -n "${IAC_GPU_BACKGROUND_ID:-}" ] && [ "${_bg_target}" != "${IAC_GPU_BACKGROUND_ID}" ]; then
  iac_info "preferred background '${IAC_GPU_BACKGROUND_ID}' is not serving — using '${_bg_target:-none}'"
fi
if [ "${IAC_GPU_SET_BACKGROUND:-1}" = 1 ] && [ -n "${_bg_target}" ] && [ "${IAC_DRY_RUN}" != 1 ]; then
  _bg="$(curl -fsS --max-time 10 -X POST "${_gw}/v1/models/background" \
    -H 'Content-Type: application/json' -d "{\"id\":\"${_bg_target}\"}" 2>&1)"
  case "${_bg}" in
    *"${_bg_target}"*) ok "background alias → ${_bg_target}" ;;
    *)                 iac_info "could not set the background alias: ${_bg}" ;;
  esac
fi
