#!/usr/bin/env bash
# publish what the tiers ACTUALLY serve, so the panels stop describing the catalog
# gate: IAC_ENABLE_MODEL_STATE
#
# WHY
#   Every device cell in D-21 / D-22 / D-03 listed catalog CANDIDATES. The box
#   showed GPU0 hosting DeepSeek-R1-Distill-70B while gpt-oss-120b was the
#   process running, GPU1 hosting Qwen-32B-Ternary-Quant while Nemotron-30B
#   served, and the eGPU hosting nomic-embed-text-v2-moe — not even downloaded —
#   while bge-m3 answered every request.
#
#   Nothing was lying: model-health falls back to the catalog and labels it
#   `model_source: catalog`. But a panel whose rows describe an intention rather
#   than a machine is the same failure as "EXT_GPU · N/A" and the silently
#   unrouted GPUs — reporting the plan and calling it the state. This is the
#   third instance in two days, so it is worth fixing at the source rather than
#   one panel at a time.
#
# WHY NOTHING PUBLISHED IT BEFORE
#   The data path was already complete. model-health PREFERS `loaded` from
#   /run/sovereign-os/model-state.json; scripts/models/load.py writes `loaded`
#   and scripts/inference/prompt.py writes measured `tokens_per_sec`. Those
#   writers simply never run for the vLLM tiers, which systemd starts directly —
#   nothing was missing except the part that observes reality.
#
# WHY A TIMER AND NOT A HOOK ON EACH TIER
#   A timer converges on the truth from any starting point: a tier started by
#   hand, a crash, a unit stopped outside converge. Publishing only on tier start
#   would leave a stopped tier claiming residency until something restarted it —
#   the exact stale-claim problem being fixed. The publisher asks each tier what
#   IT says it serves, so a tier that does not answer contributes nothing and
#   disappears from the panel.
#
# shellcheck shell=bash

_libdir="${IAC_GPU_ROUTE_LIBDIR:-/usr/local/lib/sovereign-os}"
_pub="${_libdir}/publish-model-state.py"
_unit=sovereign-model-state.service
_timer=sovereign-model-state.timer

# Installed from the checkout, not the payload: /opt is dpkg-owned and only
# module 90 writes there, and 90 runs AFTER this module.
_src="${IAC_SOURCE_RESOLVED_DIR:-${IAC_SOURCE_DIR:-}}/scripts/iac/assets/publish-model-state.py"
if [ ! -f "${_src}" ]; then
  _self_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  _src="${_self_dir}/assets/publish-model-state.py"
fi
if [ ! -f "${_src}" ]; then
  fail "publish-model-state.py not found — cannot install the state publisher"
  return 0 2>/dev/null || exit 0
fi

ensure_dir "${_libdir}" 0755 root:root
ensure_file "${_pub}" 0755 root:root < "${_src}"

# One record per serving tier: "<role>@<host:port>@<catalog-id>".
#
# The catalog id is carried separately because a tier serves under its PROXY id
# (gpu-logic, gpu-embed) — gatewayd's relay forwards the client's model field
# verbatim, so the served name has to match the proxy name. That is a routing
# name, not a model name; the panel should show the model. Defaults track the
# same variables modules 72 / 76 / 78 use, so a retier in converge.conf moves
# this table with it rather than silently disagreeing.
_TIERS="logic@${IAC_GPU_TIER_ENDPOINT:-127.0.0.1:8082}@${IAC_VLLM_MODEL_ID:-Nemotron-3-Nano-Omni-30B-Reasoning-NVFP4}"
_TIERS="${_TIERS},oracle@127.0.0.1:${IAC_ORACLE_PORT:-8083}@${IAC_ORACLE_MODEL_ID:-gpt-oss-120b}"
_TIERS="${_TIERS},router@127.0.0.1:${IAC_ROUTER_EMBED_PORT:-8084}@${IAC_ROUTER_EMBED_ID:-BAAI-bge-m3}"
_TIERS="${_TIERS},router@127.0.0.1:${IAC_ROUTER_RERANK_PORT:-8085}@${IAC_ROUTER_RERANK_ID:-BAAI-bge-reranker-v2-m3}"

