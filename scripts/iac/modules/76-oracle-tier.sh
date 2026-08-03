#!/usr/bin/env bash
# Oracle tier — gpt-oss-120b on the RTX PRO 6000
# gate: IAC_ENABLE_ORACLE
#
# WHY
#   The RTX PRO 6000 Blackwell (96 GiB) contributes nothing. Module 72 put a 30B
#   on the RTX 5090; this card is bigger and idle, and sovereign-oracle-core
#   ships as a unit waiting for weights.
#
#   gpt-oss-120b is not a guess. models/catalog.yaml records it PROMOTED to
#   verified-real on 2026-07-28 — "weights pulled and served on SAIN-01, bench
#   gate passed", measured on THIS card at 199.76 tok/s decode, TTFT 0.036 s,
#   918 tok/s aggregate under concurrency, on vLLM 0.26.0 with MXFP4/Marlin. It
#   has run here before; this module makes that reproducible.
#
# WHAT THE ORACLE UNIT ALREADY GETS RIGHT
#   Unlike sovereign-logic-engine, it is written for a host-resident process:
#   no `podman stop` in ExecStop, TimeoutStartSec=600, HOME already relocated to
#   /var/lib/sovereign-os/oracle-cache, and ReadWritePaths covering
#   /var/lib/sovereign-os. So it needs an env file and weights, not the four
#   drop-in repairs the Logic tier did.
#
# shellcheck shell=bash

_venv="${IAC_VLLM_VENV:-/opt/sovereign-os/venv/vllm}"
_py="${_venv}/bin/python"
_model_id="${IAC_ORACLE_MODEL_ID:-gpt-oss-120b}"
_models_dir="${IAC_VLLM_MODELS_DIR:-/mnt/vault/models}"
_model="${IAC_ORACLE_MODEL:-${_models_dir}/${_model_id}}"
_proxy_id="${IAC_ORACLE_PROXY_ID:-gpu-oracle}"

if [ ! -x "${_py}" ] || ! "${_py}" -c 'import vllm' >/dev/null 2>&1; then
  skip "vllm not installed — module 72 provisions the shared venv"
  return 0 2>/dev/null || exit 0
fi

# Pin to the PRO 6000 BY NAME. The Logic tier already showed why: the 5090 is
# index 1 here, so a hard-coded 0 would have been wrong for it — and is right for
# this card only by coincidence of PCI order. CUDA_DEVICE_ORDER=PCI_BUS_ID makes
# the nvidia-smi index and CUDA's index the same thing.
_idx="$(nvidia-smi --query-gpu=index,name --format=csv,noheader 2>/dev/null \
  | awk -F', *' '/PRO 6000/{print $1; exit}')"
if [ -z "${_idx}" ]; then
  skip "no RTX PRO 6000 found — this module targets that card specifically"
  return 0 2>/dev/null || exit 0
fi
iac_info "oracle → GPU ${_idx} (PRO 6000), model ${_model_id}"

_cfg_before="$(cat /etc/sovereign-os/inference-oracle-core.env 2>/dev/null | sha256sum)"

