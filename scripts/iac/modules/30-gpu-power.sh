#!/usr/bin/env bash
# per-GPU power caps — profiles.provisioning + hardware.gpu[].tdp_watts
# gate: IAC_ENABLE_GPU
#
# WHY THIS MODULE RE-PATCHES A PACKAGE-OWNED FILE
#   nvidia-power-limit.sh reads hardware.gpu[].tdp_watts from the ACTIVE PROFILE
#   and matches cards by PCI device id. That profile file is package-owned and
#   is NOT a dpkg conffile — `dpkg --verify sovereign-os-cockpit` already reports
#   it as ??5?????? (md5 drift). The next `apt upgrade sovereign-os-cockpit`
#   will therefore overwrite it and silently restore tdp_watts: 350.
#
#   The clean fix would be an override path, but common.sh line 31 sets
#   SOVEREIGN_OS_PROFILES_DIR unconditionally from SOVEREIGN_OS_ROOT, so it
#   cannot be redirected without relocating the whole tree. Re-asserting the
#   value on every converge is the honest alternative: drift is expected and
#   self-heals. That is exactly what a converge loop is for.
#
# WHY 400 W AND NOT THE PROFILE'S 350 W
#   See converge.conf IAC_GPU_CAPS. The installed 5090 is a TUF OC SKU with
#   power.min_limit = 400 W; nvidia-smi rejects 350 outright.
#
# shellcheck shell=bash

if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi >/dev/null 2>&1; then
  skip "nvidia-smi unavailable — no GPU caps to converge"
  return 0 2>/dev/null || exit 0
fi

_caps="${IAC_GPU_CAPS:-}"
if [ -z "${_caps}" ]; then
  skip "IAC_GPU_CAPS empty in converge.conf — nothing declared"
  return 0 2>/dev/null || exit 0
fi

for pair in ${_caps}; do
  devid="${pair%%:*}"
  watts="${pair##*:}"

  # Resolve device id → nvidia-smi index (enumeration-order safe).
  idx="$(nvidia-smi --query-gpu=index,pci.device_id --format=csv,noheader 2>/dev/null \
        | awk -F, -v d="${devid}" 'tolower($2) ~ tolower(d) {gsub(/ /,"",$1); print $1; exit}')"
  if [ -z "${idx}" ]; then
    skip "GPU ${devid} not present on this host"
    continue
  fi

  name="$(nvidia-smi -i "${idx}" --query-gpu=name --format=csv,noheader 2>/dev/null)"
  cur="$(nvidia-smi -i "${idx}" --query-gpu=power.limit --format=csv,noheader,nounits 2>/dev/null | cut -d. -f1)"
  min="$(nvidia-smi -i "${idx}" --query-gpu=power.min_limit --format=csv,noheader,nounits 2>/dev/null | cut -d. -f1)"
  max="$(nvidia-smi -i "${idx}" --query-gpu=power.max_limit --format=csv,noheader,nounits 2>/dev/null | cut -d. -f1)"

  # Refuse to request something the silicon rejects — that is how the profile's
  # 350 W produced a hook that failed every single boot.
  if [ -n "${min}" ] && [ "${watts}" -lt "${min}" ] 2>/dev/null; then
    fail "GPU ${idx} (${name}): declared ${watts}W is below hardware min ${min}W — refusing"
    continue
  fi
  if [ -n "${max}" ] && [ "${watts}" -gt "${max}" ] 2>/dev/null; then
    fail "GPU ${idx} (${name}): declared ${watts}W is above hardware max ${max}W — refusing"
    continue
  fi

  if [ "${cur}" = "${watts}" ]; then
    ok "GPU ${idx} ${name} @ ${watts}W"
  else
    run "persistence" nvidia-smi -pm 1
    if run "power-limit" nvidia-smi -i "${idx}" -pl "${watts}"; then
      changed "GPU ${idx} ${name} ${cur}W → ${watts}W"
    else
      fail "GPU ${idx} ${name} — could not set ${watts}W"
    fi
  fi

  # ---- re-assert the profile value the boot hook actually reads ----
  cur_profile="$(python3 - "${IAC_PROFILE_FILE}" "${devid}" <<'PY' 2>/dev/null
import sys, yaml
try:
    d = yaml.safe_load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
for g in (d.get("hardware") or {}).get("gpu") or []:
    if sys.argv[2].lower() in str(g.get("pci_id", "")).lower():
        print(g.get("tdp_watts", "")); break
