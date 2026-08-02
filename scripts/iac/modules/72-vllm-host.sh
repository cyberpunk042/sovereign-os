#!/usr/bin/env bash
# host-resident vLLM for the GPU inference tier
# gate: IAC_ENABLE_VLLM
#
# WHY THIS EXISTS
#   This box ships a complete three-tier GPU inference architecture — a router
#   on :8080, sovereign-logic-engine on the RTX 5090, sovereign-oracle-core on
#   the RTX PRO 6000 — as systemd units, all DISABLED, whose launchers need an
#   engine that was never installed. So both GPUs (96 GiB + 32 GiB) sat idle and
#   sovereign-gatewayd's pure-Rust CPU decoder became the only inference path by
#   default rather than by design, at ~1 tok/s.
#
#   start-logic-engine.sh already supports three backends: `vllm` (podman),
#   `vllm_host` (host-resident) and `llama_cpp`. Host-resident is chosen here:
#   it mirrors how the Oracle Core path already runs, and it avoids adding a
#   container runtime to a sovereign-posture box. Neither podman nor docker is
#   installed and this module does not install one.
#
# WHAT THIS MODULE DOES AND DOES NOT DO
#   It provisions the ENGINE and its unit configuration. It does NOT download
#   model weights and does NOT start the tier: a 30B checkpoint is tens of GB and
#   which model to serve is an operator decision, not a converge side effect.
#   The unit stays disabled until IAC_VLLM_ENABLE_UNIT=1 AND weights exist.
#
# shellcheck shell=bash

_venv="${IAC_VLLM_VENV:-/opt/sovereign-os/venv/vllm}"
_py="${_venv}/bin/python"

# ─── prerequisites, checked rather than assumed ──────────────────────────────
# Python 3.14 is the system interpreter here and looked like a hard blocker:
# vLLM historically trails new releases. It is not one. vllm 0.26.0 declares
# requires_python <3.15,>=3.10 and ships cp38-abi3 wheels (stable ABI, so one
# wheel covers every 3.x), and torch 2.13.0 publishes real cp314 wheels. Both
# verified against PyPI before this module was written.
if ! command -v nvidia-smi >/dev/null 2>&1; then
  skip "no nvidia-smi — this host has no NVIDIA driver, nothing for vLLM to use"
  return 0 2>/dev/null || exit 0
fi
_drv="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)"
iac_info "nvidia driver ${_drv:-unknown}, python $(python3 -V 2>&1 | cut -d' ' -f2)"

