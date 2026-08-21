#!/usr/bin/env bash
# route sovereign-gatewayd at the GPU tiers
# gate: IAC_ENABLE_GPU_ROUTE
#
# WHY 84 AND NOT 74
#   Modules run in NUMERIC order, not the order they are listed on the command
#   line. As 74 this ran BEFORE 80-binaries, with two consequences on the same
#   converge: it talked to the OLD gatewayd — which 404'd on /v1/models/default
#   because that route had just been written — and then 80 installed the new
#   binary and restarted the daemon, wiping the proxy table it had just
#   populated. The registry is IN-MEMORY, so every gatewayd restart empties it.
#   Routing configuration must therefore come after the binary that serves it,
#   and after the tiers it points at (72, 76).
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
# WHY THE WORK MOVED OUT OF THIS FILE
#   An earlier version of this module carried the registration logic inline and
#   noted, as an accepted limitation, that a gatewayd restart outside converge
#   "also drops the proxies until the next converge re-runs this module. That is
#   inherent to an in-memory registry, not a bug introduced here."
#
#   It then happened for real. The box rebooted to have an eGPU fitted and came
#   back with both tiers serving and NOTHING routed to them: every unit green,
#   no error anywhere, and every caller silently back on the 1.7B CPU model. It
#   surfaced only as a reply that took 12 seconds.
#
#   The registry being in-memory is indeed inherent. A machine that does not
#   return to its converged state after a reboot is not — that is a gap in the
#   IaC. So the logic now lives in assets/gpu-route-apply.sh, installed here and
#   driven by systemd from three triggers: boot, any gatewayd restart (PartOf=),
#   and converge. This module installs it, configures it, and runs it.
#
# shellcheck shell=bash

_gw="${IAC_GATEWAY_URL:-http://127.0.0.1:8787}"
_libdir="${IAC_GPU_ROUTE_LIBDIR:-/usr/local/lib/sovereign-os}"
_applier="${_libdir}/gpu-route-apply.sh"
_unit=sovereign-gpu-route.service
_reconcile_unit=sovereign-gpu-route-reconcile.service
_reconcile_timer=sovereign-gpu-route-reconcile.timer

# One COMMA-separated record per GPU tier: "<proxy-id>@<endpoint>@<device>@<vram_gb>".
# The proxy id must equal what the tier serves under (--served-model-name),
# because gatewayd's relay forwards the client's model field verbatim with no
# rewrite. Comma and not space because the applier sources this file with bash,
# where an unquoted value holding a space runs its second word as a command.
_TIERS="${IAC_GPU_PROXY_ID:-gpu-logic}@${IAC_GPU_TIER_ENDPOINT:-127.0.0.1:8082}@${IAC_GPU_PROXY_DEVICE:-logic}@${IAC_GPU_PROXY_VRAM:-32}"
_TIERS="${_TIERS},${IAC_ORACLE_PROXY_ID:-gpu-oracle}@127.0.0.1:${IAC_ORACLE_PORT:-8083}@oracle@${IAC_ORACLE_PROXY_VRAM:-96}"

# ─── the applier ──────────────────────────────────────────────────────────────
# Installed from the repo checkout module 15 maintains, NOT from /opt: the
# payload tree is dpkg-owned and only module 90 writes into it — and 90 runs
# AFTER this one. A boot unit whose ExecStart lands in the payload would point at
# a file that does not exist until the next converge.
_src="${IAC_SOURCE_RESOLVED_DIR:-${IAC_SOURCE_DIR:-}}/scripts/iac/assets/gpu-route-apply.sh"
if [ ! -f "${_src}" ]; then
  _self_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  _src="${_self_dir}/assets/gpu-route-apply.sh"
fi
if [ ! -f "${_src}" ]; then
  fail "gpu-route-apply.sh not found — cannot install the routing applier"
  return 0 2>/dev/null || exit 0
fi

ensure_dir "${_libdir}" 0755 root:root
ensure_file "${_applier}" 0755 root:root < "${_src}"

