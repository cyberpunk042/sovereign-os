#!/usr/bin/env bash
# tests/nspawn/test_auditor_guardian_core.sh
#
# Layer 3 test for R155 — scripts/auditor/guardian-core.py +
# systemd/system/sovereign-guardian-core.service (master spec § 10).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/auditor/guardian-core.py"
UNIT="${__REPO_ROOT}/systemd/system/sovereign-guardian-core.service"
INSTALLER="${__REPO_ROOT}/scripts/auditor/install.sh"

echo "tests/nspawn/test_auditor_guardian_core.sh"
echo

# ---------- files present ----------
[ -f "${SCRIPT}" ]    && ok "guardian-core.py present"    || { ko "missing"; exit 1; }
[ -f "${UNIT}" ]      && ok "sovereign-guardian-core.service present" || ko "unit missing"
[ -f "${INSTALLER}" ] && ok "install.sh present"          || ko "installer missing"
[ -x "${SCRIPT}" ]    && ok "guardian-core.py executable" || ko "not executable"

# ---------- syntactic sanity ----------
if python3 -c "import ast; ast.parse(open('${SCRIPT}').read())" 2>/dev/null; then
  ok "python3 parses guardian-core.py"
else
  ko "python parse error"
fi

# ---------- master spec citations ----------
if grep -q "master spec § 10" "${SCRIPT}"; then
  ok "script cites master spec § 10"
else
  ko "master spec § 10 missing from script"
fi
if grep -q "master spec § 10" "${UNIT}"; then
  ok "unit cites master spec § 10"
else
  ko "master spec § 10 missing from unit"
fi

# ---------- master spec § 10.1 verbatim element check ----------
for kw in "tetragon" "podman" "kill" "security_audit.log" "SIGKILL" "process" "syscall"; do
  if grep -q "${kw}" "${SCRIPT}"; then
    ok "script mentions ${kw}"
  else
    ko "script missing ${kw}"
  fi
done

# ---------- master spec § 10.2 verbatim unit declarations ----------
for kw in "After=tetragon.service" "Requires=tetragon.service" "ExecStart=/usr/local/bin/guardian-core" "Restart=always"; do
  if grep -q "${kw}" "${UNIT}"; then
    ok "unit declares: ${kw}"
  else
    ko "unit missing: ${kw}"
  fi
done

# ---------- defense-in-depth hardening on the unit ----------
for kw in "ProtectSystem=strict" "NoNewPrivileges=true" "PrivateTmp=true"; do
  if grep -q "${kw}" "${UNIT}"; then
    ok "unit hardened: ${kw}"
  else
    ko "unit missing hardening: ${kw}"
  fi
done

# ---------- installer DRY-RUN ----------
set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 bash "${INSTALLER}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "DRY-RUN" <<< "${out}"; then
  ok "installer DRY-RUN exit 0 + surfaces intent"
else
  ko "installer DRY-RUN broken (rc=${rc} out=${out:0:200})"
fi
for kw in "master spec § 10" "guardian-core" "tetragon.service"; do
  if grep -q "${kw}" <<< "${out}"; then
    ok "installer DRY-RUN surfaces: ${kw}"
  else
    ko "installer DRY-RUN missing: ${kw}"
  fi
done

# ---------- parse + trigger predicate ----------
out="$(python3 -c "
import sys, importlib.util
spec = importlib.util.spec_from_file_location('g','${SCRIPT}')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
# SIGKILL action → trigger
t,_ = m.parse_event('{\"action\":\"SIGKILL\"}')
print('sigkill', t)
# action contains 'process' → trigger
t,_ = m.parse_event('{\"action\":\"PROCESS_EXEC\"}')
print('process', t)
# benign LOG → no trigger
t,_ = m.parse_event('{\"action\":\"LOG\"}')
print('log', t)
# bad json → False + empty
t,e = m.parse_event('garbage')
print('badjson', t, len(e))
")"
grep -q "^sigkill True"   <<< "${out}" && ok "parse: SIGKILL → trigger"   || ko "parse: SIGKILL trigger broken"
grep -q "^process True"   <<< "${out}" && ok "parse: action~process → trigger" || ko "parse: process trigger broken"
grep -q "^log False"      <<< "${out}" && ok "parse: benign LOG → no trigger"  || ko "parse: benign LOG misfired"
grep -q "^badjson False 0" <<< "${out}" && ok "parse: bad JSON returns (False, {})" || ko "parse: bad JSON broken"

# ---------- end-to-end loop via FIFO + fake podman binary ----------
TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "${TMPDIR_TEST}"' EXIT
# Tetragon --export-filename writes a regular FILE (not the socket/FIFO the
# original M084 contract assumed). Model that reality — EOF on a file is the
# normal caught-up state, so guardian must tail past it, not exit.
EVENTS="${TMPDIR_TEST}/events"
: > "${EVENTS}"