PY
)"
  if [ "${cur_profile}" = "${watts}" ]; then
    ok "profile tdp_watts for ${devid} = ${watts}"
  elif [ -z "${cur_profile}" ]; then
    skip "no hardware.gpu entry matching ${devid} in profile"
  elif [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "profile tdp_watts ${devid}: ${cur_profile} → ${watts}"
  else
    if python3 - "${IAC_PROFILE_FILE}" "${devid}" "${watts}" <<'PY' 2>/dev/null
import re, sys
path, devid, watts = sys.argv[1], sys.argv[2].lower(), sys.argv[3]
src = open(path).read()
# Operate on the one hardware.gpu list item whose pci_id matches, so a shared
# tdp_watts value on another card is never collaterally rewritten.
best = None
for m in re.finditer(r'- vendor:.*?(?=\n\s*- vendor:|\n[a-zA-Z_]|\Z)', src, re.S):
    if devid in m.group(0).lower():
        best = m; break
if not best:
    sys.exit(1)
block = best.group(0)
new = re.sub(r'tdp_watts:\s*\d+[^\n]*',
             f'tdp_watts: {watts}   # hardware floor — set by scripts/iac (min_limit reported by nvidia-smi)',
             block, count=1)
if new == block:
    sys.exit(1)
open(path, "w").write(src[:best.start()] + new + src[best.end():])
PY
    then
      changed "profile tdp_watts ${devid}: ${cur_profile} → ${watts}"
    else
      fail "profile tdp_watts ${devid} — could not patch ${IAC_PROFILE_FILE}"
    fi
  fi
done

# ---- keep gpu-watch's alert threshold aligned with reality ----
# /etc/sovereign-os/gpu-policy.toml is NOT package-owned (install copies it from
# config/gpu-policy.toml.example), so it survives upgrades — but it also drifts
# untracked. gpu-watch.py alerts on abs(actual - safe_limit_watts) > tolerance,
# so a stale 350 here means a permanent false deviance.
_policy=/etc/sovereign-os/gpu-policy.toml
if [ -f "${_policy}" ]; then
  want5090="$(printf '%s\n' ${_caps} | awk -F: '/^2b85:/{print $2}')"
  if [ -n "${want5090}" ]; then
    # Parsed in python, not awk: an awk range /\[gpu\."…"\]/,/^\[/ collapses to a
    # single line, because the table header that OPENS the range also matches the
    # /^\[/ that closes it. That silently yielded an empty value and made this
    # module report a change on every run — an idempotency break, not a cosmetic
    # one. Use the same parser shape as the writer below.
    cur="$(python3 - "${_policy}" <<'PY' 2>/dev/null
import re, sys
try:
    src = open(sys.argv[1]).read()
except Exception:
    sys.exit(0)
m = re.search(r'\[gpu\."GeForce RTX 5090"\](.*?)(?=\n\[|\Z)', src, re.S)
if m:
    v = re.search(r'safe_limit_watts\s*=\s*(\d+)', m.group(1))
    if v:
        print(v.group(1))
PY
)"
    if [ "${cur}" = "${want5090}" ]; then
      ok "gpu-policy safe_limit_watts = ${want5090}"
    elif [ "${IAC_DRY_RUN}" = 1 ]; then
      changed "gpu-policy safe_limit_watts: ${cur} → ${want5090}"
    else
      if python3 - "${_policy}" "${want5090}" <<'PY' 2>/dev/null
import re, sys
path, w = sys.argv[1], sys.argv[2]
src = open(path).read()
m = re.search(r'(\[gpu\."GeForce RTX 5090"\].*?)(?=\n\[|\Z)', src, re.S)
if not m: sys.exit(1)
b = m.group(1)
n = re.sub(r'safe_limit_watts\s*=\s*\d+', f'safe_limit_watts = {w}', b, count=1)
n = re.sub(r'max_sustained_draw_watts\s*=\s*\d+', f'max_sustained_draw_watts = {int(w)-10}', n, count=1)
if n == b: sys.exit(1)
open(path, "w").write(src[:m.start(1)] + n + src[m.end(1):])
PY
      then changed "gpu-policy safe_limit_watts: ${cur} → ${want5090}"
      else fail "gpu-policy — could not update safe_limit_watts"; fi
    fi
  fi
else
  skip "gpu-policy.toml absent — nothing to align"
fi
