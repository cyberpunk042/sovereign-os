#!/usr/bin/env bash
# tests/nspawn/test_science_panel.sh — R558 (SDD-070) science-tools catalog +
# NVIDIA Warp particle-sim panel: catalog CLI, warp-runner graceful degradation
# (runs GPU-or-CPU, and is exit-0 clean even when warp-lang is not installed —
# the CI/dev box has no CUDA and usually no warp), the read-only API + webapp,
# and the osctl bridge + R citation.

set -euo pipefail
__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0; pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCIENCE="${__REPO_ROOT}/scripts/science/science.py"
RUNNER="${__REPO_ROOT}/scripts/science/warp-runner.py"
API="${__REPO_ROOT}/scripts/operator/science-api.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
CATALOG="${__REPO_ROOT}/config/science-tools.yaml"

echo "tests/nspawn/test_science_panel.sh"
echo

# ---------- catalog + schema presence ----------
[ -f "${CATALOG}" ] && ok "config/science-tools.yaml present" || ko "catalog missing"
[ -f "${__REPO_ROOT}/schemas/science-tools.schema.yaml" ] && ok "schema present" || ko "schema missing"
grep -q "warp-lang" "${CATALOG}" && ok "catalog declares warp-lang" || ko "warp-lang absent from catalog"

# ---------- science.py list ----------
out="$(python3 "${SCIENCE}" list 2>&1)"
{ echo "${out}" | grep -q "warp-lang" && echo "${out}" | grep -qi "particles"; } \
  && ok "science list shows warp-lang under particles" || ko "science list wrong: ${out}"

out="$(python3 "${SCIENCE}" list --json 2>&1)"
n="$(echo "${out}" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)["tools"]))' 2>/dev/null || echo 0)"
[ "${n}" = "7" ] && ok "science list --json enumerates 7 tools" || ko "expected 7 tools, got ${n}"

# ---------- science.py status ----------
set +e
out="$(python3 "${SCIENCE}" status --json 2>/dev/null)"; rc=$?
set -e
if [ "${rc}" -eq 0 ] && echo "${out}" | grep -q '"integrated_tools"' && echo "${out}" | grep -q '"warp"'; then
  ok "science status --json is structured (integrated_tools + warp)"
else
  ko "science status broken (rc=${rc}): ${out}"
fi

# ---------- science.py info ----------
python3 "${SCIENCE}" info warp-lang 2>&1 | grep -qi "particles" \
  && ok "science info warp-lang shows the particles domain" || ko "science info warp-lang wrong"
set +e
python3 "${SCIENCE}" info no-such-tool >/dev/null 2>&1; rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "science info <unknown> exits 2 (usage error)" || ko "unknown tool rc=${rc}, expected 2"

# ---------- warp-runner.py graceful degradation (the GPU/CPU/absent invariant) ----------
set +e
out="$(python3 "${RUNNER}" status --json 2>/dev/null)"; rc=$?
set -e
if [ "${rc}" -eq 0 ] && echo "${out}" | grep -q '"installed"'; then
  ok "warp-runner status --json is exit-0 + structured (installed flag)"
else
  ko "warp-runner status broken (rc=${rc}): ${out}"
fi

# run MUST be exit-0 clean whether warp is installed (GPU/CPU) or absent.
set +e
out="$(python3 "${RUNNER}" run --particles 1000 --steps 5 --json 2>/dev/null)"; rc=$?
set -e
if [ "${rc}" -eq 0 ] && echo "${out}" | grep -q '"installed"'; then
  if echo "${out}" | grep -q '"installed": true'; then
    echo "${out}" | grep -qE '"device": *"(cpu|cuda)' \
      && ok "warp-runner run selected a device (warp installed) + exit 0" \
      || ko "warp installed but no device chosen: ${out}"
  else
    ok "warp-runner run degrades cleanly when warp-lang absent (exit 0)"
  fi
else
  ko "warp-runner run not exit-0/structured (rc=${rc}): ${out}"
fi

# ---------- science-api.py --self-check + live HTTP ----------
set +e
out="$(python3 "${API}" --self-check 2>/dev/null)"; rc=$?
set -e
tc="$(echo "${out}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["tool_count"])' 2>/dev/null || echo 0)"
{ [ "${rc}" -eq 0 ] && [ "${tc}" = "7" ]; } \
  && ok "science-api --self-check reports 7 tools" || ko "self-check rc=${rc} tool_count=${tc}"

# ephemeral-port live serve (hang-proof: background, poll, curl, kill-then-wait)
PORT=$(( (RANDOM % 2000) + 18600 ))
SCIENCE_API_PORT="${PORT}" python3 "${API}" >/tmp/sci-panel-api.$$ 2>&1 &
apipid=$!
served=0
for _ in $(seq 1 15); do
  if grep -q "science-api on" /tmp/sci-panel-api.$$ 2>/dev/null; then served=1; break; fi
  sleep 0.2
done
if [ "${served}" = "1" ]; then
  curl -fsS "127.0.0.1:${PORT}/healthz" 2>/dev/null | grep -q '"ok": true' \
    && ok "science-api /healthz → ok" || ko "healthz not ok"
  curl -fsS "127.0.0.1:${PORT}/science.json" 2>/dev/null | grep -q '"tools"' \
    && ok "science-api /science.json serves the catalog" || ko "/science.json missing tools"
  curl -fsS "127.0.0.1:${PORT}/" 2>/dev/null | grep -q "DOCTYPE html" \
    && ok "science-api / serves the webapp" || ko "webapp not served"
  code="$(curl -fsS -o /dev/null -w '%{http_code}' -X POST "127.0.0.1:${PORT}/" 2>/dev/null || true)"
  [ "${code}" = "405" ] && ok "science-api POST → 405 (read-only)" || ko "POST returned ${code}, expected 405"
else
  ko "science-api failed to bind on 127.0.0.1:${PORT}"
fi
kill "${apipid}" 2>/dev/null || true
wait "${apipid}" 2>/dev/null || true
rm -f /tmp/sci-panel-api.$$

# ---------- webapp + osctl bridge + R citation ----------
[ -f "${__REPO_ROOT}/webapp/science/index.html" ] && ok "webapp/science/index.html present" || ko "webapp missing"
grep -q "science)" "${OSCTL}" && ok "sovereign-osctl carries the science) verb" || ko "osctl science verb missing"
grep -q "R558" "${OSCTL}" && ok "osctl science bridge cites R558" || ko "R558 citation missing in osctl"
grep -q "slug: science" "${__REPO_ROOT}/config/dashboard-catalog.yaml" \
  && ok "dashboard-catalog has the science entry" || ko "dashboard-catalog entry missing"

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_science_panel: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
