#!/usr/bin/env bash
# scripts/hooks/post-install/open-computer-install.sh
#
# Provision the open-computer QEMU AI-sandbox (SDD-706) at first boot and point its
# LLM backend at the LOCAL vLLM endpoint (SDD-702). open-computer (Mintplex-Labs,
# AGPL-3.0) is a QEMU virtual machine (Debian guest + XFCE + Chromium) an AI agent
# drives; its web UI is served per-agent from base port 9800. It needs system
# QEMU/KVM + OVMF + Node, a cloned+built CLI, and a ~3GB base.qcow2 — none reachable
# during the image build (no network at postinst), so this runs at FIRST BOOT.
#
# BEST-EFFORT / NON-FATAL: missing network / apt / npm / git / KVM each log a clear
# message + clean skip; the ~3GB base-image pull is resumable (curl -C -). Installed-
# off: it provisions everything but does NOT start the VM — `sovereign-osctl
# open-computer on` does. Idempotent (a built CLI + present base image is a no-op).
# VM-tolerant at the UNIT level, but nested KVM is usually absent on a VM — the hook
# provisions the software regardless and the runtime simply won't accelerate without
# /dev/kvm (surfaced by `open-computer doctor`).
#
# AGPL note: the open-computer tree is CLONED from upstream at first boot (the box
# fetches it itself) — it is not redistributed inside our image. Preconfig sets only
# the local model backend; no external channels/credentials are baked.
set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="open-computer-install"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "${STEP_ID}" "provision the open-computer QEMU AI-sandbox (installed-off)"
require_root

emit_oc_metric() {
  emit_metric sovereign_os_post_install_open_computer_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"$1\""
}

endpoint="$(profile_field provisioning.open_computer.endpoint)"
model_id="$(profile_field provisioning.open_computer.model_id)"
web_port="$(profile_field provisioning.open_computer.web_port)"
repo="$(profile_field provisioning.open_computer.repo)"
base_url="$(profile_field provisioning.open_computer.base_image_url)"
node_major="$(profile_field provisioning.open_computer.node_major)"
operator="$(profile_field provisioning.operator.username)"
: "${endpoint:=http://127.0.0.1:8000/v1}"
: "${model_id:=local-oracle}"
: "${web_port:=9800}"
: "${repo:=https://github.com/Mintplex-Labs/anything-llm}"
: "${node_major:=22}"
: "${operator:=operator}"

OC_ROOT="/var/lib/sovereign-os/open-computer"
OC_SRC="${OC_ROOT}/src"                 # the sparse anything-llm checkout
OC_APP="${OC_SRC}/open-computer"        # the open-computer subdir (CLI + services)
OC_BASE="${OC_ROOT}/base_image"         # OPEN_COMPUTER_BASE_DIR (base.qcow2 + efi-vars.fd)
OC_AGENTS="${OC_ROOT}/agents"           # OPEN_COMPUTER_AGENTS_DIR (per-agent overlays)
ENV_FILE="/etc/sovereign-os/open-computer.env"

# ---- idempotency: CLI built + base image present ----
if [ -x "${OC_APP}/open-computer" ] && [ -s "${OC_BASE}/base.qcow2" ]; then
  log_info "open-computer already provisioned (CLI built + base image present) — no-op"
  emit_oc_metric already-present
  exit 0
fi

# ---- (1) system QEMU/KVM + OVMF + git ----
export DEBIAN_FRONTEND=noninteractive
if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
  log_info "installing QEMU/KVM + OVMF"
  apt-get install -y --no-install-recommends qemu-system-x86 qemu-utils ovmf git >/dev/null 2>&1 \
    || { log_warn "qemu/ovmf install failed (no network?) — deferred (resumable post-flash)"; emit_oc_metric no-qemu; exit 0; }
fi
if [ ! -e /dev/kvm ]; then
  log_warn "/dev/kvm absent (no hardware virt / running in a VM without nested KVM) — provisioning software anyway; the VM won't accelerate until KVM is available"
fi
# The runtime runs as the operator — it needs the kvm group for /dev/kvm.
getent group kvm >/dev/null 2>&1 && usermod -aG kvm "${operator}" 2>/dev/null || true

# ---- (2) Node (reuse or install NodeSource) ----
if ! command -v node >/dev/null 2>&1; then
  log_info "installing NodeSource ${node_major}.x for the open-computer CLI"
  if command -v curl >/dev/null 2>&1 \
       && curl -fsSL "https://deb.nodesource.com/setup_${node_major}.x" -o /tmp/oc-node.sh 2>/dev/null \
       && bash /tmp/oc-node.sh >/dev/null 2>&1 \
       && apt-get install -y nodejs >/dev/null 2>&1; then
    rm -f /tmp/oc-node.sh
  else
    log_warn "node install failed — deferred (resumable post-flash)"; emit_oc_metric no-node; exit 0
  fi
