#!/usr/bin/env bash
# Router tier — embedder + cross-encoder reranker on the RTX 4090 eGPU
# gate: IAC_ENABLE_ROUTER
#
# WHY
#   The eGPU was fitted 2026-08-14 and contributes nothing: an idle 24 GiB card
#   beside a 5090 running Logic and a PRO 6000 running Oracle. The catalog's
#   fourth tier — `router`, the models that do not generate text — had never been
#   served at all, and that absence is load-bearing: retrieval on this box is
#   BM25 + char-n-gram (gatewayd main.rs:75), which is lexical only. Nothing here
#   can tell that "the gateway sends traffic to the graphics cards" and "the
#   sovereign gateway routes requests to GPU tiers" mean the same thing.
#
#   Measured on this card while writing this module, bge-m3 puts that pair at
#   cosine 0.7278 and an unrelated French sentence at 0.3273. That is the
#   capability the box was missing.
#
# WHY THIS CARD
#   sain-01.yaml declares the 4090 as role: egpu, OcuLink-to-M.2, PCIe 4.0 x4,
#   350 W — "host-resident by default". The x4 link is the reason this tier and
#   not a generation tier: x4 slows WEIGHT LOADING, but decode never crosses the
#   bus once weights are resident, and these two models are ~2 GiB each. The
#   profile's own suggestion of a speculative-decoding draft does not work here —
#   vLLM loads the draft in the same process on the same GPU as its target, so a
#   draft on a separate card is not a configuration vLLM offers.
#
# WHY TWO UNITS
#   vLLM serves one model per process. An embedder and a reranker are different
#   models with different heads, so the tier is two services sharing one card:
#     :8084  gpu-embed   /v1/embeddings
#     :8085  gpu-rerank  /rerank, /v1/score
#   Measured together: 3745 MiB of 24564 on the 4090, both idle-resident.
#
# WHAT THIS DOES NOT DO
#   It does not make anything USE them. gatewayd has no /v1/embeddings route
#   today (it answers "no route for POST /v1/embeddings") even though the M033 /
#   M034 / M060 compatibility lint tests assert the gateway exposes one. Serving
#   the models is the half that belongs in IaC; the gateway route is Rust and is
#   tracked separately. Until then this tier is reachable directly on its ports
#   and by nothing else — stated plainly rather than left for someone to discover.
#
#   It is also deliberately NOT added to module 84's proxy table. That registry
#   holds CHAT backends, and its "auto" designation falls back to whichever tier
#   registered last. An embedder in that table could become the target of every
#   request that expresses no model preference — a pooling model asked for a chat
#   completion. Embeddings need their own route, not a seat among the generators.
#
# shellcheck shell=bash

_venv="${IAC_VLLM_VENV:-/opt/sovereign-os/venv/vllm}"
_py="${_venv}/bin/python"
_models_dir="${IAC_VLLM_MODELS_DIR:-/mnt/vault/models}"
_libdir="${IAC_GPU_ROUTE_LIBDIR:-/usr/local/lib/sovereign-os}"
_launcher="${_libdir}/start-router-tier.sh"

if [ ! -x "${_py}" ] || ! "${_py}" -c 'import vllm' >/dev/null 2>&1; then
  skip "vllm not installed — module 72 provisions the shared venv"
  return 0 2>/dev/null || exit 0
fi

# Pin BY NAME, never by index. On this box the cards enumerate PRO 6000 / 5090 /
# 4090, but that is PCI order, not a guarantee — and CUDA's own default ordering
# is FASTEST_FIRST, which would disagree. CUDA_DEVICE_ORDER=PCI_BUS_ID in the env
# file makes the nvidia-smi index and the CUDA index the same thing.
_idx="$(nvidia-smi --query-gpu=index,name --format=csv,noheader 2>/dev/null \
  | awk -F', *' '/RTX 4090/{print $1; exit}')"
if [ -z "${_idx}" ]; then
  skip "no RTX 4090 found — this module targets the OcuLink eGPU specifically"
  return 0 2>/dev/null || exit 0
fi
iac_info "router → GPU ${_idx} (RTX 4090 eGPU, PCIe 4.0 x4)"

