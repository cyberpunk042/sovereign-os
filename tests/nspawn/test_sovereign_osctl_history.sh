#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_history.sh
#
# Layer 3 test for sovereign-osctl history (Round 107).
# Verifies per-run summary derivation from synthetic JSONL log files.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_sovereign_osctl_history.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

logdir="${tmp}/logs"
mkdir -p "${logdir}"

# Synthetic run 1: clean sain-01 run, 2 step PASS, no errors
cat > "${logdir}/build-20260101T010000Z.jsonl" <<'EOF'
{"ts":"2026-01-01T01:00:00+00:00","level":"info","step":"build","msg":"loaded profile: sain-01 (/path/sain-01.yaml)"}
{"ts":"2026-01-01T01:00:01+00:00","level":"info","step":"build","msg":"━━━ STEP preflight-network — installer-time network reachability check ━━━"}
{"ts":"2026-01-01T01:00:30+00:00","level":"info","step":"build","msg":"preflight-network: PASS"}
{"ts":"2026-01-01T01:00:31+00:00","level":"info","step":"build","msg":"━━━ STEP preflight-storage — storage layout reality check ━━━"}
{"ts":"2026-01-01T01:01:30+00:00","level":"info","step":"build","msg":"preflight-storage: PASS"}
EOF

# Synthetic run 2: minimal profile with errors
cat > "${logdir}/build-20260101T020000Z.jsonl" <<'EOF'
{"ts":"2026-01-01T02:00:00+00:00","level":"info","step":"build","msg":"loaded profile: minimal"}
{"ts":"2026-01-01T02:00:01+00:00","level":"info","step":"build","msg":"━━━ STEP friction-audit-spec — spec-time check ━━━"}
{"ts":"2026-01-01T02:00:02+00:00","level":"error","step":"build","msg":"  FAIL — at least one GPU declared"}
{"ts":"2026-01-01T02:00:03+00:00","level":"error","step":"build","msg":"friction-audit-spec: FAIL"}
EOF

# Synthetic run 3: empty file
touch "${logdir}/build-20260101T030000Z.jsonl"

# ---------- list ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" history list 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "list exits 0"
else
  ko "list broken (rc=${rc})"
fi

if grep -qE "20260101T010000Z\s+sain-01\s+\S+\s+\S+\s+ok" <<< "${out}"; then
  ok "run 1 reported as sain-01 / ok"
else
  ko "run 1 summary wrong"
fi

if grep -qE "20260101T020000Z\s+minimal\s+\S+\s+\S+\s+FAIL" <<< "${out}"; then
  ok "run 2 reported as minimal / FAIL (errors present)"
else
  ko "run 2 summary wrong"
fi

# Empty file → empty result
if grep -qE "20260101T030000Z.*empty" <<< "${out}"; then
  ok "empty file → 'empty' result"
else
  ko "empty-file handling broken"
fi

# Header row
if grep -q "RUN ID.*PROFILE.*STEPS.*RESULT" <<< "${out}"; then
  ok "list emits header row"
else
  ko "list header missing"
fi

# Duration computed (run 1: 60s + 60s ≈ 1m30s)
if grep -qE "1m30s|90s" <<< "${out}"; then
  ok "duration computed from first→last ts (run 1 ≈ 1m30s)"
else
  ko "duration computation broken"
fi

# ---------- list with no logs ----------
empty_dir="${tmp}/empty"; mkdir -p "${empty_dir}"
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${empty_dir}" "${OSCTL}" history list 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "no .jsonl files" <<< "${out}"; then
  ok "list on empty dir → exit 0 + 'no .jsonl files'"
else
  ko "list empty-dir broken"
fi

# ---------- show with full run-id ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" history show 20260101T010000Z 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "show exits 0 on real run-id"
else
  ko "show broken (rc=${rc})"
fi
if grep -q "profile:  sain-01" <<< "${out}"; then
  ok "show surfaces profile from 'loaded profile:' event"
else
  ko "show profile detection broken"
fi
if grep -q "events:   5" <<< "${out}"; then
  ok "show reports event count (5)"
else
  ko "show event count wrong"
fi
if grep -q "preflight-network" <<< "${out}" && grep -q "PASS" <<< "${out}"; then
  ok "show enumerates STEP markers + their results"
else
  ko "show step enumeration broken"
fi

# ---------- show resolves bare run-id (no 'build-' prefix, no .jsonl) ----------
# already tested above with bare run-id; verify alternate forms
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" history show build-20260101T010000Z.jsonl 2>&1)"
set -e
if grep -q "profile:  sain-01" <<< "${out}"; then
  ok "show resolves full filename"
else
  ko "show full-filename resolution broken"
fi

# ---------- show missing ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" history show no-such-run 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "no log file matches" <<< "${out}"; then
  ok "show missing run-id → exit 1 + clear error"
else
  ko "show missing-run gate broken (rc=${rc})"
fi

# ---------- show without arg ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" history show 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "usage:" <<< "${out}"; then
  ok "show without arg → exit 2 + usage"
else
  ko "show no-arg gate broken (rc=${rc})"
fi

# ---------- show surfaces errors for fail run ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" history show 20260101T020000Z 2>&1)"
set -e
if grep -q "errors: 2" <<< "${out}"; then
  ok "show counts errors in summary header"
else
  ko "show error count wrong"
fi
if grep -q "friction-audit-spec" <<< "${out}"; then
  ok "show surfaces failing step id"
else
  ko "failing step not surfaced"
fi

# ---------- unknown subverb ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" history bogus 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown history subcommand: bogus" <<< "${out}"; then
  ok "unknown subverb → exit 2 + clear error"
else
  ko "unknown-subverb gate broken (rc=${rc})"
fi

# ---------- help ----------
help_out="$("${OSCTL}" help 2>&1)"
for kw in "history list" "history show"; do
  if grep -q "${kw}" <<< "${help_out}"; then
    ok "help documents: ${kw}"
  else
    ko "help missing: ${kw}"
  fi
done

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_sovereign_osctl_history: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
