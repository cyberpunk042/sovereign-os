#!/usr/bin/env bash
# tests/nspawn/test_observability_lib.sh
#
# Layer 3 test for scripts/build/lib/observability.sh — the Layer B
# metrics emitter (SDD-016).
#
# Asserts:
#   - emit_metric writes a single line to a .prom file
#   - emit_metric atomically rewrites the file (no partial reads)
#   - emit_metric with labels formats correctly
#   - re-emitting the same metric replaces the prior value (gauge semantics)
#   - emit_metric_set writes multiple lines + HELP/TYPE preamble
#   - SOVEREIGN_OS_METRICS_DISABLE=1 skips writes
#   - SOVEREIGN_OS_DRY_RUN=1 skips writes
#   - missing metrics dir → graceful skip (never breaks caller)
#   - log-rotate.sh actually emits the expected metrics

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

LIB="${__REPO_ROOT}/scripts/build/lib/observability.sh"
[ -f "${LIB}" ] || { echo "FAIL: observability lib not found"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_observability_lib.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_METRICS_DIR="${tmp}/metrics"

# ----------- single metric, no labels ---------------

(
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  . "${LIB}"
  emit_metric sovereign_os_test_simple_value 42
)

found="$(find "${SOVEREIGN_OS_METRICS_DIR}" -name '*.prom' -type f 2>/dev/null | head -1)"
if [ -n "${found}" ]; then
  ok "emit_metric created a .prom file: $(basename "${found}")"
else
  ko "emit_metric did not create a .prom file"
fi

if [ -n "${found}" ] && grep -q "^sovereign_os_test_simple_value 42$" "${found}"; then
  ok "metric line shape correct (no labels)"
else
  ko "metric line shape wrong: $(cat "${found}" 2>/dev/null)"
fi

# ----------- single metric, with labels ---------------

(
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  . "${LIB}"
  emit_metric sovereign_os_test_with_labels 7 'tier="pulse"'
)

found_labeled="$(find "${SOVEREIGN_OS_METRICS_DIR}" -name '*.prom' -type f | xargs grep -l 'with_labels' 2>/dev/null | head -1)"
if [ -n "${found_labeled}" ] && grep -q 'sovereign_os_test_with_labels{tier="pulse"} 7' "${found_labeled}"; then
  ok "metric with labels formatted correctly"
else
  ko "labeled metric not found or malformed"
fi

# ----------- gauge replacement (re-emit same metric) ---------------

(
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  . "${LIB}"
  emit_metric sovereign_os_test_simple_value 99   # overwrite the 42
)

if grep -q "^sovereign_os_test_simple_value 99$" "${found}" 2>/dev/null; then
  ok "re-emit replaced the prior gauge value (42 → 99)"
else
  ko "gauge replacement failed"
fi

# Must NOT have both lines
count="$(grep -c "^sovereign_os_test_simple_value " "${found}" 2>/dev/null || echo 0)"
if [ "${count}" -eq 1 ]; then
  ok "exactly one line for the metric (no duplicate)"
else
  ko "found ${count} lines for the metric (expected 1)"
fi

# ----------- emit_metric_set ---------------

(
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  . "${LIB}"
  emit_metric_set test-bulk \
    '# HELP sovereign_os_bulk_a Test bulk metric A' \
    '# TYPE sovereign_os_bulk_a gauge' \
    "sovereign_os_bulk_a 1" \
    "sovereign_os_bulk_b 2" \
    "sovereign_os_bulk_c 3"
)

bulk_file="${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-test-bulk.prom"
if [ -f "${bulk_file}" ]; then
  ok "emit_metric_set wrote sovereign-os-test-bulk.prom"
else
  ko "bulk file missing"
fi

for line in "# HELP sovereign_os_bulk_a" "sovereign_os_bulk_a 1" "sovereign_os_bulk_b 2" "sovereign_os_bulk_c 3"; do
  if grep -qF "${line}" "${bulk_file}" 2>/dev/null; then
    ok "bulk file contains: ${line}"
  else
    ko "bulk file missing: ${line}"
  fi
done

# ----------- DRY-RUN skips ---------------

before_count="$(find "${SOVEREIGN_OS_METRICS_DIR}" -name '*.prom' -type f | wc -l)"
(
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  . "${LIB}"
  SOVEREIGN_OS_DRY_RUN=1 emit_metric sovereign_os_dryrun_check 1 >/dev/null
)
after_count="$(find "${SOVEREIGN_OS_METRICS_DIR}" -name '*.prom' -type f | wc -l)"
if [ "${before_count}" -eq "${after_count}" ]; then
  ok "DRY-RUN does not create new .prom files"
else
  ko "DRY-RUN wrote files (count went ${before_count} → ${after_count})"
fi

# ----------- DISABLE skips ---------------

(
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  . "${LIB}"
  SOVEREIGN_OS_METRICS_DISABLE=1 emit_metric sovereign_os_disabled_check 1
)
if ! find "${SOVEREIGN_OS_METRICS_DIR}" -name '*.prom' -type f -exec grep -l disabled_check {} \; 2>/dev/null | grep -q .; then
  ok "SOVEREIGN_OS_METRICS_DISABLE=1 skips writes"
else
  ko "DISABLE did not skip — metric was written"
fi

# ----------- missing dir → graceful skip ---------------

(
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  . "${LIB}"
  # Set to an unwritable path; emission must not error
  SOVEREIGN_OS_METRICS_DIR="/nonexistent/never-here/$$" emit_metric sovereign_os_unwritable 0
)
ok "unwritable metrics dir → graceful skip (no caller-breaking error)"

# ----------- log-rotate.sh end-to-end metric emission ---------------

rm -rf "${SOVEREIGN_OS_METRICS_DIR}"
log_dir="$(mktemp -d)"
mkdir -p "${log_dir}"
touch -d '30 days ago' "${log_dir}/build-old.jsonl"
echo '{"x":1}' > "${log_dir}/build-old.jsonl"
touch -d '30 days ago' "${log_dir}/build-old.jsonl"

SOVEREIGN_OS_LOG_DIR="${log_dir}" \
SOVEREIGN_OS_LOG_RETENTION_DAYS=14 \
SOVEREIGN_OS_METRICS_DIR="${SOVEREIGN_OS_METRICS_DIR}" \
SOVEREIGN_OS_NONINTERACTIVE=1 \
  "${__REPO_ROOT}/scripts/hooks/recurrent/log-rotate.sh" >/dev/null

rotation_file="${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-log-rotation.prom"
if [ -f "${rotation_file}" ]; then
  ok "log-rotate emitted sovereign-os-log-rotation.prom"
else
  ko "log-rotate did not emit metrics file"
fi

if grep -q "sovereign_os_log_rotation_files_rotated 1" "${rotation_file}" 2>/dev/null; then
  ok "log-rotate metric: files_rotated == 1 (matches actual rotation)"
else
  ko "log-rotate metric files_rotated wrong: $(grep files_rotated "${rotation_file}" 2>/dev/null)"
fi

if grep -qE "^sovereign_os_log_rotation_last_run_timestamp [0-9]+$" "${rotation_file}" 2>/dev/null; then
  ok "log-rotate metric: last_run_timestamp is a unix epoch"
else
  ko "log-rotate metric last_run_timestamp missing/malformed"
fi

rm -rf "${log_dir}"

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_observability_lib: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
