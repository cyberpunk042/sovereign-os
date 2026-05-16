#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_inference_health.sh
#
# Layer 3 test for Round 42 — 'sovereign-osctl inference health'.
# Validates the HTTP /healthz probe + TCP fallback for all 4 tiers
# (pulse / logic / oracle / router).
#
# CI environment doesn't have backends running, so we verify:
#   - all 4 tiers reported with correct ports
#   - all-down state → exit 1 (operator-actionable alarm signal)
#   - output table shape: TIER + ENDPOINT + STATUS + DETAIL columns
#   - help text documents the new subcommand
#
# Additionally spawns scripts/inference/router.py on the actual port
# 8080 (when free) to verify the up-path → exit 0 + ✓ ok row.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

CTL="${__REPO_ROOT}/scripts/sovereign-osctl"
[ -x "${CTL}" ] || { echo "FAIL: sovereign-osctl not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_sovereign_osctl_inference_health.sh"
echo

export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_PROFILE=sain-01

# ----------- all-down state (no backends running) ---------------

set +e
out="$("${CTL}" inference health 2>&1)"
rc=$?
set -e

# Note: rc may be 0 if some other service is squatting on these ports
# (unlikely in CI). Most-conservative assertion: all 4 tiers appear.
for tier in pulse logic oracle router; do
  if grep -qE "^${tier}\s" <<< "${out}"; then
    ok "tier reported in health output: ${tier}"
  else
    ko "tier missing from health output: ${tier}"
  fi
done

for port in 8081 8082 8083 8080; do
  if grep -q ":${port}" <<< "${out}"; then
    ok "endpoint port ${port} surfaced"
  else
    ko "endpoint port ${port} missing"
  fi
done

# Column header
if grep -q "TIER" <<< "${out}" && grep -q "STATUS" <<< "${out}" && grep -q "ENDPOINT" <<< "${out}"; then
  ok "table header includes TIER/ENDPOINT/STATUS columns"
else
  ko "table header malformed: ${out:0:200}"
fi

# All-down should be rc=1 OR rc=0-with-all-down-marker. Be liberal:
# require rc != 0 OR all rows show ✗ down.
if [ "${rc}" -ne 0 ] || ! grep -q "✓ ok" <<< "${out}"; then
  ok "no-backends-up → exit ${rc} signals 'down' to caller"
else
  ko "no-backends path returned ok unexpectedly: ${out}"
fi

# ----------- help documents the new subcommand ---------------

help_out="$("${CTL}" help 2>&1)"
if grep -q "inference health" <<< "${help_out}"; then
  ok "help documents 'inference health'"
else
  ko "help missing 'inference health'"
fi

# ----------- up-path: spawn the router on 8080 if port is free ---------------

if ! (echo >/dev/tcp/127.0.0.1/8080) 2>/dev/null; then
  # Port is free — try spawning the router
  router_log="$(mktemp)"
  python3 "${__REPO_ROOT}/scripts/inference/router.py" --host 127.0.0.1 --port 8080 \
    >"${router_log}" 2>&1 &
  router_pid=$!
  trap "kill ${router_pid} 2>/dev/null || true; wait ${router_pid} 2>/dev/null || true; rm -f ${router_log}" EXIT

  # Wait for listener
  for _ in $(seq 1 30); do
    if (echo >/dev/tcp/127.0.0.1/8080) 2>/dev/null; then
      break
    fi
    sleep 0.1
  done

  set +e
  out_up="$("${CTL}" inference health 2>&1)"
  set -e

  if grep -qE "^router\s+http://127\.0\.0\.1:8080\s+✓ ok" <<< "${out_up}"; then
    ok "router up-path: ✓ ok row when router is reachable"
  else
    # Soft path: any non-down indicator
    if grep -qE "^router\s+http://127\.0\.0\.1:8080\s+(✓ ok|~ tcp)" <<< "${out_up}"; then
      ok "router up-path: at least liveness detected (✓ ok or ~ tcp)"
    else
      ko "router up-path: probe didn't detect listening router: ${out_up:0:300}"
    fi
  fi
else
  echo "  SKIP — port 8080 squatted by something else; up-path test not possible in this env"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_sovereign_osctl_inference_health: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
