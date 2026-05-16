#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_metrics.sh
#
# Layer 3 test for the `sovereign-osctl metrics` verb (Round 88).
# Verifies the 4 subverbs against a synthetic textfile-collector dir:
#   - list                show files + counts
#   - show <basename>     prefix/suffix resolution + missing-file error
#   - tail [N]            newest-first, bad N → exit 2
#   - health              malformed lines + stale files → reported

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_sovereign_osctl_metrics.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

mdir="${tmp}/textfile_collector"
mkdir -p "${mdir}"

# Two well-formed .prom files
cat > "${mdir}/sovereign-os-build.prom" <<'EOF'
# HELP sovereign_os_build_step_render_total Render step counter
# TYPE sovereign_os_build_step_render_total counter
sovereign_os_build_step_render_total{profile="sain-01",result="success"} 1
sovereign_os_build_step_render_total{profile="minimal",result="success"} 3
EOF

cat > "${mdir}/sovereign-os-recurrent.prom" <<'EOF'
# TYPE sovereign_os_zfs_pool_health gauge
sovereign_os_zfs_pool_health{pool="tank"} 1
EOF

# One malformed file (line that doesn't match the metric grammar)
cat > "${mdir}/sovereign-os-broken.prom" <<'EOF'
this is not a valid metric line at all
sovereign_os_legit{x="y"} 42
EOF

# One stale file (force mtime 30 days back)
cp "${mdir}/sovereign-os-build.prom" "${mdir}/sovereign-os-stale.prom"
touch -d '30 days ago' "${mdir}/sovereign-os-stale.prom"

export SOVEREIGN_OS_METRICS_DIR="${mdir}"

# ----- list -----
set +e
out="$("${OSCTL}" metrics list 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "sovereign-os-build.prom" <<< "${out}" && grep -q "sovereign-os-recurrent.prom" <<< "${out}"; then
  ok "list shows every .prom file"
else
  ko "list missing expected files (rc=${rc})"
fi
if grep -q "FILE.*LAST UPDATE.*METRICS" <<< "${out}"; then
  ok "list emits header row"
else
  ko "list header missing"
fi

# ----- list against empty dir -----
empty_dir="${tmp}/empty"; mkdir -p "${empty_dir}"
set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${empty_dir}" "${OSCTL}" metrics list 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "no sovereign-os-\*.prom files" <<< "${out}"; then
  ok "list on empty dir → exit 0 + clear message"
else
  ko "list on empty dir gate broken (rc=${rc})"
fi

# ----- list against absent dir -----
set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${tmp}/never-existed-$$" "${OSCTL}" metrics list 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "metrics dir absent" <<< "${out}"; then
  ok "list on absent dir → exit 0 + 'metrics dir absent'"
else
  ko "list on absent dir broken (rc=${rc})"
fi

# ----- show: exact basename -----
set +e
out="$("${OSCTL}" metrics show sovereign-os-build.prom 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "sovereign_os_build_step_render_total" <<< "${out}"; then
  ok "show resolves exact filename"
else
  ko "show exact resolution broken (rc=${rc})"
fi

# ----- show: short name (sovereign-os- and .prom both inferred) -----
set +e
out="$("${OSCTL}" metrics show build 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "sovereign_os_build_step_render_total" <<< "${out}"; then
  ok "show resolves bare 'build' → sovereign-os-build.prom"
else
  ko "show short-name resolution broken (rc=${rc})"
fi

# ----- show: missing file -----
set +e
out="$("${OSCTL}" metrics show no-such-thing 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "no .prom file matches" <<< "${out}"; then
  ok "show missing → exit 1 + 'no .prom file matches'"
else
  ko "show missing-file gate broken (rc=${rc})"
fi

# ----- show: no arg -----
set +e
out="$("${OSCTL}" metrics show 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "usage:" <<< "${out}"; then
  ok "show without arg → exit 2 + usage"
else
  ko "show no-arg gate broken (rc=${rc})"
fi

# ----- tail (default N=5) -----
set +e
out="$("${OSCTL}" metrics tail 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "===== sovereign-os-" <<< "${out}"; then
  ok "tail default emits per-file separators"
else
  ko "tail default broken (rc=${rc})"
fi

# ----- tail N=2 (newest two) -----
set +e
out="$("${OSCTL}" metrics tail 2 2>&1)"
rc=$?
set -e
sep_count="$(grep -c '^===== ' <<< "${out}" || true)"
if [ "${rc}" -eq 0 ] && [ "${sep_count}" -eq 2 ]; then
  ok "tail N=2 emits exactly 2 file blocks"
else
  ko "tail N=2 broken (rc=${rc}, sep_count=${sep_count})"
fi

# ----- tail bad N -----
set +e
out="$("${OSCTL}" metrics tail not-a-number 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "tail count must be a non-negative integer" <<< "${out}"; then
  ok "tail bad-N → exit 2"
else
  ko "tail bad-N gate broken (rc=${rc})"
fi

# ----- health: with malformed + stale files -----
set +e
out="$("${OSCTL}" metrics health 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ]; then
  ok "health on mixed dir → exit 1 (issues found)"
else
  ko "health did not flag issues (rc=${rc})"
fi
if grep -q "STALE.*sovereign-os-stale.prom" <<< "${out}"; then
  ok "health flags 30-day-old file as STALE"
else
  ko "health stale detection broken"
fi
if grep -q "MALFORMED.*sovereign-os-broken.prom" <<< "${out}"; then
  ok "health flags malformed file"
else
  ko "health malformed detection broken"
fi

# ----- health: clean dir -----
clean_dir="${tmp}/clean"; mkdir -p "${clean_dir}"
cat > "${clean_dir}/sovereign-os-clean.prom" <<'EOF'
sovereign_os_test_metric{x="y"} 1
EOF
set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${clean_dir}" "${OSCTL}" metrics health 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "all files fresh + well-formed" <<< "${out}"; then
  ok "health on clean dir → exit 0 + summary line"
else
  ko "health clean-dir broken (rc=${rc})"
fi

# ----- unknown subverb -----
set +e
out="$("${OSCTL}" metrics bogus 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown metrics subcommand: bogus" <<< "${out}"; then
  ok "unknown subverb → exit 2 + clear error"
else
  ko "unknown-subverb gate broken (rc=${rc})"
fi

# ----- help includes metrics rows -----
set +e
help_out="$("${OSCTL}" help 2>&1)"
set -e
for kw in "metrics list" "metrics show" "metrics tail" "metrics health"; do
  if grep -q "${kw}" <<< "${help_out}"; then
    ok "help documents: ${kw}"
  else
    ko "help missing: ${kw}"
  fi
done

# ----- result -----
echo
total=$((pass + fail))
echo "test_sovereign_osctl_metrics: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