ensure_dir /etc/sovereign-os 0755 root:root
ensure_file /etc/sovereign-os/model-state-publish.env 0644 root:root <<EOF
# Managed by scripts/iac — do not edit by hand.
# Consumed by ${_pub}.
MODEL_STATE_TIERS=${_TIERS}
MODEL_STATE_TIMEOUT=${IAC_MODEL_STATE_TIMEOUT:-3}
SOVEREIGN_OS_ROOT=/opt/sovereign-os
EOF

ensure_file "/etc/systemd/system/${_unit}" 0644 root:root <<EOF
# Managed by scripts/iac — do not edit by hand.
[Unit]
Description=sovereign-os — publish what the inference tiers actually serve
Documentation=https://github.com/cyberpunk042/sovereign-os/blob/main/scripts/iac/modules/86-model-state.sh
After=sovereign-logic-engine.service sovereign-oracle-core.service sovereign-router-embed.service sovereign-router-rerank.service

[Service]
Type=oneshot
EnvironmentFile=-/etc/sovereign-os/model-state-publish.env
ExecStart=/usr/bin/python3 ${_pub}
# /run/sovereign-os is the only thing written, and the catalog under /opt is
# read. ProtectSystem=strict makes everything else read-only.
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ProtectClock=true
ProtectHostname=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictRealtime=true
LockPersonality=true
MemoryDenyWriteExecute=true
# Loopback HTTP to the tiers. No AF_NETLINK here — unlike the vLLM units this is
# a plain urllib client with no torch.distributed underneath.
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
ReadWritePaths=/run/sovereign-os
TimeoutStartSec=${IAC_MODEL_STATE_TIMEOUT_START:-60}
EOF

ensure_file "/etc/systemd/system/${_timer}" 0644 root:root <<EOF
# Managed by scripts/iac — do not edit by hand.
[Unit]
Description=sovereign-os — refresh the served-model state the panels read

[Timer]
# Shortly after boot so the panels are right before anyone opens them, then on a
# cadence. Persistent=false: a missed run is worthless — this publishes CURRENT
# residency, and replaying an old one would assert a state that has passed.
OnBootSec=${IAC_MODEL_STATE_BOOT_SEC:-90}
OnUnitActiveSec=${IAC_MODEL_STATE_INTERVAL:-60}
AccuracySec=${IAC_MODEL_STATE_ACCURACY:-10}
Persistent=false

[Install]
WantedBy=timers.target
EOF
iac_daemon_reload

if [ "${IAC_MODEL_STATE_ENABLE:-1}" != 1 ]; then
  skip "state publisher installed; timer left disabled (set IAC_MODEL_STATE_ENABLE=1)"
  return 0 2>/dev/null || exit 0
fi

ensure_unit_state "${_timer}" enabled started

# ─── publish once now, and verify it actually landed ─────────────────────────
# Waiting up to a minute for the first timer fire would leave the converge unable
# to say whether this works. And a module that installs a publisher without
# checking it published is the same "reported the action, not the machine"
# pattern this whole module exists to correct.
if [ "${IAC_DRY_RUN}" != 1 ]; then
  if run "publish-model-state" systemctl start "${_unit}"; then
    _n="$(python3 -c '
import json, sys
try:
    d = json.load(open("/run/sovereign-os/model-state.json"))
except Exception:
    print(-1); raise SystemExit
loaded = d.get("loaded") or {}
print(sum(len(v) for v in loaded.values()))' 2>/dev/null)"
    case "${_n}" in
      -1|"") fail "publisher ran but /run/sovereign-os/model-state.json is unreadable" ;;
      0)     skip "publisher ran; no tier is currently serving, so nothing is claimed loaded" ;;
      *)     ok "published ${_n} serving model(s) — panels now read runtime, not catalog" ;;
    esac
  else
    fail "could not run ${_unit} — panels stay on catalog candidates"
  fi
fi
