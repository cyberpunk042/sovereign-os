#!/usr/bin/env bash
# scripts/hooks/post-install/openclaw-install.sh
#
# Provision the OpenClaw Node gateway daemon (SDD-705) at first boot and point it
# at the LOCAL OpenAI-compatible endpoint (the vLLM router/Oracle from SDD-702), so
# on-box agents run against the sovereign model with no external provider. OpenClaw
# needs Node (banded engines: >=22.22.3 <23 || >=24.15 <25 || >=25.9) + a global
# `npm install -g openclaw` — neither reachable during the image build (no network at
# postinst), so this runs at FIRST BOOT when the box has network.
#
# BEST-EFFORT / NON-FATAL: missing network / npm / a too-old Node each log a clear
# message + clean skip; fully resumable post-flash (`sovereign-osctl openclaw install`
# re-runs this). Installed-off: it renders config + installs the runtime unit but does
# NOT start the daemon — `sovereign-osctl openclaw on` does. Idempotent (a present,
# band-satisfying openclaw + rendered config is a no-op). VM-tolerant (a Node daemon
# runs fine on a VM — unlike the GPU hooks, this unit is NOT ConditionVirtualization=no).
#
# Preconfig only points at the local model + no external channels (SDD-703 D5 — never
# bake channel credentials). The operator adds WhatsApp/Telegram/etc. later.
set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="openclaw-install"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "${STEP_ID}" "provision the OpenClaw gateway daemon (installed-off)"
require_root

emit_oc_metric() {
  emit_metric sovereign_os_post_install_openclaw_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"$1\""
}

backend="$(profile_field provisioning.openclaw.backend)"
endpoint="$(profile_field provisioning.openclaw.endpoint)"
model_id="$(profile_field provisioning.openclaw.model_id)"
anthropic_endpoint="$(profile_field provisioning.openclaw.anthropic_endpoint)"
anthropic_model="$(profile_field provisioning.openclaw.anthropic_model)"
gw_port="$(profile_field provisioning.openclaw.gateway_port)"
node_major="$(profile_field provisioning.openclaw.node_major)"
operator="$(profile_field provisioning.operator.username)"
: "${backend:=local}"
: "${endpoint:=http://127.0.0.1:8787}"            # SDD-707: LOCAL = the safety-spine gateway (Anthropic Messages), not raw vLLM
: "${model_id:=local-oracle}"
: "${anthropic_endpoint:=https://api.anthropic.com}"
: "${anthropic_model:=claude-sonnet-4-6}"
: "${gw_port:=18789}"
: "${node_major:=24}"
: "${operator:=operator}"

# State lives OUTSIDE /home so the runtime unit can carry ProtectHome=tmpfs: the
# daemon runs with HOME here, so ~/.openclaw resolves under this writable tree.
OC_HOME="/var/lib/sovereign-os/openclaw"
OC_CFG_DIR="${OC_HOME}/.openclaw"
ENV_FILE="/etc/sovereign-os/openclaw.env"

# ---- Node: is a band-satisfying node already present? ----
node_ok() {
  command -v node >/dev/null 2>&1 || return 1
  local v major minor patch
  v="$(node --version 2>/dev/null | sed 's/^v//')"; [ -n "${v}" ] || return 1
  major="${v%%.*}"; minor="${v#*.}"; minor="${minor%%.*}"; patch="${v##*.}"
  # >=22.22.3 <23  OR  >=24.15 <25  OR  >=25.9
  if [ "${major}" = 22 ] && { [ "${minor}" -gt 22 ] || { [ "${minor}" = 22 ] && [ "${patch}" -ge 3 ]; }; }; then return 0; fi
  if [ "${major}" = 24 ] && [ "${minor}" -ge 15 ]; then return 0; fi
  if [ "${major}" -gt 25 ] || { [ "${major}" = 25 ] && [ "${minor}" -ge 9 ]; }; then return 0; fi
  return 1
}

