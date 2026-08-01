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
  _ver="$("${_py}" -c 'import vllm; print(vllm.__version__)' 2>/dev/null)"
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
      _ver="$("${_py}" -c 'import vllm; print(vllm.__version__)' 2>/dev/null)"
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
_logic_idx="$(nvidia-smi --query-gpu=index,name --format=csv,noheader 2>/dev/null \
  | awk -F', *' '/5090/{print $1; exit}')"
if [ -z "${_logic_idx}" ]; then
  iac_info "no RTX 5090 found by name — leaving CUDA_VISIBLE_DEVICES unset (vLLM would see every GPU)"
fi

ensure_dir /etc/sovereign-os 0755 root:root
ensure_file /etc/sovereign-os/inference-logic-engine.env 0644 root:root <<EOF
# Managed by scripts/iac — do not edit by hand.
# Host-resident vLLM for the Logic tier (SDD-011).
SOVEREIGN_OS_LOGIC_BACKEND=vllm_host
LOGIC_MODEL=${IAC_VLLM_LOGIC_MODEL:-/mnt/vault/models/qwen3-coder}
LOGIC_HOST=127.0.0.1
LOGIC_PORT=8082
LOGIC_GPU_MEMORY_UTILIZATION=${IAC_VLLM_GPU_UTIL:-0.90}
LOGIC_MAX_MODEL_LEN=${IAC_VLLM_MAX_LEN:-32768}
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

# ─── weights + activation, both deliberately withheld ────────────────────────
_model="${IAC_VLLM_LOGIC_MODEL:-/mnt/vault/models/qwen3-coder}"
if [ ! -d "${_model}" ]; then
  skip "no weights at ${_model} — set IAC_VLLM_LOGIC_MODEL, or fetch a checkpoint, before enabling the tier"
elif [ "${IAC_VLLM_ENABLE_UNIT:-0}" != 1 ]; then
  skip "weights present; unit left disabled (set IAC_VLLM_ENABLE_UNIT=1 to serve)"
elif [ "${_have_vllm}" != 1 ]; then
  skip "weights present but vllm is not importable — not enabling a unit that cannot start"
else
  ensure_unit_state sovereign-logic-engine.service enabled started
fi
