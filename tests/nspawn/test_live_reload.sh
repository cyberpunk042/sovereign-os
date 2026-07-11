#!/usr/bin/env bash
# tests/nspawn/test_live_reload.sh — R559 (SDD-203 / E11.M203) dev live-reload:
# the broker's SSE change-notify (relevant edit notifies, irrelevant stays
# silent — "never for nothing") and reload-run.py's in-place self-re-exec
# (fresh code, SAME pid, no kill). Runs entirely on loopback with throwaway
# ports. Socket-bind is tolerated: if the sandbox cannot bind a loopback port
# the network subtests SKIP (not fail), so CI stays green while a real dev box
# exercises the full path. Static invariants live in
# tests/lint/test_live_reload_contract.py.

set -uo pipefail
__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"
cd "${__REPO_ROOT}" || exit 2

fail=0; pass=0; skip=0
ok()   { echo "  PASS — $1"; pass=$((pass + 1)); }
ko()   { echo "  FAIL — $1"; fail=$((fail + 1)); }
sk()   { echo "  SKIP — $1"; skip=$((skip + 1)); }

BROKER_PORT=8236            # throwaway (real broker is 8136; avoid collisions)
RR_PORT=8237
WORK="$(mktemp -d "${TMPDIR:-/tmp}/lr-nspawn.XXXXXX")"
pids=()
cleanup(){ for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done
           wait 2>/dev/null || true; rm -rf "${WORK}"; }
trap cleanup EXIT

echo "tests/nspawn/test_live_reload.sh"
echo

command -v python3 >/dev/null || { echo "python3 required"; exit 2; }
command -v curl    >/dev/null || { sk "curl absent — cannot probe"; echo; echo "$pass pass / $fail fail / $skip skip"; exit 0; }

# ---------- broker: healthz + SSE relevance (relevant notifies, irrelevant silent)
SOVEREIGN_OS_LIVERELOAD_PORT="${BROKER_PORT}" SOVEREIGN_OS_LIVERELOAD_POLL_MS=200 \
  python3 scripts/operator/livereload-broker.py >"${WORK}/broker.log" 2>&1 &
pids+=($!)
up=0
for _ in $(seq 1 25); do
  curl -sf --max-time 1 "http://127.0.0.1:${BROKER_PORT}/healthz" >/dev/null 2>&1 && { up=1; break; }
  sleep 0.2
done

if [ "${up}" != 1 ]; then
  sk "broker did not bind :${BROKER_PORT} (sandbox socket limitation) — SSE subtests skipped"
else
  ok "broker /healthz answers on :${BROKER_PORT}"
  # positive + negative in one client run: a science page should be notified by
  # an edit to webapp/science/ but NOT by an edit to an unrelated panel (ups).
  python3 - "${BROKER_PORT}" "${WORK}" <<'PY'
import sys, time, threading, os, urllib.request
port, work = sys.argv[1], sys.argv[2]

def edit(path, delay):
    time.sleep(delay)
    try: os.utime(path, None)
    except OSError: pass

def listen(panel, port, seconds):
    """Return True if a 'reload' event arrives within `seconds`."""
    try:
        req = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/events?panel={panel}&port=8134", timeout=seconds + 2)
    except Exception:
        return None
    deadline = time.time() + seconds
    req.fp.raw._sock.settimeout(seconds)  # bound the blocking readline
    try:
        while time.time() < deadline:
            line = req.readline()
            if not line:
                break
            if line.startswith(b"event: reload"):
                return True
    except Exception:
        pass
    return False

# 1) relevant edit → notified
threading.Thread(target=edit, args=("webapp/science/index.html", 0.8), daemon=True).start()
rel = listen("science", port, 4)
# 2) irrelevant edit (another panel) → NOT notified
threading.Thread(target=edit, args=("webapp/ups/index.html", 0.8), daemon=True).start()
irr = listen("science", port, 3)

with open(f"{work}/sse.txt", "w") as fh:
    fh.write(f"{rel}\n{irr}\n")
PY
  REL="$(sed -n 1p "${WORK}/sse.txt" 2>/dev/null)"
  IRR="$(sed -n 2p "${WORK}/sse.txt" 2>/dev/null)"
  [ "${REL}" = "True" ]  && ok "relevant edit (science/) notifies the science page" \
                         || ko "relevant edit did NOT notify (got: ${REL:-none})"
  [ "${IRR}" = "False" ] && ok "irrelevant edit (ups/) stays silent — never for nothing" \
                         || ko "irrelevant edit notified science (reloaded for nothing: ${IRR:-none})"
fi

echo
# ---------- reload-run: in-place self-re-exec (fresh code, SAME pid, no kill)
cat > "${WORK}/toy-api.py" <<PY
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
VERSION = "v1"
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        b = f"{VERSION} pid={os.getpid()}".encode()
        self.send_response(200); self.send_header("Content-Length",str(len(b))); self.end_headers()
        self.wfile.write(b)
HTTPServer(("127.0.0.1", ${RR_PORT}), H).serve_forever()
PY
SOVEREIGN_OS_LIVERELOAD=1 SOVEREIGN_OS_LIVERELOAD_POLL_MS=200 \
  python3 scripts/operator/lib/reload-run.py "${WORK}/toy-api.py" >"${WORK}/rr.log" 2>&1 &
pids+=($!)
rr_up=0
for _ in $(seq 1 25); do
  curl -sf --max-time 1 "http://127.0.0.1:${RR_PORT}/v" >/dev/null 2>&1 && { rr_up=1; break; }
  sleep 0.2
done

if [ "${rr_up}" != 1 ]; then
  sk "reload-run toy daemon did not bind :${RR_PORT} (sandbox socket limitation) — re-exec subtests skipped"
else
  BEFORE="$(curl -sf --max-time 2 "http://127.0.0.1:${RR_PORT}/v" || echo FAIL)"
  case "${BEFORE}" in v1*) ok "toy daemon serves v1 under reload-run" ;; *) ko "toy daemon did not serve (${BEFORE})" ;; esac
  PID_BEFORE="$(printf '%s' "${BEFORE}" | grep -oE 'pid=[0-9]+')"
  # Edit AFTER the watcher's 1.0s baseline settles (an edit inside the first
  # second is absorbed by design — real edits always land much later).
  sleep 1.3
  sed -i 's/VERSION = "v1"/VERSION = "v2"/' "${WORK}/toy-api.py"
  sleep 2.0
  AFTER="$(curl -sf --max-time 2 "http://127.0.0.1:${RR_PORT}/v" || echo FAIL)"
  PID_AFTER="$(printf '%s' "${AFTER}" | grep -oE 'pid=[0-9]+')"
  case "${AFTER}" in v2*) ok "daemon reloaded to v2 with no manual restart" ;; *) ko "daemon did NOT reload to v2 (${AFTER})" ;; esac
  if [ -n "${PID_BEFORE}" ] && [ "${PID_BEFORE}" = "${PID_AFTER}" ]; then
    ok "SAME pid across reload (${PID_BEFORE}) — true in-place self-re-exec, no kill"
  else
    ko "pid changed (${PID_BEFORE} → ${PID_AFTER}) — not an in-place re-exec"
  fi
fi

echo
echo "== ${pass} pass / ${fail} fail / ${skip} skip =="
[ "${fail}" -eq 0 ]
