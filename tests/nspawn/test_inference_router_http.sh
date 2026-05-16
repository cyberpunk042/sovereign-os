#!/usr/bin/env bash
# tests/nspawn/test_inference_router_http.sh
#
# Layer 3 test for scripts/inference/router.py — actual HTTP spawn.
# Spawns the router on a free port, hits /healthz, then POSTs requests
# whose 'model' / 'messages' shapes trigger each classify() rule.
# Asserts the upstream tier is chosen by reading the 502 'backend
# unreachable: http://<host>:<port>/...' error — the tier port reveals
# which classify() rule fired.
#
# Backends are intentionally NOT spawned (we're testing routing, not
# inference). The 502 IS the proof of correct routing.
#
# Pure stdlib — no aiohttp, no httpx; uses python3 urllib + curl (or
# python3 if curl absent).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

ROUTER="${__REPO_ROOT}/scripts/inference/router.py"
[ -f "${ROUTER}" ] || { echo "FAIL: router.py not found"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

# Find a free high port
port="$(python3 -c '
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
')"

echo "tests/nspawn/test_inference_router_http.sh"
echo "  router port: ${port}"
echo

# ----------- spawn router ---------------

router_log="$(mktemp)"
metrics_dir="$(mktemp -d)"
SOVEREIGN_OS_METRICS_DIR="${metrics_dir}" python3 "${ROUTER}" --host 127.0.0.1 --port "${port}" >"${router_log}" 2>&1 &
router_pid=$!

cleanup() {
  kill "${router_pid}" 2>/dev/null || true
  wait "${router_pid}" 2>/dev/null || true
  rm -f "${router_log}"
  rm -rf "${metrics_dir}"
}
trap cleanup EXIT

# Wait for the listener (up to 5s)
for _ in $(seq 1 50); do
  if (echo >/dev/tcp/127.0.0.1/"${port}") 2>/dev/null; then
    break
  fi
  sleep 0.1
done

# ----------- helper: POST JSON, return status + body ---------------

post_json() {
  local path="$1" body="$2"
  PORT="${port}" python3 - "${path}" "${body}" <<'PY'
import os, sys, urllib.request, urllib.error
port = os.environ["PORT"]
path = sys.argv[1]; body = sys.argv[2]
req = urllib.request.Request(
    f"http://127.0.0.1:{port}{path}",
    data=body.encode(),
    method="POST",
    headers={"Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        print(f"status:{r.status}")
        print("body:" + r.read().decode("utf-8", "replace")[:200])
except urllib.error.HTTPError as e:
    print(f"status:{e.code}")
    txt = e.read().decode("utf-8", "replace")[:200] if e.fp else ""
    print("body:" + txt)
except Exception as e:
    print("status:0")
    print("body:exception:" + str(e))
PY
}

get_path() {
  local path="$1"
  PORT="${port}" python3 - "${path}" <<'PY'
import os, sys, urllib.request, urllib.error
port = os.environ["PORT"]
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{sys.argv[1]}", timeout=5) as r:
        print(f"status:{r.status}")
        print("body:" + r.read().decode("utf-8", "replace")[:200])
except urllib.error.HTTPError as e:
    print(f"status:{e.code}")
except Exception as e:
    print("status:0")
    print("body:exception:" + str(e))
PY
}

# ----------- healthz ---------------

out="$(get_path /healthz)"
if grep -q '^status:200' <<< "${out}"; then
  ok "/healthz returns 200"
else
  ko "/healthz didn't return 200: ${out}"
fi

# The router's response body uses Python's default HTML error page
# (target URL not in body). Instead we grep the router's stderr log
# where it logs each routing decision via:
#   log.info("route: model=%r → tier=%s (%s)", ...)
#
# After each POST, sleep briefly to let the log line flush, then grep.

post_then_check_tier() {
  local desc="$1" body="$2" expected_tier="$3"
  post_json /v1/chat/completions "${body}" >/dev/null
  sleep 0.2
  # Match the most recent route: line in the log
  if grep -q "tier=${expected_tier}" "${router_log}"; then
    # Even stronger: check the LAST route line is for our expected tier
    last_tier="$(grep -oE "tier=[a-z_]+" "${router_log}" | tail -1 | cut -d= -f2)"
    if [ "${last_tier}" = "${expected_tier}" ]; then
      ok "${desc} → tier=${expected_tier}"
    else
      ko "${desc} → expected tier=${expected_tier}, got last=${last_tier}"
    fi
  else
    ko "${desc}: tier=${expected_tier} never appeared in router log"
  fi
}

# rule 1: bitnet model → pulse
post_then_check_tier \
  "bitnet model" \
  '{"model":"microsoft/bitnet-b1.58-2B-4T","messages":[{"role":"user","content":"hi"}]}' \
  pulse

# rule 2: code/math marker in last user message → oracle_core
# classify() looks for markers like 'def ', 'function ', 'math',
# 'solve ', 'prove ', 'compute ' or fenced code blocks.
post_then_check_tier \
  "code marker in user message" \
  '{"model":"oracle-code","messages":[{"role":"user","content":"compute 2+2 and show me the python def for it"}]}' \
  oracle_core

# rule 4: json_object response_format → logic_engine
post_then_check_tier \
  "json_object response_format" \
  '{"model":"generic","response_format":{"type":"json_object"},"messages":[{"role":"user","content":"return JSON"}]}' \
  logic_engine

# rule 5: default → logic_engine
post_then_check_tier \
  "default rule (unknown model)" \
  '{"model":"unknown","messages":[{"role":"user","content":"hello"}]}' \
  logic_engine

# ----------- bad JSON → 400 ---------------

out="$(PORT="${port}" python3 - <<'PY'
import os, urllib.request, urllib.error
port = os.environ["PORT"]
req = urllib.request.Request(
    f"http://127.0.0.1:{port}/v1/chat/completions",
    data=b"not-json",
    method="POST",
    headers={"Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        print(f"status:{r.status}")
except urllib.error.HTTPError as e:
    print(f"status:{e.code}")
PY
)"
if grep -q '^status:400' <<< "${out}"; then
  ok "bad JSON → 400"
else
  ko "bad JSON returned: ${out}"
fi

# ----------- unknown path → 404 ---------------

out="$(get_path /not-a-real-endpoint)"
if grep -q '^status:404' <<< "${out}"; then
  ok "unknown path → 404"
else
  ko "unknown path: ${out}"
fi

# ----------- Layer B metrics emission (SDD-016) ---------------

metrics_file="${metrics_dir}/sovereign-os-inference-router.prom"
if [ -f "${metrics_file}" ]; then
  ok "router emitted sovereign-os-inference-router.prom"
else
  ko "router metrics file missing at ${metrics_file}"
fi

# Each successful classify (pulse + oracle_core + logic_engine x 2) should
# increment the matching tier counter. logic_engine count >= 2.
if grep -qE '^sovereign_os_inference_route_total\{tier="pulse"\} [1-9]' "${metrics_file}" 2>/dev/null; then
  ok "metrics: pulse counter >= 1"
else
  ko "metrics: pulse counter not incremented"
fi

if grep -qE '^sovereign_os_inference_route_total\{tier="logic_engine"\} [2-9]' "${metrics_file}" 2>/dev/null; then
  ok "metrics: logic_engine counter >= 2 (json + default both route here)"
else
  ko "metrics: logic_engine counter wrong: $(grep logic_engine "${metrics_file}" 2>/dev/null)"
fi

if grep -qE '^sovereign_os_inference_route_total\{tier="oracle_core"\} [1-9]' "${metrics_file}" 2>/dev/null; then
  ok "metrics: oracle_core counter >= 1"
else
  ko "metrics: oracle_core counter not incremented"
fi

if grep -qE '^sovereign_os_inference_router_last_route_timestamp [0-9]{10}$' "${metrics_file}" 2>/dev/null; then
  ok "metrics: last_route_timestamp is a unix epoch"
else
  ko "metrics: last_route_timestamp missing/malformed"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_inference_router_http: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
