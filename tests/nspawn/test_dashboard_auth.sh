#!/usr/bin/env bash
# tests/nspawn/test_dashboard_auth.sh — R250 (SDD-026 Z-1 auth).
# Dashboard IP allowlist + Bearer token gate. Loopback shortcut by default.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SERVE="${__REPO_ROOT}/scripts/dashboard/serve.py"
EXAMPLE="${__REPO_ROOT}/config/dashboard-auth.toml.example"

echo "tests/nspawn/test_dashboard_auth.sh"
echo

[ -x "${SERVE}" ] && ok "serve.py executable" \
  || { ko "missing serve.py"; exit 1; }
[ -f "${EXAMPLE}" ] && ok "dashboard-auth.toml.example shipped" \
  || ko "example config missing"
grep -q "R250" "${SERVE}" && ok "serve.py cites R250" || ko "R250 missing"
grep -q "_check_auth" "${SERVE}" \
  && ok "serve.py implements _check_auth handler hook" \
  || ko "_check_auth missing"
grep -q "AUTH_CONFIG" "${SERVE}" \
  && ok "AUTH_CONFIG module-level state present" \
  || ko "AUTH_CONFIG missing"

TMP="$(mktemp -d -t r250.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

start_server() {
  local port="$1"
  local cfg="$2"
  local token="$3"
  if [ -n "${cfg}" ]; then
    export SOVEREIGN_OS_DASHBOARD_AUTH_CONFIG="${cfg}"
  else
    unset SOVEREIGN_OS_DASHBOARD_AUTH_CONFIG || true
  fi
  if [ -n "${token}" ]; then
    export DASHBOARD_TEST_TOKEN="${token}"
  fi
  python3 "${SERVE}" --bind "127.0.0.1:${port}" --once \
    > "/tmp/r250-srv-${port}.log" 2>&1 &
  echo $! > "/tmp/r250-pid-${port}"
  for _ in 1 2 3 4 5 6 7 8; do
    if grep -q "serving" "/tmp/r250-srv-${port}.log" 2>/dev/null; then
      return 0
    fi
    sleep 0.5
  done
  echo "ERROR: server did not bind on ${port}: $(cat /tmp/r250-srv-${port}.log)"
  return 1
}

stop_server() {
  local port="$1"
  wait "$(cat /tmp/r250-pid-${port})" 2>/dev/null || true
  rm -f "/tmp/r250-srv-${port}.log" "/tmp/r250-pid-${port}"
}

# ---- case 1: no auth config, loopback works ----
P1=$(python3 -c "import random; print(random.randint(19000,19099))")
unset SOVEREIGN_OS_DASHBOARD_AUTH_CONFIG || true
if python3 "${SERVE}" --bind "127.0.0.1:${P1}" --once > "/tmp/r250-1.log" 2>&1 &
then PID=$!; for _ in 1 2 3 4 5 6; do grep -q serving "/tmp/r250-1.log" 2>/dev/null && break; sleep 0.4; done
fi
# Force unset of the in-process example config by passing a NON-existent path.
# Easier: rely on env override below.
set +e
out_code=$(curl -sS -o /dev/null -w "%{http_code}" "http://127.0.0.1:${P1}/api/health" 2>/dev/null)
set -e
# With example config auto-loaded, allow_loopback=true means 200.
[ "${out_code}" = "200" ] && ok "loopback request returns 200 (allow_loopback=true)" \
  || ko "expected 200, got ${out_code}"
wait "${PID}" 2>/dev/null || true
rm -f "/tmp/r250-1.log"

# ---- case 2: auth required, no token → 401 (override via env-override) ----
# Construct a config that requires the token (loopback also required to send it).
cat > "${TMP}/cfg-strict.toml" <<'TOML'
token_env = "DASHBOARD_TEST_TOKEN"
allow_loopback = false
allow_ips = ["127.0.0.1"]
TOML
P2=$(python3 -c "import random; print(random.randint(19100,19199))")
export SOVEREIGN_OS_DASHBOARD_AUTH_CONFIG="${TMP}/cfg-strict.toml"
export DASHBOARD_TEST_TOKEN="secret-r250-token"
python3 "${SERVE}" --bind "127.0.0.1:${P2}" --once > "/tmp/r250-2.log" 2>&1 &
PID=$!
for _ in 1 2 3 4 5 6 7 8; do grep -q serving "/tmp/r250-2.log" 2>/dev/null && break; sleep 0.4; done
set +e
out_code=$(curl -sS -o "${TMP}/no-token.json" -w "%{http_code}" "http://127.0.0.1:${P2}/api/health" 2>/dev/null)
set -e
[ "${out_code}" = "401" ] && ok "auth-required + no Authorization header → 401" \
  || ko "expected 401, got ${out_code}: $(cat ${TMP}/no-token.json 2>/dev/null)"