ensure_node() {
  if node_ok; then log_info "node $(node --version) satisfies OpenClaw's engines band"; return 0; fi
  log_info "node absent or too old for OpenClaw — installing NodeSource ${node_major}.x"
  if ! command -v curl >/dev/null 2>&1; then log_warn "curl missing — cannot fetch NodeSource; skipping"; return 1; fi
  if curl -fsSL "https://deb.nodesource.com/setup_${node_major}.x" -o /tmp/nodesource-setup.sh 2>/dev/null \
       && bash /tmp/nodesource-setup.sh >/dev/null 2>&1 \
       && apt-get install -y nodejs >/dev/null 2>&1; then
    rm -f /tmp/nodesource-setup.sh
    node_ok && { log_info "node $(node --version) installed"; return 0; }
    log_warn "installed node $(node --version 2>/dev/null) still outside the OpenClaw band"; return 1
  fi
  log_warn "NodeSource install failed (no network?) — skipping (resumable post-flash)"; return 1
}

# ---- idempotency: openclaw present + config rendered ----
if command -v openclaw >/dev/null 2>&1 && [ -s "${OC_CFG_DIR}/openclaw.json" ] && node_ok; then
  log_info "openclaw already installed ($(command -v openclaw)) + config present — no-op"
  emit_oc_metric already-present
  exit 0
fi

if ! ensure_node; then
  log_warn "node prerequisite unmet — OpenClaw install deferred (re-run: sovereign-osctl openclaw install)"
  emit_oc_metric no-node
  exit 0
fi

# ---- install openclaw globally ----
if ! command -v openclaw >/dev/null 2>&1; then
  log_info "installing openclaw (npm -g openclaw@latest)"
  if ! npm install -g openclaw@latest >/dev/null 2>&1; then
    log_warn "npm install -g openclaw failed (no network / registry?) — deferred (resumable post-flash)"
    emit_oc_metric npm-failed
    exit 0
  fi
fi
log_info "openclaw present: $(command -v openclaw) ($(openclaw --version 2>/dev/null || echo '?'))"

# ---- render the preconfig via the single backend renderer (SDD-707) ----
# agent-backend.py owns openclaw.json (two coexisting providers: local safety-spine
# gateway + hosted Claude) and the local↔anthropic hotswap. No external channels are
# baked; the cloud key is operator-supplied (never here).
install -d -m 750 "${OC_CFG_DIR}"
_AB="${__REPO_ROOT}/scripts/operator/agent-backend.py"
if [ -f "${_AB}" ]; then
  SOVEREIGN_OS_OPENCLAW_HOME="${OC_HOME}" python3 "${_AB}" openclaw provision \
    --backend "${backend}" \
    --local-endpoint "${endpoint}" --local-model "${model_id}" \
    --anthropic-endpoint "${anthropic_endpoint}" --anthropic-model "${anthropic_model}" \
    --gateway-port "${gw_port}" >/dev/null \
    && log_info "openclaw config rendered (backend=${backend}, local=${endpoint}, cloud=${anthropic_endpoint})" \
    || log_warn "agent-backend render hiccup (non-fatal)"
else
  log_warn "agent-backend.py not staged — openclaw config not rendered"
fi

# The gateway process environment (the runtime unit EnvironmentFiles this + the separate
# anthropic-key.env). HOME points the daemon at its state dir.
if [ ! -s "${ENV_FILE}" ]; then
  install -d -m 755 /etc/sovereign-os
  cat > "${ENV_FILE}" <<ENV
# /etc/sovereign-os/openclaw.env — OpenClaw gateway env (SDD-705/707). The hosted-Claude
# key lives in the root-only /etc/sovereign-os/anthropic-key.env (operator-supplied).
HOME=${OC_HOME}
ENV
fi

# operator owns its state dir so the daemon (User=operator) can read/write + hot-reload.
chown -R "${operator}:${operator}" "${OC_HOME}" 2>/dev/null || true

# ---- stage the runtime unit installed-off (do NOT enable/start) ----
if [ -f "${__REPO_ROOT}/systemd/system/sovereign-openclaw.service" ]; then
  install -m 644 "${__REPO_ROOT}/systemd/system/sovereign-openclaw.service" /etc/systemd/system/ 2>/dev/null || true
  systemctl daemon-reload 2>/dev/null || true
fi

log_info "OpenClaw installed-off — config → ${OC_CFG_DIR}/openclaw.json (endpoint ${endpoint}); turn on: sovereign-osctl openclaw on"
emit_oc_metric installed
exit 0