# ─── configuration ────────────────────────────────────────────────────────────
# Built once into a variable, not written straight out, because a dry run has to
# preview routing against the config it WOULD write. Reading it back off disk
# would mean previewing against whatever converge left there last time — or,
# on a first run, against nothing at all, which reports "no tiers configured"
# and looks like a clean pass over work that was never examined.
_env_content="# Managed by scripts/iac — do not edit by hand.
# Consumed by ${_applier}, from converge and from ${_unit}.
GPU_ROUTE_GATEWAY=${_gw}
GPU_ROUTE_TIERS=${_TIERS}
GPU_ROUTE_DEFAULT=${IAC_GPU_DEFAULT_ID:-gpu-logic}
GPU_ROUTE_BACKGROUND=${IAC_GPU_BACKGROUND_ID:-gpu-oracle}
GPU_ROUTE_SET_DEFAULT=${IAC_GPU_SET_DEFAULT:-1}
GPU_ROUTE_SET_BACKGROUND=${IAC_GPU_SET_BACKGROUND:-1}
# Wait budgets use := (not =) so a unit's Environment= WINS over this default
# instead of being clobbered. The applier SOURCES this file AFTER systemd has set
# the process env, so a plain assignment would overwrite the guard unit's
# Environment=GPU_ROUTE_TIER_TRIES=150 with 45 — silently capping the intended
# 300s cold-checkpoint wait (see the unit's TimeoutStartSec comment) at 90s. With
# :=, the file supplies the default only when nothing already set it (a converge
# direct run, or the reconcile timer, both of which want the shorter budget).
: \"\${GPU_ROUTE_GATEWAY_TRIES:=${IAC_GATEWAY_WAIT_TRIES:-30}}\"
: \"\${GPU_ROUTE_TIER_TRIES:=${IAC_TIER_WAIT_TRIES:-45}}\""

ensure_dir /etc/sovereign-os 0755 root:root
# Here-string, NOT a pipe: `printf ... | ensure_file ...` would run ensure_file in
# a subshell, where its ok/changed increments are made and then discarded with
# the subshell, so the file would silently stop appearing in the summary.
ensure_file /etc/sovereign-os/gpu-route.env 0644 root:root <<< "${_env_content}"

# ─── the embeddings upstream ─────────────────────────────────────────────────
# Module 78 SERVES the Router tier; this module is the single owner of gatewayd's
# outbound configuration, so pointing the daemon at the embedder belongs here.
# Splitting it would mean two modules writing Environment=SOVEREIGN_GATEWAY_
# PROXY_ALLOW in separate drop-ins, and systemd does not merge those — the
# alphabetically-later file wins outright and silently drops the other's
# endpoints.
#
# Deliberately NOT a proxy registration: /v1/embeddings resolves this env var,
# not resolve_proxy(), precisely so a pooling model can never become the target
# of "auto" and be handed a chat completion it cannot answer.
_embed_ep="127.0.0.1:${IAC_ROUTER_EMBED_PORT:-8084}"
_embed_model="${IAC_ROUTER_EMBED_NAME:-gpu-embed}"

# Narrow the SSRF allowlist to exactly the endpoints this box has.
# proxy_endpoint_allowed() permits loopback and LAN by default and only NARROWS
# when this is set, so registration works without it — but /v1/models/register
# lets a caller point the daemon's outbound connections somewhere, and pinning it
# costs two lines.
#
# The Router endpoints have to be in here too. The allowlist is checked for EVERY
# outbound destination, including the embeddings relay — leaving it at the two
# chat tiers would have made /v1/embeddings answer 403 against a backend that was
# up and healthy.
_allow="$(printf '%s' "${_TIERS}" | tr ',' '\n' | awk -F'@' 'NF{printf "%s%s", sep, $2; sep=","}')"
_allow="${_allow},${_embed_ep},127.0.0.1:${IAC_ROUTER_RERANK_PORT:-8085}"
_dropin=/etc/systemd/system/sovereign-gatewayd.service.d/30-proxy-allow.conf
_dropin_before="$(cat "${_dropin}" 2>/dev/null | sha256sum)"
ensure_dropin sovereign-gatewayd.service 30-proxy-allow <<EOF
# Managed by scripts/iac — do not edit by hand.
[Service]
Environment=SOVEREIGN_GATEWAY_PROXY_ALLOW=${_allow}
Environment=SOVEREIGN_GATEWAY_EMBED_ENDPOINT=${_embed_ep}
Environment=SOVEREIGN_GATEWAY_EMBED_MODEL=${_embed_model}
EOF