# ─── the launcher ─────────────────────────────────────────────────────────────
# Installed to /usr/local/lib for the same reason as gpu-route-apply.sh: the
# payload at /opt is dpkg-owned and only module 90 writes there, and 90 runs
# after this module.
_src="${IAC_SOURCE_RESOLVED_DIR:-${IAC_SOURCE_DIR:-}}/scripts/iac/assets/start-router-tier.sh"
if [ ! -f "${_src}" ]; then
  _self_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  _src="${_self_dir}/assets/start-router-tier.sh"
fi
if [ ! -f "${_src}" ]; then
  fail "start-router-tier.sh not found — cannot install the router launcher"
  return 0 2>/dev/null || exit 0
fi
ensure_dir "${_libdir}" 0755 root:root
ensure_file "${_launcher}" 0755 root:root < "${_src}"

# ─── one record per role ──────────────────────────────────────────────────────
# "<role>@<catalog-id>@<port>@<served-name>@<convert>". `convert` is empty for the
# embedder — bge-m3's config already declares its pooling head — and `classify`
# for the cross-encoder, which is a sequence-classification model vLLM has to be
# told to expose as a scorer.
_ROLES="embed@${IAC_ROUTER_EMBED_ID:-BAAI-bge-m3}@${IAC_ROUTER_EMBED_PORT:-8084}@${IAC_ROUTER_EMBED_NAME:-gpu-embed}@"
_ROLES="${_ROLES} rerank@${IAC_ROUTER_RERANK_ID:-BAAI-bge-reranker-v2-m3}@${IAC_ROUTER_RERANK_PORT:-8085}@${IAC_ROUTER_RERANK_NAME:-gpu-rerank}@classify"

ensure_dir /etc/sovereign-os 0755 root:root
ensure_dir /var/lib/sovereign-os/router-home 0755 root:root

for _rec in ${_ROLES}; do
  IFS='@' read -r _role _mid _port _served _convert <<<"${_rec}"
  _unit="sovereign-router-${_role}.service"
  _envf="/etc/sovereign-os/router-${_role}.env"
  _model="${_models_dir}/${_mid}"

  # BOTH files, not just the env file. The first version hashed only the env, so
  # when the fix for the crash-loop landed in the UNIT (a missing AF_NETLINK) the
  # hash was unchanged and the restart never fired — converge would have rewritten
  # the unit correctly and left the broken process running, reporting success.
  _cfg_files=("${_envf}" "/etc/systemd/system/${_unit}")
  _cfg_before="$(cat "${_cfg_files[@]}" 2>/dev/null | sha256sum)"

  ensure_file "${_envf}" 0644 root:root <<EOF
