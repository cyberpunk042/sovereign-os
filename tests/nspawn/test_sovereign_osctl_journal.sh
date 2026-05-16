#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_journal.sh
#
# Layer 3 test for `sovereign-osctl journal` (Round 91).
# Verifies the 4 subverbs against a synthetic Layer A log dir.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_sovereign_osctl_journal.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

logdir="${tmp}/logs"
mkdir -p "${logdir}"

# Two well-formed JSONL files
cat > "${logdir}/build-20260516T010000Z.jsonl" <<'EOF'
{"ts":"2026-05-16T01:00:00+00:00","level":"info","step":"build","msg":"start"}
{"ts":"2026-05-16T01:00:01+00:00","level":"info","step":"build","msg":"phase 1"}
{"ts":"2026-05-16T01:00:02+00:00","level":"warn","step":"build","msg":"slow operation"}
{"ts":"2026-05-16T01:00:03+00:00","level":"error","step":"build","msg":"file not found"}
{"ts":"2026-05-16T01:00:04+00:00","level":"info","step":"build","msg":"done"}
EOF

cat > "${logdir}/build-20260516T020000Z.jsonl" <<'EOF'
{"ts":"2026-05-16T02:00:00+00:00","level":"info","step":"render","msg":"ok"}
EOF

# Empty file
touch "${logdir}/build-20260516T030000Z.jsonl"

# Malformed file (one bad line + one good)
cat > "${logdir}/build-20260516T040000Z.jsonl" <<'EOF'
this is not json at all
{"ts":"2026-05-16T04:00:00+00:00","level":"info","step":"sign","msg":"signed"}
EOF

# ---------- list ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" journal list 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "log dir: ${logdir}" <<< "${out}"; then
  ok "list reports the log dir"
else
  ko "list dir-report broken (rc=${rc})"
fi
if grep -q "build-20260516T010000Z.jsonl  *5" <<< "${out}"; then
  ok "list counts 5 events in first file"
else
  ko "list event-count wrong"
fi
if grep -q "FIRST → LAST" <<< "${out}"; then
  ok "list emits header row with timestamp range"
else
  ko "list header missing"
fi

# ---------- list with empty dir ----------
empty="${tmp}/empty"; mkdir -p "${empty}"
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${empty}" "${OSCTL}" journal list 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "no .jsonl files" <<< "${out}"; then
  ok "list on empty dir → exit 0 + clear message"
else
  ko "list empty-dir broken"
fi

# ---------- list with no dir at all ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${tmp}/missing-$$" "${OSCTL}" journal list 2>&1)"
rc=$?
set -e
# Fallback path: if SOVEREIGN_OS_LOG_DIR doesn't exist, cmd_journal
# tries /var/log/sovereign-os/ then ~/.sovereign-os/log/. Either it
# finds a real one or reports "no Layer A log dir found".
# We just check the verb exits cleanly.
if [ "${rc}" -eq 0 ]; then
  ok "list with missing SOVEREIGN_OS_LOG_DIR → falls through cleanly"
else
  ko "fallthrough broken (rc=${rc})"
fi

# ---------- show <basename> ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" journal show build-20260516T010000Z.jsonl 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "TS .*LEVEL .*STEP .*MSG" <<< "${out}" && grep -q "INFO.*build.*start" <<< "${out}"; then
  ok "show pretty-prints events as a table"
else
  ko "show output broken (rc=${rc})"
fi

# ---------- show resolves bare names ----------
# Make a name that's the file without dir
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" journal show build-20260516T020000Z 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "render" <<< "${out}"; then
  ok "show resolves bare basename (no .jsonl suffix)"
else
  ko "show bare-name resolution broken"
fi

# ---------- show missing file ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" journal show no-such-file 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "no log file matches" <<< "${out}"; then
  ok "show missing → exit 1 + 'no log file matches'"
else
  ko "show missing-file gate broken (rc=${rc})"
fi

# ---------- show no arg ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" journal show 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "usage:" <<< "${out}"; then
  ok "show without arg → exit 2 + usage"
else
  ko "show no-arg gate broken (rc=${rc})"
fi

# ---------- show malformed file → marks line + keeps going ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" journal show build-20260516T040000Z.jsonl 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "malformed" <<< "${out}" && grep -q "signed" <<< "${out}"; then
  ok "show handles malformed lines gracefully (marks + continues)"
else
  ko "show malformed-handling broken"
fi

# ---------- tail (default 3) ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" journal tail 2>&1)"
rc=$?
set -e
sep_count="$(grep -c '^===== ' <<< "${out}" || true)"
if [ "${rc}" -eq 0 ] && [ "${sep_count}" -eq 3 ]; then
  ok "tail default → 3 file blocks"
else
  ko "tail default broken (sep_count=${sep_count})"
fi

# ---------- tail N=1 ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" journal tail 1 2>&1)"
set -e
sep_count="$(grep -c '^===== ' <<< "${out}" || true)"
if [ "${sep_count}" -eq 1 ]; then
  ok "tail N=1 → exactly 1 block"
else
  ko "tail N=1 broken (sep_count=${sep_count})"
fi

# ---------- tail bad N ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" journal tail not-a-number 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "tail count must be a non-negative integer" <<< "${out}"; then
  ok "tail bad-N → exit 2"
else
  ko "tail bad-N gate broken (rc=${rc})"
fi

# ---------- errors ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" journal errors 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "WARN.*slow operation" <<< "${out}" && grep -q "ERROR.*file not found" <<< "${out}"; then
  ok "errors surfaces both warn AND error entries"
else
  ko "errors verb broken"
fi
# errors verb should NOT surface info-level entries
if ! grep -q "INFO.*phase 1" <<< "${out}"; then
  ok "errors verb filters out info-level entries"
else
  ko "errors verb leaked info entries"
fi

# ---------- errors with no warn/error in logs ----------
clean_logdir="${tmp}/clean_logdir"; mkdir -p "${clean_logdir}"
cat > "${clean_logdir}/clean.jsonl" <<'EOF'
{"ts":"2026-05-16T05:00:00+00:00","level":"info","step":"build","msg":"all good"}
EOF
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${clean_logdir}" "${OSCTL}" journal errors 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "no warn/error entries" <<< "${out}"; then
  ok "errors on clean dir → exit 0 + 'no warn/error entries'"
else
  ko "errors clean-dir broken"
fi

# ---------- unknown subverb ----------
set +e
out="$(SOVEREIGN_OS_LOG_DIR="${logdir}" "${OSCTL}" journal bogus 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown journal subcommand: bogus" <<< "${out}"; then
  ok "unknown subverb → exit 2 + clear error"
else
  ko "unknown-subverb gate broken (rc=${rc})"
fi

# ---------- help text ----------
help_out="$("${OSCTL}" help 2>&1)"
for kw in "journal list" "journal show" "journal tail" "journal errors"; do
  if grep -q "${kw}" <<< "${help_out}"; then
    ok "help documents: ${kw}"
  else
    ko "help missing: ${kw}"
  fi
done

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_sovereign_osctl_journal: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