# ─── the unit that makes routing survive a restart ────────────────────────────
# PartOf is the load-bearing line. WantedBy=multi-user.target alone would only
# cover boot, leaving the exact hole this unit exists to close: `systemctl
# restart sovereign-gatewayd` — which module 80 does on every binary change —
# empties the registry with nothing to refill it. PartOf propagates gatewayd's
# restarts here, so the applier re-runs whenever the thing holding the registry
# comes back.
#
# Type=oneshot + RemainAfterExit so the unit reads as active once routing is
# applied, rather than as a dead service.
ensure_file "/etc/systemd/system/${_unit}" 0644 root:root <<EOF
# Managed by scripts/iac — do not edit by hand.
[Unit]
Description=sovereign-os — register GPU tiers with sovereign-gatewayd
Documentation=https://github.com/cyberpunk042/sovereign-os/blob/main/scripts/iac/modules/84-gpu-route.sh
After=sovereign-gatewayd.service sovereign-logic-engine.service sovereign-oracle-core.service
Wants=sovereign-logic-engine.service sovereign-oracle-core.service
Requires=sovereign-gatewayd.service
PartOf=sovereign-gatewayd.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=${_applier}
# The applier's own bounded waits are the real budget; this only has to be
# larger than they are. A cold-cache 58 GiB checkpoint load is minutes, not
# seconds, and a tier that is still loading must not be recorded as absent.
TimeoutStartSec=${IAC_GPU_ROUTE_TIMEOUT:-900}
Environment=GPU_ROUTE_TIER_TRIES=${IAC_GPU_ROUTE_BOOT_TIER_TRIES:-150}

[Install]
WantedBy=multi-user.target
EOF

# ─── level trigger: close the gap the three edge-triggers cannot ──────────────
# The unit above re-registers on three EDGE triggers — boot, a gatewayd restart
# (PartOf=), and converge. None of them fire in the case that actually stranded
# this box: gatewayd stays UP the whole time while its in-memory registry drifts
# away from converged state — a tier that finished loading its 58 GiB checkpoint
# after the boot window closed, a tier that OOM'd and came back, a gatewayd
# auto-restart (Restart=on-failure) that does NOT propagate PartOf the way a
# `systemctl restart` does, or the registry going unreachable while the daemon
# itself never restarts. In every one the tiers serve and nothing routes to them:
# the exact silent 1-tok/s fallback this module exists to end, reached by a path
# the edge triggers miss. A periodic re-assertion is the level-triggered
# complement — the applier is idempotent (an already-routed tier is an OK, not a
# CHANGED and no POST), so a healthy box just re-reads and logs OKs, and a
# diverged one is repaired within one interval instead of waiting for a restart
# that may be days away.
#
# A SEPARATE oneshot, not the guard unit above: that one is RemainAfterExit=yes
# so PartOf can see it as active, and systemd will NOT re-run an already-active
# oneshot's ExecStart — a timer pointed at it would fire and do nothing. This
# unit omits RemainAfterExit so every timer fire genuinely re-runs the applier.
ensure_file "/etc/systemd/system/${_reconcile_unit}" 0644 root:root <<EOF
# Managed by scripts/iac — do not edit by hand.
[Unit]
Description=sovereign-os — reconcile GPU tier routing with sovereign-gatewayd
Documentation=https://github.com/cyberpunk042/sovereign-os/blob/main/scripts/iac/modules/84-gpu-route.sh
After=sovereign-gatewayd.service
Wants=sovereign-gatewayd.service

[Service]
Type=oneshot
ExecStart=${_applier}
# Reads the same /etc/sovereign-os/gpu-route.env as the guard unit, so a
# reconcile blocks at most the applier's own bounded waits when a tier or the
# gateway is down. Larger than those so a slow-but-present tier is not cut off.
TimeoutStartSec=${IAC_GPU_ROUTE_RECONCILE_TIMEOUT:-300}
EOF

ensure_file "/etc/systemd/system/${_reconcile_timer}" 0644 root:root <<EOF
# Managed by scripts/iac — do not edit by hand.
[Unit]
Description=sovereign-os — periodically reconcile GPU tier routing

[Timer]
# OnBootSec sits AFTER the guard unit's boot window so the first reconcile checks
# a settled machine rather than racing the checkpoint loads; then on a cadence.
# Persistent=false: a missed run is worthless — this asserts CURRENT routing, and
# replaying a stale run would re-assert a registry state that has already moved on.
OnBootSec=${IAC_GPU_ROUTE_RECONCILE_BOOT_SEC:-120}
OnUnitActiveSec=${IAC_GPU_ROUTE_RECONCILE_INTERVAL:-180}
AccuracySec=${IAC_GPU_ROUTE_RECONCILE_ACCURACY:-15}
Persistent=false

[Install]
WantedBy=timers.target
EOF
iac_daemon_reload