python3 -c "
import json
d=json.load(open('${TMP}/no-token.json'))
assert d['error']=='unauthorized', d
assert d['round']=='R250', d
" \
  && ok "401 body cites round + error=unauthorized" \
  || ko "401 body shape wrong"
wait "${PID}" 2>/dev/null || true

# ---- case 3: auth required, correct token → 200 ----
P3=$(python3 -c "import random; print(random.randint(19200,19299))")
python3 "${SERVE}" --bind "127.0.0.1:${P3}" --once > "/tmp/r250-3.log" 2>&1 &
PID=$!
for _ in 1 2 3 4 5 6 7 8; do grep -q serving "/tmp/r250-3.log" 2>/dev/null && break; sleep 0.4; done
set +e
out_code=$(curl -sS -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer secret-r250-token" \
  "http://127.0.0.1:${P3}/api/health" 2>/dev/null)
set -e
[ "${out_code}" = "200" ] && ok "auth-required + correct token → 200" \
  || ko "expected 200, got ${out_code}"
wait "${PID}" 2>/dev/null || true

# ---- case 4: auth required, wrong token → 401 ----
P4=$(python3 -c "import random; print(random.randint(19300,19399))")
python3 "${SERVE}" --bind "127.0.0.1:${P4}" --once > "/tmp/r250-4.log" 2>&1 &
PID=$!
for _ in 1 2 3 4 5 6 7 8; do grep -q serving "/tmp/r250-4.log" 2>/dev/null && break; sleep 0.4; done
set +e
out_code=$(curl -sS -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer wrong-token" \
  "http://127.0.0.1:${P4}/api/health" 2>/dev/null)
set -e
[ "${out_code}" = "401" ] && ok "auth-required + wrong token → 401" \
  || ko "expected 401, got ${out_code}"
wait "${PID}" 2>/dev/null || true

# ---- case 5: IP not in allowlist → 403 ----
cat > "${TMP}/cfg-ipdeny.toml" <<'TOML'
token_env = "DASHBOARD_TEST_TOKEN"
allow_loopback = false
allow_ips = ["10.99.99.99"]
TOML
export SOVEREIGN_OS_DASHBOARD_AUTH_CONFIG="${TMP}/cfg-ipdeny.toml"
P5=$(python3 -c "import random; print(random.randint(19400,19499))")
python3 "${SERVE}" --bind "127.0.0.1:${P5}" --once > "/tmp/r250-5.log" 2>&1 &
PID=$!
for _ in 1 2 3 4 5 6 7 8; do grep -q serving "/tmp/r250-5.log" 2>/dev/null && break; sleep 0.4; done
set +e
out_code=$(curl -sS -o "${TMP}/ipdeny.json" -w "%{http_code}" \
  -H "Authorization: Bearer secret-r250-token" \
  "http://127.0.0.1:${P5}/api/health" 2>/dev/null)
set -e
[ "${out_code}" = "403" ] && ok "client IP not in allowlist → 403" \
  || ko "expected 403, got ${out_code}"
python3 -c "
import json
d=json.load(open('${TMP}/ipdeny.json'))
assert d['error']=='forbidden', d
" \
  && ok "403 body cites error=forbidden" \
  || ko "403 body wrong"
wait "${PID}" 2>/dev/null || true

# ---- case 6: token_env missing from env → 500 server-misconfig ----
unset DASHBOARD_TEST_TOKEN || true
cat > "${TMP}/cfg-noenv.toml" <<'TOML'
token_env = "DASHBOARD_TEST_TOKEN"
allow_loopback = false
allow_ips = ["127.0.0.1"]
TOML
P7=$(python3 -c "import random; print(random.randint(19600,19699))")
SOVEREIGN_OS_DASHBOARD_AUTH_CONFIG="${TMP}/cfg-noenv.toml" \
  python3 "${SERVE}" --bind "127.0.0.1:${P7}" --once > "/tmp/r250-7.log" 2>&1 &
PID=$!
for _ in 1 2 3 4 5 6 7 8; do grep -q serving "/tmp/r250-7.log" 2>/dev/null && break; sleep 0.4; done
set +e
out_code=$(curl -sS -o "${TMP}/noenv.json" -w "%{http_code}" \
  -H "Authorization: Bearer anything" \
  "http://127.0.0.1:${P7}/api/health" 2>/dev/null)
set -e
[ "${out_code}" = "500" ] && ok "token_env missing → 500 server-misconfig" \
  || ko "expected 500, got ${out_code}"
python3 -c "
import json
d=json.load(open('${TMP}/noenv.json'))
assert d['error']=='server-misconfig', d
" \
  && ok "500 body cites error=server-misconfig" \
  || ko "500 body wrong"
wait "${PID}" 2>/dev/null || true

echo
total=$((pass + fail))
echo "test_dashboard_auth: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