ensure_dir /etc/sovereign-os 0755 root:root
ensure_file /etc/sovereign-os/inference-oracle-core.env 0644 root:root <<EOF
# Managed by scripts/iac — do not edit by hand.
# Oracle tier: gpt-oss-120b, host-resident vLLM on the RTX PRO 6000.
ORACLE_MODEL=${_model}
ORACLE_HOST=127.0.0.1
ORACLE_PORT=${IAC_ORACLE_PORT:-8083}
ORACLE_KV_CACHE_DTYPE=${IAC_ORACLE_KV_DTYPE:-fp8}
ORACLE_QUANTIZATION=${IAC_ORACLE_QUANT:-nvfp4}
ORACLE_VRAM_REQUIRED_GIB=${IAC_ORACLE_VRAM_MIN:-63}
CUDA_DEVICE_ORDER=PCI_BUS_ID
CUDA_VISIBLE_DEVICES=${_idx}
PATH=${_venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HF_HOME=/var/lib/sovereign-os/hf
XDG_CACHE_HOME=/var/lib/sovereign-os/cache
VLLM_CACHE_ROOT=/var/lib/sovereign-os/cache/vllm-oracle
# Both nvcc routes, closed up front rather than one restart-loop at a time. The
# Logic tier hit these in sequence: flashinfer ships JIT-only and needs a
# compiler that is not installed, and apt's CUDA 12.4 is too old for sm_120 to
# help. Triton is already present and compiles with its own LLVM.
VLLM_USE_FLASHINFER_SAMPLER=${IAC_VLLM_FLASHINFER_SAMPLER:-0}
# Flags the backend class does not model, via the passthrough added for this:
#   --served-model-name  gatewayd's proxy relay forwards the client's model
#                        field verbatim, so the served id must equal the proxy id
#   --attention-backend  the second nvcc route
#   --reasoning-parser   gpt-oss emits chain-of-thought; unparsed it becomes the
#                        answer (vllm/reasoning/__init__.py registers it as
#                        openai_gptoss)
ORACLE_EXTRA_ARGS=--served-model-name ${_proxy_id} --attention-backend ${IAC_VLLM_ATTENTION_BACKEND:-TRITON_ATTN} --reasoning-parser ${IAC_ORACLE_REASONING_PARSER:-openai_gptoss}
EOF

# ─── weights ─────────────────────────────────────────────────────────────────
# Completeness, not mere presence — see weights_complete() in lib/iac.sh. A 63 GiB
# download that stops halfway leaves 13 of 14 shards behind, which two earlier
# versions of this check both accepted.
_have=0
if weights_complete "${_model}" 2>/dev/null; then _have=1; fi

if [ "${_have}" = 1 ]; then
  ok "weights present: ${_model} ($(du -sh "${_model}" 2>/dev/null | cut -f1))"
elif [ "${IAC_ORACLE_FETCH_MODEL:-0}" != 1 ]; then
  skip "no weights at ${_model} — set IAC_ORACLE_FETCH_MODEL=1 to download (~63 GiB)"
elif [ "${IAC_DRY_RUN}" = 1 ]; then
  changed "would fetch ${_model_id} (~63 GiB)"
else
  iac_info "fetching ${_model_id} — ~63 GiB, this takes a long while"
  _pull="${IAC_SOURCE_RESOLVED_DIR:-${IAC_SOURCE_DIR:-}}/scripts/models/pull.sh"
  [ -f "${_pull}" ] || _pull=/opt/sovereign-os/scripts/models/pull.sh
  if PATH="${_venv}/bin:${PATH}" SOVEREIGN_OS_MODELS_DIR="${_models_dir}" \
     run "pull-oracle" bash "${_pull}" "${_model_id}"; then
    if weights_complete "${_model}" 2>/dev/null; then
      changed "fetched ${_model_id} → ${_model}"
      _have=1
    else
      fail "pull.sh exited 0 but ${_model} is still incomplete: $(weights_complete "${_model}" 2>&1 >/dev/null)"
    fi
  else
    fail "could not fetch ${_model_id}"
  fi
fi

# ─── activation ──────────────────────────────────────────────────────────────
if [ "${_have}" != 1 ]; then
  skip "no usable weights — not enabling a tier with nothing to serve"
elif [ "${IAC_ORACLE_ENABLE_UNIT:-0}" != 1 ]; then
  skip "weights present; unit left disabled (set IAC_ORACLE_ENABLE_UNIT=1 to serve)"
else
  ensure_unit_state sovereign-oracle-core.service enabled started
  # Same restart-on-config-change the Logic tier needed: ensure_unit_state
  # "started" will not restart a unit that is already active with stale env.
  _cfg_now="$(cat /etc/sovereign-os/inference-oracle-core.env 2>/dev/null | sha256sum)"
  if [ "${_cfg_before}" != "${_cfg_now}" ] \
     && systemctl is-active --quiet sovereign-oracle-core.service 2>/dev/null \
     && [ "${IAC_DRY_RUN}" != 1 ]; then
    if run "restart-oracle" systemctl restart sovereign-oracle-core.service; then
      changed "restarted sovereign-oracle-core onto the new configuration"
    else
      fail "configuration changed but sovereign-oracle-core would not restart"
    fi
  fi
fi