fi

install -d -m 750 "${OC_ROOT}" "${OC_BASE}" "${OC_AGENTS}"

# ---- (3) sparse-clone the open-computer subdir + build the CLI ----
if [ ! -x "${OC_APP}/open-computer" ]; then
  if [ ! -d "${OC_SRC}/.git" ]; then
    log_info "sparse-cloning open-computer from ${repo}"
    if ! git clone --filter=blob:none --sparse "${repo}" "${OC_SRC}" >/dev/null 2>&1; then
      log_warn "git clone failed (no network?) — deferred (resumable post-flash)"; emit_oc_metric clone-failed; exit 0
    fi
    git -C "${OC_SRC}" sparse-checkout set open-computer >/dev/null 2>&1 || true
  fi
  if [ -d "${OC_APP}/cli" ]; then
    log_info "building the open-computer CLI (npm install + build)"
    ( cd "${OC_APP}/cli" && npm install >/dev/null 2>&1 && npm run build >/dev/null 2>&1 ) \
      || log_warn "CLI build hiccup — the wrapper may still run via ts-node (non-fatal)"
  fi
fi

# ---- (4) base image (~3GB tar → base.qcow2 + efi-vars.fd) — RESUMABLE ----
# Upstream's fetch-base-image.sh is NOT resumable; we pull the same CDN asset with
# curl -C - + sha256 verify so a dropped multi-GB download resumes instead of restarting.
if [ ! -s "${OC_BASE}/base.qcow2" ] && [ -n "${base_url}" ]; then
  log_info "downloading the open-computer base image (~3GB, resumable) from ${base_url}"
  tar_dst="${OC_BASE}/base-image.tar"
  if command -v curl >/dev/null 2>&1 && curl -fL -C - --retry 3 -o "${tar_dst}" "${base_url}" 2>/dev/null; then
    # sha256 sidecar (best-effort verify — a mismatch aborts the extract, keeps the .tar for a retry)
    if curl -fsSL -o "${tar_dst}.sha256" "${base_url}.sha256" 2>/dev/null; then
      exp="$(awk '{print $1}' "${tar_dst}.sha256" 2>/dev/null)"
      got="$(sha256sum "${tar_dst}" 2>/dev/null | awk '{print $1}')"
      if [ -n "${exp}" ] && [ "${exp}" != "${got}" ]; then
        log_warn "base image sha256 mismatch (exp ${exp:0:12}… got ${got:0:12}…) — keeping .tar for resume; not extracting"
        emit_oc_metric base-image-bad-sha; exit 0
      fi
    fi
    tar -xf "${tar_dst}" -C "${OC_BASE}" 2>/dev/null && rm -f "${tar_dst}" "${tar_dst}.sha256" \
      && log_info "base image extracted → ${OC_BASE}" \
      || log_warn "base image extract hiccup (non-fatal)"
  else
    log_warn "base image download incomplete (no network?) — resumable via 'sovereign-osctl open-computer install'"
    emit_oc_metric base-image-incomplete; exit 0
  fi
fi

# ---- (5) LLM preconfig (env the interface-service reads) ----
# 127.0.0.1 on the HOST is auto-rewritten to the QEMU user-net gateway 10.0.2.2 for the
# guest by open-computer, so the host-local vLLM endpoint is reachable from the VM.
install -d -m 755 /etc/sovereign-os
cat > "${ENV_FILE}" <<ENV
# /etc/sovereign-os/open-computer.env — open-computer LLM backend (SDD-706). Points at
# the LOCAL vLLM endpoint; OPENAI_API_KEY may stay empty for a keyless local server.
HOME=${OC_ROOT}
OPENAI_BASE_URL=${endpoint}
OPENAI_MODEL=${model_id}
OPENAI_API_KEY=
PORT=${web_port}
OPEN_COMPUTER_BASE_DIR=${OC_BASE}
OPEN_COMPUTER_AGENTS_DIR=${OC_AGENTS}
ENV

chown -R "${operator}:${operator}" "${OC_ROOT}" 2>/dev/null || true

# ---- (6) stage the runtime unit installed-off ----
if [ -f "${__REPO_ROOT}/systemd/system/sovereign-open-computer.service" ]; then
  install -m 644 "${__REPO_ROOT}/systemd/system/sovereign-open-computer.service" /etc/systemd/system/ 2>/dev/null || true
  systemctl daemon-reload 2>/dev/null || true
fi

log_info "open-computer installed-off — UI base port ${web_port}, LLM → ${endpoint}; turn on: sovereign-osctl open-computer on"
emit_oc_metric installed
exit 0
