#!/usr/bin/env bash
# tests/nspawn/test_log_rotate.sh
#
# Layer 3 test for scripts/hooks/recurrent/log-rotate.sh.
# Validates the rotation + archive + purge passes against a synthetic
# log directory with timestamps set via touch -d.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

ROTATE="${__REPO_ROOT}/scripts/hooks/recurrent/log-rotate.sh"
[ -x "${ROTATE}" ] || { echo "FAIL: log-rotate.sh not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_LOG_RETENTION_DAYS=14
export SOVEREIGN_OS_LOG_ARCHIVE_DAYS=90
export SOVEREIGN_OS_NONINTERACTIVE=1

mkdir -p "${SOVEREIGN_OS_LOG_DIR}"

echo "tests/nspawn/test_log_rotate.sh"
echo "  log dir: ${SOVEREIGN_OS_LOG_DIR}"
echo

# ----------- seed test corpus ---------------

# Fresh log (must NOT rotate)
touch "${SOVEREIGN_OS_LOG_DIR}/build-fresh.jsonl"
echo '{"event":"fresh"}' > "${SOVEREIGN_OS_LOG_DIR}/build-fresh.jsonl"

# Old log (must rotate)
touch -d '30 days ago' "${SOVEREIGN_OS_LOG_DIR}/build-old.jsonl"
echo '{"event":"old"}' > "${SOVEREIGN_OS_LOG_DIR}/build-old.jsonl"
touch -d '30 days ago' "${SOVEREIGN_OS_LOG_DIR}/build-old.jsonl"

# Ancient archive file (must purge)
mkdir -p "${SOVEREIGN_OS_LOG_DIR}/archive"
touch "${SOVEREIGN_OS_LOG_DIR}/archive/build-ancient.jsonl.gz"
touch -d '120 days ago' "${SOVEREIGN_OS_LOG_DIR}/archive/build-ancient.jsonl.gz"

# Recent archive file (must remain)
touch -d '30 days ago' "${SOVEREIGN_OS_LOG_DIR}/archive/build-recentish.jsonl.gz"

# Large ACTIVE log (recent mtime, over the size cap → must size-rotate even
# though it's fresh — the disk-fill case for continuously-appended logs).
export SOVEREIGN_OS_LOG_MAX_BYTES=2048
head -c 5000 /dev/zero | tr '\0' 'x' > "${SOVEREIGN_OS_LOG_DIR}/notify.jsonl"
# (build-fresh.jsonl above is tiny — must NOT size-rotate.)

# ----------- run rotation ---------------

"${ROTATE}" >/dev/null 2>&1
rc=$?

if [ "${rc}" -eq 0 ]; then
  ok "log-rotate exit code 0"
else
  ko "log-rotate exit code ${rc}"
fi

# ----------- assertions ---------------

# Fresh log must remain
if [ -f "${SOVEREIGN_OS_LOG_DIR}/build-fresh.jsonl" ]; then
  ok "fresh log retained (within retention window)"
else
  ko "fresh log incorrectly rotated"
fi

# Old log must have moved + gzipped
if [ ! -f "${SOVEREIGN_OS_LOG_DIR}/build-old.jsonl" ]; then
  ok "old log removed from primary dir"
else
  ko "old log still in primary dir (rotation failed)"
fi

if [ -f "${SOVEREIGN_OS_LOG_DIR}/archive/build-old.jsonl.gz" ]; then
  ok "old log archived as build-old.jsonl.gz"
else
  ko "old log not present in archive/"
fi

# Old archive content should still be valid gzip
if [ -f "${SOVEREIGN_OS_LOG_DIR}/archive/build-old.jsonl.gz" ]; then
  if gzip -t "${SOVEREIGN_OS_LOG_DIR}/archive/build-old.jsonl.gz" 2>/dev/null; then
    ok "archived gzip is valid (gzip -t passes)"
  else
    ko "archived gzip is corrupt"
  fi
fi

# Content preserved through rotation
if [ -f "${SOVEREIGN_OS_LOG_DIR}/archive/build-old.jsonl.gz" ]; then
  decompressed="$(gunzip -c "${SOVEREIGN_OS_LOG_DIR}/archive/build-old.jsonl.gz")"
  if grep -q "old" <<< "${decompressed}"; then
    ok "archived content preserved (decompresses to original)"
  else
    ko "archived content does NOT match input"
  fi
fi

# Ancient archive must have been purged
if [ ! -f "${SOVEREIGN_OS_LOG_DIR}/archive/build-ancient.jsonl.gz" ]; then
  ok "ancient archive purged (>${SOVEREIGN_OS_LOG_ARCHIVE_DAYS}d)"
else
  ko "ancient archive not purged"
fi

# Recent-ish archive must remain
if [ -f "${SOVEREIGN_OS_LOG_DIR}/archive/build-recentish.jsonl.gz" ]; then
  ok "recent-ish archive retained (within archive window)"
else
  ko "recent-ish archive incorrectly purged"
fi

# Large active log must be SIZE-rotated (gone from primary, archived) even
# though its mtime is fresh — the unbounded-growth fix.
if [ ! -f "${SOVEREIGN_OS_LOG_DIR}/notify.jsonl" ]; then
  ok "large active notify.jsonl size-rotated out of primary dir"
else
  ko "large active notify.jsonl NOT size-rotated (would grow unbounded)"
fi
if ls "${SOVEREIGN_OS_LOG_DIR}/archive/"notify.jsonl.*.gz >/dev/null 2>&1; then
  ok "size-rotated notify.jsonl archived (timestamped .gz)"
else
  ko "size-rotated notify.jsonl not found in archive"
fi
# Tiny fresh log must NOT be size-rotated.
if [ -f "${SOVEREIGN_OS_LOG_DIR}/build-fresh.jsonl" ]; then
  ok "tiny fresh log not size-rotated (under cap)"
else
  ko "tiny fresh log wrongly size-rotated"
fi

# ----------- idempotency: re-run must not re-rotate anything ---------------
# log_init writes a fresh build-<timestamp>.jsonl per invocation as a
# side-effect — that's the rotation's own session log, not state being
# mutated by the rotation logic. Check the load-bearing invariants
# directly instead.

fresh_count_before="$(find "${SOVEREIGN_OS_LOG_DIR}" -maxdepth 1 -name '*.jsonl' -type f -newer "${SOVEREIGN_OS_LOG_DIR}/archive" -mtime "-${SOVEREIGN_OS_LOG_RETENTION_DAYS}" | wc -l)"
archive_count_before="$(find "${SOVEREIGN_OS_LOG_DIR}/archive" -type f | wc -l)"
"${ROTATE}" >/dev/null 2>&1
archive_count_after="$(find "${SOVEREIGN_OS_LOG_DIR}/archive" -type f | wc -l)"

if [ "${archive_count_after}" -eq "${archive_count_before}" ]; then
  ok "re-run is idempotent (archive count unchanged)"
else
  ko "re-run added/removed archive entries (before=${archive_count_before} after=${archive_count_after})"
fi

# ----------- dry-run mode ---------------

# Add another old log; SOVEREIGN_OS_DRY_RUN=1 should NOT rotate it
touch -d '30 days ago' "${SOVEREIGN_OS_LOG_DIR}/build-old2.jsonl"
SOVEREIGN_OS_DRY_RUN=1 "${ROTATE}" >/dev/null 2>&1
if [ -f "${SOVEREIGN_OS_LOG_DIR}/build-old2.jsonl" ]; then
  ok "DRY-RUN does not actually rotate (old2 still in primary dir)"
else
  ko "DRY-RUN mutated state — not honoring SOVEREIGN_OS_DRY_RUN"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_log_rotate: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
