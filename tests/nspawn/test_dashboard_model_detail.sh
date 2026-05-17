#!/usr/bin/env bash
# tests/nspawn/test_dashboard_model_detail.sh — R233 (SDD-026 Z-2).
# Per-model detail endpoint on the R225 dashboard: GET /api/models/<slug>
# proxies the R231 `models info <slug>` JSON.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SERVE="${__REPO_ROOT}/scripts/dashboard/serve.py"

echo "tests/nspawn/test_dashboard_model_detail.sh"
echo

[ -x "${SERVE}" ] && ok "dashboard/serve.py executable" \
  || { ko "missing serve.py"; exit 1; }
grep -q "R233" "${SERVE}" && ok "serve.py cites R233" || ko "R233 ref missing"
grep -q "/api/models/" "${SERVE}" \
  && ok "serve.py routes /api/models/<slug>" || ko "route missing"

start_server() {
  PORT="$1"
  python3 "${SERVE}" --bind "127.0.0.1:${PORT}" --once > "/tmp/r233-srv-${PORT}.log" 2>&1 &
  echo "$!" > "/tmp/r233-pid-${PORT}"
  for _ in 1 2 3 4 5 6 7 8; do
    if grep -q "serving" "/tmp/r233-srv-${PORT}.log" 2>/dev/null; then
      return 0
    fi
    sleep 0.5
  done
  echo "ERROR: server did not bind on ${PORT}: $(cat /tmp/r233-srv-${PORT}.log)"
  return 1
}

stop_server() {
  PORT="$1"
  wait "$(cat /tmp/r233-pid-${PORT})" 2>/dev/null || true
  rm -f "/tmp/r233-srv-${PORT}.log" "/tmp/r233-pid-${PORT}"
}

# ---- happy path: known slug → 200 + R231 JSON shape ----
PORT=$(python3 -c "import random; print(random.randint(18100,18200))")
if start_server "${PORT}"; then
  ok "server bound (happy path)"
  set +e
  curl -fsS "http://127.0.0.1:${PORT}/api/models/BitNet-b1.58-2B-4T" \
    > /tmp/r233-detail.json 2>&1
  curl_rc=$?
  set -e
  [ "${curl_rc}" -eq 0 ] && ok "GET /api/models/<slug> returned 200" \
    || ko "curl rc=${curl_rc}"
  python3 -c "
import json
d=json.load(open('/tmp/r233-detail.json'))
assert d['round']=='R231', d   # endpoint proxies R231 detail
assert d['model']['id']=='BitNet-b1.58-2B-4T', d
assert 'variants' in d and 'lora_adapters' in d, d
assert 'actions' in d and 'pull' in d['actions'], d
" \
    && ok "endpoint surfaces R231 detail JSON shape" \
    || ko "JSON shape wrong"
  stop_server "${PORT}"
fi
rm -f /tmp/r233-detail.json

# ---- fragment-match slug (hf_repo_id substring) → 200 ----
PORT=$(python3 -c "import random; print(random.randint(18201,18300))")
if start_server "${PORT}"; then
  ok "server bound (fragment match)"
  set +e
  curl -fsS "http://127.0.0.1:${PORT}/api/models/Phi-4-mini-instruct" \
    > /tmp/r233-frag.json 2>&1
  rc=$?
  set -e
  [ "${rc}" -eq 0 ] && ok "fragment-match slug returns 200" \
    || ko "fragment-match failed rc=${rc}"
  stop_server "${PORT}"
fi
rm -f /tmp/r233-frag.json

# ---- unknown slug → 404 with operator hint ----
PORT=$(python3 -c "import random; print(random.randint(18301,18400))")
if start_server "${PORT}"; then
  ok "server bound (404 path)"
  set +e
  curl -sS -o /tmp/r233-404.json -w "%{http_code}" \
    "http://127.0.0.1:${PORT}/api/models/definitely-not-a-real-slug-xxx" \
    > /tmp/r233-404.code 2>&1
  set -e
  code="$(cat /tmp/r233-404.code)"
  [ "${code}" = "404" ] && ok "unknown slug returns HTTP 404" \
    || ko "expected 404, got ${code}"
  python3 -c "
import json
d=json.load(open('/tmp/r233-404.json'))
assert d['error']=='unknown model slug', d
assert d['round']=='R233', d
assert 'hint' in d, d
" \
    && ok "404 body cites round + hint" \
    || ko "404 body wrong"
  stop_server "${PORT}"
fi
rm -f /tmp/r233-404.json /tmp/r233-404.code

# ---- invalid slug (path-traversal-style) → 400 ----
PORT=$(python3 -c "import random; print(random.randint(18401,18500))")
if start_server "${PORT}"; then
  ok "server bound (400 path)"
  set +e
  # %2F is "/" — exercises the invalid-char guard. The HTTP server
  # decodes it before path matching.
  curl -sS -o /tmp/r233-400.json -w "%{http_code}" \
    "http://127.0.0.1:${PORT}/api/models/foo%20bar" \
    > /tmp/r233-400.code 2>&1
  set -e
  code="$(cat /tmp/r233-400.code)"
  [ "${code}" = "400" ] && ok "slug with space returns HTTP 400" \
    || ko "expected 400, got ${code}"
  stop_server "${PORT}"
fi
rm -f /tmp/r233-400.json /tmp/r233-400.code

echo
total=$((pass + fail))
echo "test_dashboard_model_detail: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
