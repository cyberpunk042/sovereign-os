#!/usr/bin/env bash
# tests/nspawn/test_dashboard.sh — R225 (SDD-026 Z-1) dashboard SEED.
# Tests both `--render-only` (offline) and the HTTP path via `--once`
# in a background process + curl.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/dashboard/serve.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_dashboard.sh"
echo

[ -x "${SCRIPT}" ] && ok "dashboard/serve.py executable" \
  || { ko "missing dashboard/serve.py"; exit 1; }
grep -q "^  dashboard)" "${OSCTL}" \
  && ok "osctl bridges 'dashboard'" || ko "osctl bridge missing"
grep -q "R225" "${OSCTL}" \
  && ok "osctl cites R225" || ko "R225 citation missing"

# ---- --render-only: pure offline HTML render ----
set +e
python3 "${SCRIPT}" --render-only > /tmp/r225-dash.html 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--render-only rc=0" || ko "render-only rc=${rc}"
grep -q "<!doctype html>" /tmp/r225-dash.html \
  && ok "render emits doctype" || ko "no doctype"
grep -q "sovereign-os dashboard — R225 / SDD-026 Z-1 SEED" /tmp/r225-dash.html \
  && ok "render carries R225 banner" || ko "no banner"
# All 10 cards must render (R225 seed + R226 health + R227 models + R235 insights + R238 install-paths)
for needle in "GPU watt deviance (R219 / Z-5)" \
              "Network state (R220 / Z-7)" \
              "CPU mode (R221 / Z-4)" \
              "Filesystem usage (R222 / Z-10)" \
              "Software RAID (R223 / Z-9)" \
              "Flex profile (R224 / Z-3)" \
              "Health scan (R226 / Z-6)" \
              "Models — catalog × profile (R227 / Z-2)" \
              "Insights (R234 / Z-10)" \
              "Install paths (R237 / Z-8)"; do
  grep -qF "${needle}" /tmp/r225-dash.html \
    && ok "render carries card: ${needle:0:30}…" \
    || ko "missing card: ${needle}"
done

# ---- HTTP path: bind to ephemeral port, --once, curl, verify ----
# Pick a random port in the 18000-19000 range to avoid collisions.
PORT=$(python3 -c "import random; print(random.randint(18000, 19000))")
BIND="127.0.0.1:${PORT}"

# Launch in background with --once so it dies after handling our request.
python3 "${SCRIPT}" --bind "${BIND}" --once > /tmp/r225-srv.log 2>&1 &
SRV_PID=$!

# Wait for the bind banner; bail at 3s.
for _ in 1 2 3 4 5 6; do
  if grep -q "serving" /tmp/r225-srv.log 2>/dev/null; then
    break
  fi
  sleep 0.5
done

if ! grep -q "serving" /tmp/r225-srv.log; then
  ko "server failed to bind on ${BIND}: $(cat /tmp/r225-srv.log)"
else
  ok "server bound on ${BIND}"

  set +e
  curl -fsS "http://${BIND}/" > /tmp/r225-page.html 2>/dev/null
  curl_rc=$?
  set -e
  if [ "${curl_rc}" -eq 0 ]; then
    ok "GET / returned 200"
    grep -q "R225 / SDD-026 Z-1 SEED" /tmp/r225-page.html \
      && ok "served page carries the R225 banner" \
      || ko "served HTML wrong"
  else
    ko "curl GET / failed (rc=${curl_rc})"
  fi
fi

# Wait for the --once server to exit
wait "${SRV_PID}" 2>/dev/null || true

# ---- /api/health endpoint via a second --once invocation ----
PORT=$(python3 -c "import random; print(random.randint(19001, 20000))")
BIND="127.0.0.1:${PORT}"
python3 "${SCRIPT}" --bind "${BIND}" --once > /tmp/r225-api.log 2>&1 &
SRV_PID=$!
for _ in 1 2 3 4 5 6; do
  if grep -q "serving" /tmp/r225-api.log 2>/dev/null; then
    break
  fi
  sleep 0.5
done

if grep -q "serving" /tmp/r225-api.log; then
  set +e
  curl -fsS "http://${BIND}/api/health" > /tmp/r225-api.json 2>/dev/null
  curl_rc=$?
  set -e
  if [ "${curl_rc}" -eq 0 ]; then
    ok "GET /api/health returned 200"
    python3 - /tmp/r225-api.json <<'PY' 2>/dev/null \
      && ok "JSON shape: cards[10] + round + sdd_vector" \
      || ko "JSON shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["round"] == "R225"
assert d["sdd_vector"] == "SDD-026 Z-1"
assert isinstance(d["cards"], list)
# R225 SEED ships with 6 cards; R226 + R227 + R235 + R238 add 4 more.
assert len(d["cards"]) == 10, f"expected 10 cards, got {len(d['cards'])}"
ids = {c["id"] for c in d["cards"]}
assert ids == {"gpu", "network", "cpu", "fs", "raid", "flex", "health", "models", "insights", "install_paths"}, ids
PY
  else
    ko "curl GET /api/health failed (rc=${curl_rc})"
  fi
else
  ko "second server failed to bind"
fi
wait "${SRV_PID}" 2>/dev/null || true

# ---- usage error: bad --bind ----
set +e
python3 "${SCRIPT}" --bind not-a-bind > /tmp/r225-bad.log 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "bad --bind → rc=2" \
  || ko "expected rc=2 on bad bind, got ${rc}"

# ---- osctl bridge render ----
set +e
"${OSCTL}" dashboard render > /tmp/r225-osctl.html 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl dashboard render rc=0" \
  || ko "osctl bridge rc=${rc}"
grep -q "R225 / SDD-026 Z-1 SEED" /tmp/r225-osctl.html \
  && ok "osctl bridge surfaces dashboard" || ko "osctl HTML wrong"

# ---- unknown osctl subverb ----
set +e
"${OSCTL}" dashboard nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown dashboard subverb → rc=2" \
  || ko "expected rc=2 on unknown subverb, got ${rc}"

rm -f /tmp/r225-*

echo
total=$((pass + fail))
echo "test_dashboard: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