# ─── the venv ────────────────────────────────────────────────────────────────
# Ubuntu marks the system interpreter EXTERNALLY-MANAGED (PEP 668), so vLLM must
# NOT be pip-installed into it. A venv is the correct answer, not
# --break-system-packages: an apt upgrade of python3 would otherwise fight a
# multi-GB torch install for ownership of the same site-packages.
if [ ! -x "${_py}" ]; then
  if [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "would create venv ${_venv}"
  else
    ensure_dir "$(dirname "${_venv}")" 0755 root:root
    if run "venv-create" python3 -m venv "${_venv}"; then
      changed "venv created at ${_venv}"
    else
      fail "could not create venv at ${_venv} — is python3-venv installed?"
      return 0 2>/dev/null || exit 0
    fi
  fi
else
  ok "venv ${_venv}"
fi

# ─── vLLM itself ─────────────────────────────────────────────────────────────
# ~300 MB wheel plus a torch/CUDA stack of several GB. Idempotent: once `import
# vllm` succeeds this is a no-op, so a re-converge does not re-download.
_have_vllm=0
if [ -x "${_py}" ] && "${_py}" -c 'import vllm' >/dev/null 2>&1; then
  _have_vllm=1
fi

if [ "${_have_vllm}" = 1 ]; then
  # 2>/dev/null on the PROBE, not just the import test: vllm prints CUDA
  # warnings at import, and they landed mid-sentence in the converge report.
  _ver="$("${_py}" -c 'import vllm; print(vllm.__version__)' 2>/dev/null | tail -1)"
  ok "vllm ${_ver:-installed} in ${_venv}"
elif [ "${IAC_DRY_RUN}" = 1 ]; then
  changed "would pip install vllm into ${_venv} (multi-GB download)"
else
  iac_info "installing vllm — several GB, this takes a while"
  # --upgrade pip first: the venv seeds an old pip that may not understand the
  # abi3/cp314 wheel tags this install depends on.
  run "pip-upgrade" "${_py}" -m pip install --quiet --upgrade pip setuptools wheel || true
  if run "pip-vllm" "${_py}" -m pip install --quiet vllm; then
    if "${_py}" -c 'import vllm' >/dev/null 2>&1; then
      _ver="$("${_py}" -c 'import vllm; print(vllm.__version__)' 2>/dev/null | tail -1)"
      changed "vllm ${_ver:-?} installed into ${_venv}"
      _have_vllm=1
    else
      # pip can exit 0 having installed something that cannot import — a CUDA
      # or ABI mismatch shows up here and nowhere else.
      fail "pip reported success but 'import vllm' fails — check the wheel matches this python/CUDA"
    fi
  else
    fail "pip install vllm failed — see the converge log above"
  fi
fi

# ─── unit configuration ──────────────────────────────────────────────────────
# The shipped unit reads EnvironmentFile=-/etc/sovereign-os/inference-logic-engine.env
# (the leading `-` makes it optional). This is where the backend selection and
# the card pin live.
#
# CUDA_VISIBLE_DEVICES pins the tier to ONE card. The profile puts Logic on the
# RTX 5090; index is resolved from nvidia-smi rather than hard-coded, because
# PCI enumeration order is not guaranteed to match the profile's intent.
#
# CUDA_DEVICE_ORDER=PCI_BUS_ID is not decoration. nvidia-smi enumerates by PCI
# bus; the CUDA runtime defaults to FASTEST_FIRST, so an index resolved from
# nvidia-smi is not guaranteed to name the same card to CUDA. vLLM warns about
# exactly this on a mixed-GPU box ("Detected different devices in the system …
# please make sure to set CUDA_DEVICE_ORDER=PCI_BUS_ID"), and this IS one: an
# RTX PRO 6000 Blackwell beside an RTX 5090. Measured here the two orderings
# agree — PRO 6000 at 0, 5090 at 1 — but that is a coincidence of the current
# ranking, not a guarantee, and a driver update could silently swap the cards
# under a pin that still looks right. Forcing PCI order makes the resolution
# below sound by construction rather than by luck.
_logic_idx="$(nvidia-smi --query-gpu=index,name --format=csv,noheader 2>/dev/null \
  | awk -F', *' '/5090/{print $1; exit}')"
if [ -z "${_logic_idx}" ]; then
  iac_info "no RTX 5090 found by name — leaving CUDA_VISIBLE_DEVICES unset (vLLM would see every GPU)"
fi

# Resolve the model path BEFORE writing the env file. These were computed in the
# weights section below on the first version, so the env file fell back to its
# own hard-coded default and the unit was pointed at /mnt/vault/models/qwen3-coder
# while the fetch correctly populated the Nemotron directory. vLLM then treated
# the missing path as a HuggingFace repo id and died with
#     OSError: Repo id must be in the form 'repo_name' or 'namespace/repo_name'
# One value, computed once, used by both — a second fallback is a second source
# of truth.
_model_id="${IAC_VLLM_MODEL_ID:-Nemotron-3-Nano-Omni-30B-Reasoning-NVFP4}"
_models_dir="${IAC_VLLM_MODELS_DIR:-/mnt/vault/models}"
_model="${IAC_VLLM_LOGIC_MODEL:-${_models_dir}/${_model_id}}"

ensure_dir /etc/sovereign-os 0755 root:root
ensure_file /etc/sovereign-os/inference-logic-engine.env 0644 root:root <<EOF
# Managed by scripts/iac — do not edit by hand.
# Host-resident vLLM for the Logic tier (SDD-011).
SOVEREIGN_OS_LOGIC_BACKEND=vllm_host
LOGIC_MODEL=${_model}
LOGIC_HOST=127.0.0.1
LOGIC_PORT=8082
LOGIC_GPU_MEMORY_UTILIZATION=${IAC_VLLM_GPU_UTIL:-0.90}
LOGIC_MAX_MODEL_LEN=${IAC_VLLM_MAX_LEN:-32768}
# This checkpoint ships its own modeling code (modeling_nemotron_h.py,
# configuration_radio.py, processing.py …) and vLLM refuses to load it without
# an explicit opt-in. Setting this EXECUTES code from the checkpoint directory,
# so it is defensible only because the weights come from the catalog's declared
# hf_repo_id (nvidia/…) via scripts/models/pull.sh, not from an arbitrary path.
LOGIC_TRUST_REMOTE_CODE=${IAC_VLLM_TRUST_REMOTE_CODE:-1}
CUDA_DEVICE_ORDER=PCI_BUS_ID
${_logic_idx:+CUDA_VISIBLE_DEVICES=${_logic_idx}}
# The launcher invokes a bare \`python3\`, so the venv must come first on PATH.
PATH=${_venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# vLLM/HF write caches; ProtectSystem=strict makes everything else read-only.
HF_HOME=/var/lib/sovereign-os/hf
XDG_CACHE_HOME=/var/lib/sovereign-os/cache
EOF

ensure_dir /var/lib/sovereign-os/hf 0750 root:root
ensure_dir /var/lib/sovereign-os/cache 0750 root:root

# The shipped unit is written for the podman backend and hard-codes
#     ExecStop=/usr/bin/podman stop vllm-logic_engine
# On a host with no podman that stop command cannot succeed, so systemd would
# report a failure on every clean shutdown. Clearing it (empty assignment) lets
# the default SIGTERM to the main process do the work, which is correct for a
# host-resident process. ReadWritePaths re-opens exactly the cache directories
# ProtectSystem=strict closes, and nothing else.
ensure_dropin sovereign-logic-engine.service 10-vllm-host <<EOF
# Managed by scripts/iac — do not edit by hand.
[Service]
ExecStop=
ReadWritePaths=/var/lib/sovereign-os/hf /var/lib/sovereign-os/cache
# A multi-GB checkpoint load on a cold page cache exceeds the shipped 180s.
TimeoutStartSec=900
EOF

# ─── weights ─────────────────────────────────────────────────────────────────
# (_model_id / _models_dir / _model are resolved above, before the env file.)
# Fetched with the repo's OWN downloader (scripts/models/pull.sh) rather than a
# hand-rolled curl: it resolves hf_repo_id from models/catalog.yaml, so the
# thing that lands on disk is the thing the catalog claims, and it emits the
# Layer B pull metrics. The venv goes first on PATH because the `hf` CLI it
# needs lives there, not on the system.
#
# Default model: Nemotron-3-Nano-Omni-30B-A3B-Reasoning-NVFP4. Chosen because
# start-logic-engine.sh's own header records it MEASURED on this exact card —
# "2026-07-28 on the RTX 5090 with Nemotron-3-Nano-Omni-30B NVFP4: 314.41 tok/s
# decode, TTFT 0.173s" — and because NVFP4 is native to Blackwell tensor cores,
# which both cards here are. 30B total but A3B (~3B active per token), so it is
# an MoE: 22.4 GiB on disk, 24 GiB VRAM, inside the 5090's 32 GiB at 0.90
# utilization with room for a 32k KV cache.

# "Has weights" means a loadable checkpoint, not merely a directory: an
# interrupted download leaves the directory behind, and a bare `-d` test would
# call that provisioned and then hand vLLM something it cannot open.
_have_weights=0
if [ -f "${_model}/config.json" ] && \
   ls "${_model}"/*.safetensors >/dev/null 2>&1; then
  _have_weights=1
fi

if [ "${_have_weights}" = 1 ]; then
  ok "weights present: ${_model} ($(du -sh "${_model}" 2>/dev/null | cut -f1))"
elif [ "${IAC_VLLM_FETCH_MODEL:-0}" != 1 ]; then
  skip "no weights at ${_model} — set IAC_VLLM_FETCH_MODEL=1 to download (~22 GiB)"
elif [ "${IAC_DRY_RUN}" = 1 ]; then
  changed "would fetch ${_model_id} (~22 GiB) into ${_models_dir}"
else
  iac_info "fetching ${_model_id} — ~22 GiB, this takes a while"
  # Prefer the checkout's downloader over the payload's — module 15 keeps it
  # current, and this is the same tree the catalog entry is read from.
  _pull="${IAC_SOURCE_RESOLVED_DIR:-${IAC_SOURCE_DIR:-}}/scripts/models/pull.sh"
  [ -f "${_pull}" ] || _pull=/opt/sovereign-os/scripts/models/pull.sh
  if PATH="${_venv}/bin:${PATH}" SOVEREIGN_OS_MODELS_DIR="${_models_dir}" \
     run "pull-model" bash "${_pull}" "${_model_id}"; then
    if [ -f "${_model}/config.json" ] && ls "${_model}"/*.safetensors >/dev/null 2>&1; then
      changed "fetched ${_model_id} → ${_model}"
      _have_weights=1
    else
      fail "pull.sh succeeded but ${_model} has no config.json + safetensors"
    fi
  else
    fail "could not fetch ${_model_id} — check the log; some NVIDIA repos need HUGGINGFACE_HUB_TOKEN"
  fi
fi

# ─── activation, deliberately withheld ───────────────────────────────────────
if [ "${_have_weights}" != 1 ]; then
  skip "no usable weights at ${_model} — not enabling a tier with nothing to serve"
elif [ "${IAC_VLLM_ENABLE_UNIT:-0}" != 1 ]; then
  skip "weights present; unit left disabled (set IAC_VLLM_ENABLE_UNIT=1 to serve)"
elif [ "${_have_vllm}" != 1 ]; then
  skip "weights present but vllm is not importable — not enabling a unit that cannot start"
else
  ensure_unit_state sovereign-logic-engine.service enabled started
fi