# Managed by scripts/iac — do not edit by hand.
# Router tier (${_role}): host-resident vLLM on the RTX 4090 eGPU.
ROUTER_MODEL=${_model}
ROUTER_SERVED_NAME=${_served}
ROUTER_HOST=127.0.0.1
ROUTER_PORT=${_port}
ROUTER_RUNNER=pooling
ROUTER_CONVERT=${_convert}
ROUTER_MAX_MODEL_LEN=${IAC_ROUTER_MAX_MODEL_LEN:-8192}
# ~2 GiB of weights on a 24 GiB card, and BOTH roles share it. vLLM's 0.90
# default would let whichever unit started first reserve the whole GPU for a KV
# cache a pooling runner does not use, and the second would then fail to
# allocate. Measured at this setting: 1864 + 1866 MiB resident.
ROUTER_GPU_MEMORY_UTILIZATION=${IAC_ROUTER_GPU_MEM_UTIL:-0.15}
CUDA_DEVICE_ORDER=PCI_BUS_ID
CUDA_VISIBLE_DEVICES=${_idx}
PATH=${_venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HOME=/var/lib/sovereign-os/router-home
HF_HOME=/var/lib/sovereign-os/hf
XDG_CACHE_HOME=/var/lib/sovereign-os/cache
VLLM_CACHE_ROOT=/var/lib/sovereign-os/cache/vllm-router-${_role}
# The nvcc routes the Logic tier hit one restart-loop at a time: flashinfer ships
# JIT-only and needs a compiler this host does not have.
VLLM_USE_FLASHINFER_SAMPLER=${IAC_VLLM_FLASHINFER_SAMPLER:-0}
EOF

  # ─── weights ───────────────────────────────────────────────────────────────
  # bge-m3 ships a single pytorch_model.bin and NO safetensors — which the old
  # safetensors-only weights_complete() called incomplete. It now accepts either
  # format; see lib/iac.sh.
  _have=0
  if weights_complete "${_model}" 2>/dev/null; then _have=1; fi

  if [ "${_have}" = 1 ]; then
    ok "weights present: ${_model} ($(du -sh "${_model}" 2>/dev/null | cut -f1))"
  elif [ "${IAC_ROUTER_FETCH_MODEL:-0}" != 1 ]; then
    skip "no weights at ${_model} — set IAC_ROUTER_FETCH_MODEL=1 to download (~2.2 GiB)"
  elif [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "would fetch ${_mid} (~2.2 GiB)"
  else
    iac_info "fetching ${_mid} — ~2.2 GiB"
    _pull="${IAC_SOURCE_RESOLVED_DIR:-${IAC_SOURCE_DIR:-}}/scripts/models/pull.sh"
    [ -f "${_pull}" ] || _pull=/opt/sovereign-os/scripts/models/pull.sh
    # Both repos carry an onnx/ tree for a runtime this box does not use; it is
    # roughly as large as the weights themselves.
    if PATH="${_venv}/bin:${PATH}" SOVEREIGN_OS_MODELS_DIR="${_models_dir}" \
       SOVEREIGN_OS_PULL_EXCLUDE="${IAC_ROUTER_PULL_EXCLUDE:-onnx/*,*.onnx,imgs/*,assets/*}" \
       run "pull-${_role}" bash "${_pull}" "${_mid}"; then
      if weights_complete "${_model}" 2>/dev/null; then
        changed "fetched ${_mid} → ${_model}"
        _have=1
      else
        fail "pull.sh exited 0 but ${_model} is still incomplete: $(weights_complete "${_model}" 2>&1 >/dev/null)"
      fi
    else
      fail "could not fetch ${_mid}"
    fi
  fi

  # ─── the unit ──────────────────────────────────────────────────────────────
  ensure_file "/etc/systemd/system/${_unit}" 0644 root:root <<EOF
# Managed by scripts/iac — do not edit by hand.
[Unit]
Description=sovereign-os Router tier (${_role}) — ${_mid} on the RTX 4090 eGPU
Documentation=https://github.com/cyberpunk042/sovereign-os/blob/main/scripts/iac/modules/78-router-tier.sh
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=-${_envf}
ExecStart=${_launcher}
Restart=on-failure
RestartSec=10s
# ~2 GiB over a x4 link, plus torch import. Generous rather than tight: a
# TimeoutStartSec that expires mid-load produces a restart loop that never
# finishes loading, which is indistinguishable from a broken model.
TimeoutStartSec=${IAC_ROUTER_TIMEOUT:-600}
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ProtectClock=true
ProtectHostname=true
ProtectKernelTunables=true
ProtectKernelModules=true
RestrictSUIDSGID=true
RestrictRealtime=true
LockPersonality=true
# AF_NETLINK is NOT optional, and its absence does not look like a sandbox
# problem. vLLM brings up a torch.distributed process group even for a single
# GPU, and gloo's TCP device enumerates interfaces with getifaddrs(), which on
# Linux is a NETLINK socket. Without it the engine dies at
#   RuntimeError: [enforce fail at gloo/transport/tcp/device.cc:186]
#   rv != -1. -1 vs -1. Address family not supported by protocol
# which reads like a network stack fault, not a missing unit directive. Both
# working tiers (logic, oracle) already carry it; this unit was written without
# it and crash-looped on first start.
RestrictNamespaces=false
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK
# torch and triton JIT-compile and mmap executable pages.
MemoryDenyWriteExecute=false
ReadWritePaths=/var/lib/sovereign-os /var/log/sovereign-os
ReadOnlyPaths=-${_models_dir}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

  # ─── activation ────────────────────────────────────────────────────────────
  if [ "${_have}" != 1 ]; then
    skip "${_role}: no usable weights — not enabling a tier with nothing to serve"
  elif [ "${IAC_ROUTER_ENABLE_UNIT:-0}" != 1 ]; then
    skip "${_role}: weights present; unit left disabled (set IAC_ROUTER_ENABLE_UNIT=1 to serve)"
  else
    iac_daemon_reload
    # Whether it was ALREADY running matters, and has to be sampled before
    # ensure_unit_state changes it. Without this the first converge reported both
    # "unit started" and "restarted onto the new configuration" for the same
    # unit: the config had obviously changed (it did not exist a moment earlier),
    # the unit was now active because we had just started it, so the
    # stale-environment restart fired against a process that was already running
    # the new environment. Harmless once, but restarting units that did not need
    # it is exactly what tripped the start-limit lockout before.
    # "activating" counts. A unit crash-looping under Restart=on-failure reports
    # activating/auto-restart, which `is-active --quiet` calls false — so a plain
    # is-active check would decide the unit was not running, skip the restart,
    # and leave it looping on the old configuration forever.
    case "$(systemctl show "${_unit}" -p ActiveState --value 2>/dev/null)" in
      active|activating|reloading) _was_active=1 ;;
      *)                           _was_active=0 ;;
    esac

    ensure_unit_state "${_unit}" enabled started

    # ensure_unit_state "started" will not restart a unit that is already active
    # holding a stale environment, so a config change has to say so explicitly.
    _cfg_now="$(cat "${_cfg_files[@]}" 2>/dev/null | sha256sum)"
    if [ "${_cfg_before}" != "${_cfg_now}" ] \
       && [ "${_was_active}" = 1 ] \
       && systemctl is-active --quiet "${_unit}" 2>/dev/null \
       && [ "${IAC_DRY_RUN}" != 1 ]; then
      # Clear the counter first. A unit that has been crash-looping may already be
      # at or near StartLimitBurst, and systemd then refuses the very restart that
      # carries the fix — the failure mode that once locked out the daemon being
      # repaired. reset-failed on a healthy unit is a no-op.
      systemctl reset-failed "${_unit}" >/dev/null 2>&1 || true
      if run "restart-${_role}" systemctl restart "${_unit}"; then
        changed "restarted ${_unit} onto the new configuration"
      else
        fail "configuration changed but ${_unit} would not restart"
      fi
    fi

    # ─── did it actually SERVE? ──────────────────────────────────────────────
    # systemd's "started" means the process was spawned, nothing more. Both
    # router units reported `changed unit ... started` on the first converge and
    # were dead twenty seconds later, crash-looping on a missing AF_NETLINK —
    # and the run still finished "0 failed". A tier module that does not check
    # its tier is serving is reporting on its own actions, not on the machine.
    if [ "${IAC_DRY_RUN}" != 1 ]; then
      _serving=0
      for _i in $(seq 1 "${IAC_ROUTER_WAIT_TRIES:-60}"); do
        if curl -fsS --max-time 3 "http://127.0.0.1:${_port}/v1/models" >/dev/null 2>&1; then
          _serving=1; break
        fi
        # A unit that has given up restarting will never serve; stop waiting for
        # it and say so, rather than burning the whole budget on a dead tier.
        if systemctl is-failed --quiet "${_unit}" 2>/dev/null; then break; fi
        [ "${_i}" = 1 ] && iac_info "waiting for ${_role} to load (~2.2 GiB over a x4 link)"
        sleep 2
      done
      if [ "${_serving}" = 1 ]; then
        _got="$(curl -fsS --max-time 5 "http://127.0.0.1:${_port}/v1/models" 2>/dev/null \
          | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"][0]["id"])' 2>/dev/null)"
        if [ "${_got}" = "${_served}" ]; then
          ok "${_role} serving '${_served}' on :${_port}"
        else
          fail "${_role} on :${_port} serves '${_got}', expected '${_served}'"
        fi
      else
        fail "${_role} unit is up but not serving on :${_port} — journalctl -u ${_unit}"
      fi
    fi
  fi
done
