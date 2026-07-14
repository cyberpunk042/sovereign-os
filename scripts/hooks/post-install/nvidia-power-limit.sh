#!/usr/bin/env bash
# scripts/hooks/post-install/nvidia-power-limit.sh
#
# Apply each GPU's profile-declared power cap (tdp_watts) at boot (SDD-701).
# nvidia-smi -pl is NOT persistent across reboots, so this runs EVERY boot (not
# ConditionFirstBoot) after the driver is up. Without it the RTX 5090 runs at its
# stock 575W TGP — far above the profile's 350W intent and the SAIN-01 power/
# thermal budget (1600W PSU shared with a 300W-Max-Q PRO 6000 + a 9900X); the
# PRO 6000 Max-Q likewise pins to its 300W envelope.
#
# Each physical card is matched to its cap by PCI device-id (profile pci_id
# "10de:2bb4" → device 2bb4 → the nvidia-smi GPU whose pci.device_id contains it)
# so enumeration order never mis-assigns a cap. Idempotent (nvidia-smi -pl is
# reapply-safe) + VM-skipped by the unit. GPUs with role=vfio are skipped (they
# belong to the isolated sandbox, not the host).

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="nvidia-power-limit"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "${STEP_ID}" "apply per-GPU power caps from the profile"

require_root

if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi >/dev/null 2>&1; then
  log_warn "nvidia-smi absent or not functional — driver not up yet; skipping power caps this boot"
  emit_metric sovereign_os_post_install_nvidia_power_limit_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"no-driver\""
  exit 0
fi

# enable persistence mode so the cap + clocks survive an idle GPU going to sleep
nvidia-smi -pm 1 >/dev/null 2>&1 || log_warn "could not enable persistence mode (non-fatal)"

# Build the device-id → watts map from the profile, apply per matching GPU.
applied="$(python3 - "$STEP_ID" <<'PY'
import os, subprocess, sys, yaml

with open(os.environ["SOVEREIGN_OS_PROFILE_FILE"]) as f:
    prof = yaml.safe_load(f)

caps = {}  # device-id (lowercase, no 0x) -> watts
for g in (prof.get("hardware") or {}).get("gpu") or []:
    if g.get("role") == "vfio":
        continue
    pci = (g.get("pci_id") or "")
    tdp = g.get("tdp_watts")
    if ":" in pci and tdp:
        dev = pci.split(":", 1)[1].strip().lower()
        if dev and "?" not in dev:
            caps[dev] = int(tdp)

if not caps:
    print("NONE")
    sys.exit(0)

out = subprocess.run(
    ["nvidia-smi", "--query-gpu=index,pci.device_id", "--format=csv,noheader"],
    capture_output=True, text=True,
)
done = 0
for line in out.stdout.splitlines():
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 2:
        continue
    idx, devid = parts
    devid_l = devid.lower().replace("0x", "")
    watts = next((w for d, w in caps.items() if d in devid_l), None)
    if watts is None:
        continue
    r = subprocess.run(["nvidia-smi", "-i", idx, "-pl", str(watts)],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print(f"OK idx={idx} devid={devid} watts={watts}")
        done += 1
    else:
        print(f"FAIL idx={idx} devid={devid} watts={watts} :: {r.stderr.strip()[:120]}")
sys.exit(0 if done else 3)
PY
)"
rc=$?
printf '%s\n' "${applied}" | sed 's/^/  /'
if [ "${applied}" = "NONE" ]; then
  log_warn "no host GPU with a tdp_watts cap in the profile — nothing to apply"
  emit_metric sovereign_os_post_install_nvidia_power_limit_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"no-caps\""
  exit 0
fi
if [ "${rc}" -ne 0 ]; then
  log_warn "no GPU power cap applied (device-id match failed or nvidia-smi refused) — GPUs run at stock power"
  emit_metric sovereign_os_post_install_nvidia_power_limit_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"none-applied\""
  exit 0
fi

emit_metric sovereign_os_post_install_nvidia_power_limit_total 1 \
  "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"applied\""
log_info "${STEP_ID} complete"
