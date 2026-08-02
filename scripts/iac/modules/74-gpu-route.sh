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
_tier_ep="${IAC_GPU_TIER_ENDPOINT:-127.0.0.1:8082}"
_proxy_id="${IAC_GPU_PROXY_ID:-gpu-logic}"

# ─── the tier must actually be serving ───────────────────────────────────────
# Registering an endpoint that is down would leave gatewayd holding a dead id:
# `background_id()` is documented to resolve only a LOADED backend, but the
# proxy table itself does not probe. Check before claiming.
if ! curl -fsS --max-time 5 "http://${_tier_ep}/v1/models" >/dev/null 2>&1; then
  skip "GPU tier not serving at ${_tier_ep} — nothing to route to (module 72 first)"
  return 0 2>/dev/null || exit 0
fi
if ! curl -fsS --max-time 5 "${_gw}/health" >/dev/null 2>&1; then
  skip "sovereign-gatewayd not reachable at ${_gw} — cannot register a proxy"
  return 0 2>/dev/null || exit 0
fi

# The model id vLLM serves under is the weights PATH unless --served-model-name
# was passed, and the proxy must forward that exact string upstream.
_upstream_id="$(curl -fsS --max-time 5 "http://${_tier_ep}/v1/models" 2>/dev/null \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"][0]["id"])' 2>/dev/null)"
iac_info "tier ${_tier_ep} serves '${_upstream_id:-?}'"

# ─── narrow the SSRF allowlist ───────────────────────────────────────────────
# proxy_endpoint_allowed() permits loopback and LAN by default and only NARROWS
# when SOVEREIGN_GATEWAY_PROXY_ALLOW is set. Registration would therefore work
# without this — but /v1/models/register lets any caller point the daemon's
# outbound connections somewhere, so pinning it to the one endpoint this box
# actually has is worth the two lines.
ensure_dropin sovereign-gatewayd.service 30-proxy-allow <<EOF
# Managed by scripts/iac — do not edit by hand.
[Service]
Environment=SOVEREIGN_GATEWAY_PROXY_ALLOW=${_tier_ep}
EOF

# ─── register ────────────────────────────────────────────────────────────────
# Idempotent by asking gatewayd what it already has. The proxy table is
# in-memory, so this re-registers after every gatewayd restart — which is the
# correct behaviour, not a wasted call.
_registered="$(curl -fsS --max-time 5 "${_gw}/v1/models" 2>/dev/null \
  | python3 -c "
import sys, json
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
print(' '.join(m.get('id','') for m in d.get('data', [])))
" 2>/dev/null)"

case " ${_registered} " in
  *" ${_proxy_id} "*)
    ok "proxy ${_proxy_id} already registered with gatewayd"
    ;;
  *)
    if [ "${IAC_DRY_RUN}" = 1 ]; then
      changed "would register ${_proxy_id} → ${_tier_ep}"
    else
      # device/vram are advertised to operators in GET /v1/models; they describe
      # the tier, they do not allocate anything.
      # Only id/endpoint/device/vram_gb/dialect are read by models_register —
      # there is no upstream-model-rewrite field, which is exactly why module 72
      # gives vLLM --served-model-name equal to this id.
      _body="$(printf '{"id":"%s","endpoint":"%s","device":"%s","vram_gb":%s,"dialect":"openai"}' \
        "${_proxy_id}" "${_tier_ep}" "${IAC_GPU_PROXY_DEVICE:-logic}" \
        "${IAC_GPU_PROXY_VRAM:-32}")"
      _resp="$(curl -fsS --max-time 10 -X POST "${_gw}/v1/models/register" \
        -H 'Content-Type: application/json' -d "${_body}" 2>&1)"
      case "${_resp}" in
        *'"registered"'*) changed "registered ${_proxy_id} → ${_tier_ep} (${_upstream_id})" ;;
        *)                fail "gatewayd refused the proxy registration: ${_resp}" ;;
      esac
    fi
    ;;
esac

# ─── designate it for background work ────────────────────────────────────────
# The reserved "background" alias routes deliberation and CoAT expansion to a
# secondary so they do not block the primary. With a 268 tok/s backend attached
# and a 1 tok/s primary, pointing background at the GPU is strictly better for
# every caller that already uses the alias.
if [ "${IAC_GPU_SET_BACKGROUND:-1}" = 1 ] && [ "${IAC_DRY_RUN}" != 1 ]; then
  _bg="$(curl -fsS --max-time 10 -X POST "${_gw}/v1/models/background" \
    -H 'Content-Type: application/json' -d "{\"id\":\"${_proxy_id}\"}" 2>&1)"
  case "${_bg}" in
    *"${_proxy_id}"*) ok "background alias → ${_proxy_id}" ;;
    *)                iac_info "could not set the background alias: ${_bg}" ;;
  esac
fi
