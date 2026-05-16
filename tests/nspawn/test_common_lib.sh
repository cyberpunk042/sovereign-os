#!/usr/bin/env bash
# tests/nspawn/test_common_lib.sh
#
# Substantive tests for scripts/build/lib/common.sh — the shared
# helper library every build script + every hook sources. Currently
# zero direct coverage; gap closed here.
#
# Validates:
#   - source-guard prevents double-load
#   - require_command exits 1 on missing command
#   - require_command returns 0 on present command
#   - require_file / require_dir behave correctly
#   - load_profile sets SOVEREIGN_OS_PROFILE_FILE
#   - profile_field extracts dotted-path values from YAML
#   - profile_field handles missing keys (empty output, exit 0)
#   - confirm respects SOVEREIGN_OS_NONINTERACTIVE
#   - confirm default=yes returns 0 in non-interactive mode
#   - confirm default=no returns non-zero in non-interactive mode

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

# common.sh has strict mode + an ERR trap. We need to handle expected
# failures (require_command miss) without aborting the test. Source
# in a subshell for each isolated assertion.

fail=0
pass=0

ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_common_lib.sh"
echo

# ----------- source-guard ---------------

result="$(
  (
    . "${__REPO_ROOT}/scripts/build/lib/common.sh"
    . "${__REPO_ROOT}/scripts/build/lib/common.sh"
    echo "double-source-ok"
  ) 2>&1
)"
if grep -q "double-source-ok" <<< "${result}"; then
  ok "source-guard prevents double-load (no error on re-source)"
else
  ko "double-source failed: ${result}"
fi

# ----------- require_command exists ---------------

if (
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  require_command bash
) >/dev/null 2>&1; then
  ok "require_command returns 0 for present command (bash)"
else
  ko "require_command bash exited non-zero"
fi

# ----------- require_command missing ---------------

if (
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  require_command nonexistent-command-xyz
) >/dev/null 2>&1; then
  ko "require_command should have exited non-zero for nonexistent-command-xyz"
else
  ok "require_command exits non-zero for missing command"
fi

# ----------- require_file ---------------

tmpfile="$(mktemp)"
if (
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  require_file "${tmpfile}"
) >/dev/null 2>&1; then
  ok "require_file passes on existing file"
else
  ko "require_file failed on existing file"
fi
rm -f "${tmpfile}"

if (
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  require_file "/nonexistent/path/xyz"
) >/dev/null 2>&1; then
  ko "require_file should have failed on missing path"
else
  ok "require_file fails on missing path"
fi

# ----------- require_dir ---------------

tmpdir="$(mktemp -d)"
if (
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  require_dir "${tmpdir}"
) >/dev/null 2>&1; then
  ok "require_dir passes on existing dir"
else
  ko "require_dir failed on existing dir"
fi

if (
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  require_dir "/nonexistent/dir/xyz"
) >/dev/null 2>&1; then
  ko "require_dir should have failed on missing dir"
else
  ok "require_dir fails on missing dir"
fi
rmdir "${tmpdir}"

# ----------- load_profile + profile_field ---------------

result="$(
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  load_profile sain-01
  echo "id=${SOVEREIGN_OS_PROFILE_ID}"
  echo "march=$(profile_field hardware.cpu.march)"
  echo "topology=$(profile_field hardware.cpu.cores.topology)"
  echo "unknown=$(profile_field hardware.nonexistent.field)"
)"

if grep -q "id=sain-01" <<< "${result}"; then
  ok "load_profile sets SOVEREIGN_OS_PROFILE_ID"
else
  ko "load_profile didn't set PROFILE_ID: ${result}"
fi

if grep -q "march=znver5" <<< "${result}"; then
  ok "profile_field reads hardware.cpu.march"
else
  ko "profile_field hardware.cpu.march failed: ${result}"
fi

if grep -q "topology=dual-ccd" <<< "${result}"; then
  ok "profile_field reads nested hardware.cpu.cores.topology"
else
  ko "profile_field nested path failed: ${result}"
fi

if grep -q "unknown=$" <<< "${result}"; then
  ok "profile_field returns empty for missing key (no error)"
else
  ko "profile_field missing key returned: ${result}"
fi

# ----------- confirm in non-interactive mode ---------------

# default-yes → should succeed
if (
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  SOVEREIGN_OS_NONINTERACTIVE=1
  confirm "test" default-yes
) >/dev/null 2>&1; then
  ok "confirm default-yes returns 0 in non-interactive mode"
else
  ko "confirm default-yes failed in non-interactive mode"
fi

# default-no → should fail
if (
  . "${__REPO_ROOT}/scripts/build/lib/common.sh"
  SOVEREIGN_OS_NONINTERACTIVE=1
  confirm "test" default-no
) >/dev/null 2>&1; then
  ko "confirm default-no should have failed in non-interactive mode"
else
  ok "confirm default-no returns non-zero in non-interactive mode"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_common_lib: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