# ─── apply now, and report what the applier did ───────────────────────────────
# STARTED, not merely enabled. The first version enabled the unit and left it
# inactive, reasoning that the direct run below already does the work — which is
# true for the routing, and completely wrong for the protection. PartOf only
# propagates a restart to units that are ACTIVE. An enabled-but-inactive
# sovereign-gpu-route is not restarted when gatewayd restarts, so the guard
# against exactly the failure this module exists to fix would have stayed dormant
# until the next reboot: installed, reported green, doing nothing.
#
# With RemainAfterExit=yes the unit stays active once the applier has run, which
# is what arms PartOf. Starting it does run the applier an extra time; it is
# idempotent, and the direct run below then reports `ok` for every assertion.
# A drop-in only reaches the process at its next start. Writing SOVEREIGN_GATEWAY_
# EMBED_ENDPOINT and reporting `changed file ...` while the running daemon still
# has none of it is the same failure this module was rewritten to end: correct on
# disk, absent in the machine, green in the report. So a changed drop-in restarts
# the daemon — and because gpu-route is PartOf gatewayd, routing is re-applied on
# the way back up rather than being lost by the restart.
_dropin_now="$(cat "${_dropin}" 2>/dev/null | sha256sum)"
if [ "${_dropin_before}" != "${_dropin_now}" ] && [ "${IAC_DRY_RUN}" != 1 ]; then
  systemctl reset-failed sovereign-gatewayd.service >/dev/null 2>&1 || true
  if run "restart-gatewayd" systemctl restart sovereign-gatewayd.service; then
    changed "restarted sovereign-gatewayd onto the new outbound configuration"
  else
    fail "gatewayd outbound configuration changed but the daemon would not restart"
  fi
fi

ensure_unit_state "${_unit}" enabled started

# Arm the level-triggered reconcile (see the unit comments above). Gated so a
# deployment that wants only the three edge triggers can turn it off, but on by
# default: this timer is the one guard against the in-memory registry drifting
# while gatewayd stays up — the failure mode that put every caller back on the
# 1.7B CPU model for a week with every unit green.
if [ "${IAC_GPU_ROUTE_RECONCILE_ENABLE:-1}" = 1 ]; then
  ensure_unit_state "${_reconcile_timer}" enabled started
else
  ensure_unit_state "${_reconcile_timer}" disabled stopped
  skip "gpu-route reconcile timer left disabled (IAC_GPU_ROUTE_RECONCILE_ENABLE=0)"
fi

# On a dry run — and on the first real converge before the install above has
# actually written anything — the installed copy does not exist yet. Fall back to
# the source, which is byte-for-byte what ensure_file installs, so a dry run
# still previews the routing instead of reporting a phantom clean pass.
_run_applier="${_applier}"
[ -x "${_applier}" ] || _run_applier="${_src}"

if [ "${IAC_DRY_RUN}" = 1 ]; then
  # Preview against the config this run WOULD write, from a temp file, since a
  # dry run must not touch /etc.
  _tmp_env="$(mktemp)"
  printf '%s\n' "${_env_content}" > "${_tmp_env}"
  _out="$(GPU_ROUTE_ENV="${_tmp_env}" GPU_ROUTE_DRY_RUN=1 bash "${_run_applier}" 2>&1)"; _arc=$?
  rm -f "${_tmp_env}"
else
  _out="$(bash "${_run_applier}" 2>&1)"; _arc=$?
fi

# Translate the applier's status lines into converge's counters, so a routing
# change shows up in the summary exactly like a file or a unit does. Anything
# unprefixed is the applier's own stderr and is surfaced rather than swallowed —
# a silent applier was how this whole class of problem stayed invisible.
_saw_fail=0
while IFS= read -r _line; do
  [ -n "${_line}" ] || continue
  case "${_line}" in
    'OK '*)      ok      "${_line#OK }" ;;
    'CHANGED '*) changed "${_line#CHANGED }" ;;
    'SKIP '*)    skip    "${_line#SKIP }" ;;
    'FAIL '*)    fail    "${_line#FAIL }"; _saw_fail=1 ;;
    *)           iac_info "gpu-route: ${_line}" ;;
  esac
done <<< "${_out}"

# An applier that died before it could emit a status line — unreadable, not
# executable, python3 missing — would otherwise leave this module reporting a
# clean pass over routing it never touched. That silence is the failure mode this
# whole unit exists to eliminate, so it must not be reintroduced here.
if [ "${_arc}" -ne 0 ] && [ "${_saw_fail}" = 0 ]; then
  fail "gpu-route applier exited ${_arc} without reporting why — routing state unverified"
fi
