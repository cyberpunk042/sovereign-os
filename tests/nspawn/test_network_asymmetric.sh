#!/usr/bin/env bash
# tests/nspawn/test_network_asymmetric.sh
#
# Layer 3 test for R158 — scripts/network/render-asymmetric.sh
# (master spec § 8 Zero-Trust asymmetric networking).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/network/render-asymmetric.sh"

echo "tests/nspawn/test_network_asymmetric.sh"
echo

[ -x "${SCRIPT}" ] && ok "render-asymmetric.sh executable" || { ko "missing"; exit 1; }

# ---------- master spec citation ----------
if grep -q "master spec § 8" "${SCRIPT}"; then
  ok "script cites master spec § 8"
else
  ko "master spec § 8 citation missing"
fi

# ---------- sain-01 profile carries master spec § 8.1 verbatim addresses ----------
PROFILE="${__REPO_ROOT}/profiles/sain-01.yaml"
for kw in "10.0.100.50/24" "10.0.100.1" "10.0.200.50/24" "enp6s0" "enp5s0" "mtu: 9000" "vlan: 100" "vlan: 200"; do
  if grep -q "${kw}" "${PROFILE}"; then
    ok "sain-01 profile carries: ${kw}"
  else
    ko "sain-01 profile missing: ${kw}"
  fi
done

# ---------- legacy /etc/network/interfaces render (master spec § 8.1 verbatim) ----------
set +e
out="$(bash "${SCRIPT}" --legacy-interfaces 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "--legacy-interfaces exit 0"
else
  ko "--legacy-interfaces rc=${rc}"
fi

# verbatim master spec § 8.1 lines
for kw in \
  "auto enp6s0" \
  "iface enp6s0 inet static" \
  "address 10.0.100.50/24" \
  "gateway 10.0.100.1" \
  "dns-nameservers 10.0.100.1" \
  "auto enp5s0" \
  "iface enp5s0 inet static" \
  "address 10.0.200.50/24" \
  "up ip link set dev enp5s0 mtu 9000" \
  "Enable Jumbo Frames"; do
  if grep -qF "${kw}" <<< "${out}"; then
    ok "legacy render contains verbatim § 8.1 line: ${kw}"
  else
    ko "legacy render missing: ${kw}"
  fi
done

# Marvell data interface MUST NOT have a gateway directive (master spec
# § 8: "No Outbound WAN Access")
data_block="$(awk '/^auto enp5s0/,/^$/' <<< "${out}")"
if ! grep -q "^    gateway " <<< "${data_block}"; then
  ok "data interface (Marvell) has NO gateway (Zero-Trust per master spec § 8)"
else
  ko "data interface should not have a gateway — master spec § 8 violation"
fi

# ---------- systemd-networkd render ----------
TMP_OUT="$(mktemp -d)"
trap 'rm -rf "${TMP_OUT}"' EXIT
set +e
out="$(SOVEREIGN_OS_NET_OUT_DIR="${TMP_OUT}" bash "${SCRIPT}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "systemd-networkd render exit 0"
else
  ko "render rc=${rc}"
fi

# 2 .network files produced
networkd_count="$(ls "${TMP_OUT}"/*.network 2>/dev/null | wc -l)"
if [ "${networkd_count}" -eq 2 ]; then
  ok "wrote 2 .network units (mgmt + data)"
else
  ko "wrong file count: ${networkd_count}"
fi

mgmt="${TMP_OUT}/10-sovereign-mgmt.network"
data="${TMP_OUT}/20-sovereign-data.network"
[ -f "${mgmt}" ] && ok "mgmt unit produced at expected path" || ko "mgmt unit missing"
[ -f "${data}" ] && ok "data unit produced at expected path" || ko "data unit missing"

# mgmt unit content
for kw in "Name=enp6s0" "Address=10.0.100.50/24" "Gateway=10.0.100.1" "DNS=10.0.100.1"; do
  if grep -q -F "${kw}" "${mgmt}"; then
    ok "mgmt unit contains: ${kw}"
  else
    ko "mgmt unit missing: ${kw}"
  fi
done

# data unit content
for kw in "Name=enp5s0" "Address=10.0.200.50/24" "DefaultRouteOnDevice=no" "MTUBytes=9000"; do
  if grep -q -F "${kw}" "${data}"; then
    ok "data unit contains: ${kw}"
  else
    ko "data unit missing: ${kw}"
  fi
done

# data unit MUST NOT have a Gateway= directive
if ! grep -q "^Gateway=" "${data}"; then
  ok "data unit has NO Gateway= (Zero-Trust per master spec § 8)"
else
  ko "data unit incorrectly carries a Gateway= directive"
fi

# ---------- DRY-RUN ----------
set +e
out="$(SOVEREIGN_OS_NET_OUT_DIR="${TMP_OUT}/dry" SOVEREIGN_OS_DRY_RUN=1 \
       bash "${SCRIPT}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "DRY-RUN" <<< "${out}"; then
  ok "DRY-RUN exit 0 + surfaces intent"
else
  ko "DRY-RUN broken (rc=${rc})"
fi
# DRY-RUN must NOT write files
if [ ! -d "${TMP_OUT}/dry" ] || [ -z "$(ls "${TMP_OUT}/dry" 2>/dev/null)" ]; then
  ok "DRY-RUN did not write files"
else
  ko "DRY-RUN wrote files unexpectedly"
fi

# ---------- profile without address fields → skip-no-address ----------
# Create a minimal profile YAML without address fields
TMP_PROFILE_DIR="$(mktemp -d)"
mkdir -p "${TMP_PROFILE_DIR}/profiles"
cat > "${TMP_PROFILE_DIR}/profiles/test-noaddr.yaml" <<'YAMLEOF'
schema_version: "1.0.0"
profile:
  id: test-noaddr
  name: "test no-addr"
  description: "Test profile without address fields — should skip-no-address"
hardware:
  network:
    - role: mgmt
      vendor: generic
      model: nic
      speed_gbps: 1
      vlan: 100
      default_gateway: true
YAMLEOF
# Reroute the script to read from this dir — easiest is to symlink it
# under the repo's profiles/ for the test only.
TEST_PROFILE_LINK="${__REPO_ROOT}/profiles/test-noaddr.yaml"
ln -sf "${TMP_PROFILE_DIR}/profiles/test-noaddr.yaml" "${TEST_PROFILE_LINK}"
trap 'rm -rf "${TMP_OUT}" "${TMP_PROFILE_DIR}"; rm -f "${TEST_PROFILE_LINK}"' EXIT

set +e
out="$(SOVEREIGN_OS_PROFILE=test-noaddr bash "${SCRIPT}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "no hardware.network\[\].address" <<< "${out}"; then
  ok "profile without address fields → graceful skip + clear log"
else
  ko "no-address path broken (rc=${rc} out=${out:0:200})"
fi
rm -f "${TEST_PROFILE_LINK}"

# ---------- unknown profile ----------
set +e
out="$(SOVEREIGN_OS_PROFILE=no-such-profile-xyz-9999 bash "${SCRIPT}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "profile yaml not found" <<< "${out}"; then
  ok "unknown profile → rc≠0 + clear error"
else
  ko "unknown-profile path broken (rc=${rc})"
fi

echo
total=$((pass + fail))
echo "test_network_asymmetric: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