set +e
GUARDIAN_SOCKET_PATH="${EVENTS}" \
GUARDIAN_AUDIT_LOG="${TMPDIR_TEST}/audit.log" \
GUARDIAN_PODMAN_BIN=/bin/true \
GUARDIAN_POLL_INTERVAL_SEC=0.1 \
SOVEREIGN_OS_METRICS_DIR="${TMPDIR_TEST}/metrics" \
  timeout 6 python3 "${SCRIPT}" > "${TMPDIR_TEST}/stdout" 2>&1 &
GPID=$!
set -e
# Guardian seeks to END on open, so events must be APPENDED after it starts —
# a restart must never replay (or re-kill on) historical events.
sleep 1
{
  echo '{"action":"SIGKILL","process":{"docker":"cAAA","binary":"/bin/evil"},"syscall":{"name":"sys_execve"}}'
  echo '{"action":"LOG","process":{"docker":"cBBB"}}'
} >> "${EVENTS}"
sleep 1.5

# New contract (supersedes M084/E0815's socket-EOF-restart mechanism; see
# backlog note 2026-08-20-guardian-file-export-tail-follow): the export is a
# regular FILE where EOF is normal, so guardian MUST keep tailing rather than
# exit. Proven by it still running here + no perimeter-blind log. Locked by
# tests/lint/test_guardian_core_service_bidir.py::test_script_follows_export_file_past_eof.
if kill -0 "${GPID}" 2>/dev/null; then
  ok "guardian keeps tailing past EOF (file export, no exit-on-EOF crash-loop)"
else
  ko "guardian exited on EOF (regression: crash-loops against Tetragon file export)"
fi
if ! grep -q "perimeter blind" "${TMPDIR_TEST}/stdout"; then
  ok "no perimeter-blind exit (tail-follow honored)"
else
  ko "guardian logged perimeter-blind exit (regressed to socket-EOF behavior)"
fi
kill "${GPID}" 2>/dev/null || true
wait "${GPID}" 2>/dev/null || true

# audit log got exactly one VIOLATION line
if [ -f "${TMPDIR_TEST}/audit.log" ] && grep -q "Neutralized /bin/evil (cAAA)" "${TMPDIR_TEST}/audit.log"; then
  ok "audit.log appended on SIGKILL event"
else
  ko "audit.log content wrong: $(cat "${TMPDIR_TEST}/audit.log" 2>/dev/null)"
fi

# benign LOG event MUST NOT produce a violation line
if [ -f "${TMPDIR_TEST}/audit.log" ] && ! grep -q "cBBB" "${TMPDIR_TEST}/audit.log"; then
  ok "benign LOG did not produce violation"
else
  ko "benign LOG incorrectly triggered neutralization"
fi

# Layer B metrics emitted
if [ -f "${TMPDIR_TEST}/metrics/sovereign-os-auditor.prom" ]; then
  ok "Layer B metric file produced"
  if grep -q "sovereign_os_auditor_neutralization_total" "${TMPDIR_TEST}/metrics/sovereign-os-auditor.prom"; then
    ok "metric: neutralization_total emitted"
  else
    ko "metric: neutralization_total missing"
  fi
  if grep -q "sovereign_os_auditor_event_parse_total" "${TMPDIR_TEST}/metrics/sovereign-os-auditor.prom"; then
    ok "metric: event_parse_total emitted"
  else
    ko "metric: event_parse_total missing"
  fi
else
  ko "Layer B metric file absent"
fi

# ---------- missing socket → FATAL STRUCTURAL FRICTION ----------
set +e
out="$(GUARDIAN_SOCKET_PATH=/tmp/no-such-tetragon-stream-$$ \
       python3 "${SCRIPT}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "FATAL STRUCTURAL FRICTION" <<< "${out}"; then
  ok "missing socket → FATAL STRUCTURAL FRICTION + non-zero rc"
else
  ko "missing-socket path broken (rc=${rc} out=${out:0:200})"
fi

# ---------- DRY-RUN suppresses kill + audit write ----------
TMPDIR2="$(mktemp -d)"
FIFO2="${TMPDIR2}/events"
mkfifo "${FIFO2}"
echo '{"action":"SIGKILL","process":{"docker":"cZZZ","binary":"/bin/x"},"syscall":{"name":"sys_execve"}}' > "${FIFO2}" &

set +e
GUARDIAN_SOCKET_PATH="${FIFO2}" \
GUARDIAN_AUDIT_LOG="${TMPDIR2}/audit.log" \
GUARDIAN_DRY_RUN=1 \
SOVEREIGN_OS_METRICS_DIR="${TMPDIR2}/metrics" \
  timeout 5 python3 "${SCRIPT}" > "${TMPDIR2}/stdout" 2>&1
set -e
wait 2>/dev/null || true

if [ ! -f "${TMPDIR2}/audit.log" ]; then
  ok "DRY-RUN did not touch audit log"
else
  ko "DRY-RUN wrote audit log unexpectedly"
fi
if grep -q "DRY-RUN" "${TMPDIR2}/stdout"; then
  ok "DRY-RUN surfaces intent on stdout/stderr"
else
  ko "DRY-RUN intent not surfaced"
fi
rm -rf "${TMPDIR2}"

echo
total=$((pass + fail))
echo "test_auditor_guardian_core: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
