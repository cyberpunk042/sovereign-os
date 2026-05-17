#!/usr/bin/env bash
# tests/nspawn/test_operator_deps.sh — R284 (E7.M6).
# Operator-supplied dep install hooks (apt / pip / npm / curl-shell).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/install/operator-deps.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
EXAMPLE="${__REPO_ROOT}/config/operator-deps.toml.example"

echo "tests/nspawn/test_operator_deps.sh"
echo

[ -x "${SCRIPT}" ] && ok "operator-deps.py executable" \
  || { ko "missing"; exit 1; }
[ -f "${EXAMPLE}" ] && ok "config example shipped" || ko "example missing"
grep -q "R284\|E7.M6" "${SCRIPT}" && ok "script cites R284/E7.M6" \
  || ko "R284 missing"
grep -q "operator_overlay" "${SCRIPT}" \
  && ok "script consumes the R283 operator-overlay helper" \
  || ko "overlay adoption missing"
grep -q "^  operator-deps)" "${OSCTL}" \
  && ok "osctl bridges 'operator-deps'" || ko "osctl dispatch missing"

# ---- list --json: shape ----
set +e
out="$(python3 "${SCRIPT}" list --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "list rc=0" || ko "list rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R284', d
for k in ('config_source','package_managers_available','declared','overlay_keys'):
    assert k in d, k
# Declared shape
for pm in ('apt','pip','npm','curl_shell'):
    assert pm in d['declared'], pm
" \
  && ok "list --json: config_source + pms + declared shape" \
  || ko "list shape wrong"

# ---- plan --json: per-step shape + counts ----
out="$(python3 "${SCRIPT}" plan --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R284', d
for k in ('counts','steps'):
    assert k in d, k
for c in ('total','already_installed','would_install','curl_shell_count'):
    assert c in d['counts'], c
for s in d['steps']:
    for f in ('kind','name','command','currently_installed'):
        assert f in s, f
    assert s['kind'] in ('apt','pip','npm','curl-shell'), s
" \
  && ok "plan --json: counts + per-step shape" \
  || ko "plan shape wrong"

# ---- apply without --confirm → rc=2 ----
set +e
python3 "${SCRIPT}" apply > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "apply without --confirm → rc=2" \
  || ko "expected rc=2, got ${rc}"

# ---- apply --dry-run --confirm: results=dry-run, no host change ----
out="$(python3 "${SCRIPT}" apply --dry-run --confirm --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R284', d
assert d['dry_run'] is True, d
assert d['failure_count'] == 0, d
# Every step either ran dry OR was already-installed.
for r in d['results']:
    assert r['outcome'] in ('dry-run','already-installed'), r
" \
  && ok "apply --dry-run: every step dry-run or already-installed" \
  || ko "dry-run shape wrong"

# ---- SOVEREIGN_OS_CONFIRM_DESTROY=YES alt-gate accepts ----
set +e
out="$(SOVEREIGN_OS_CONFIRM_DESTROY=YES python3 "${SCRIPT}" apply --dry-run --json)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "SOVEREIGN_OS_CONFIRM_DESTROY=YES alt-gate accepts" \
  || ko "alt-gate rc=${rc}"

# ---- curl-shell entry without --confirm-curl-shell → skipped ----
TMP="$(mktemp -d -t r284.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
cat > "${TMP}/with-curl.toml" <<'TOML'
[apt]
install = []
[pip]
install = []
[npm]
global = []
[curl_shell]
installs = [
  { name = "ghost-tool", url = "https://example.invalid/install.sh", verify = "skip" },
]
TOML
# Mark as "currently_installed = False" — ghost-tool will not be on PATH.
set +e
out="$(SOVEREIGN_OS_OVERLAY_OPERATOR_DEPS="${TMP}/with-curl.toml" \
  python3 "${SCRIPT}" apply --confirm --dry-run --json 2>/dev/null)"
set -e
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
# Dry-run: outcome is 'dry-run' (curl-shell only skipped on REAL apply).
ghost = next(r for r in d['results'] if r['kind'] == 'curl-shell')
assert ghost['outcome'] == 'dry-run', ghost
" \
  && ok "curl-shell --dry-run: outcome=dry-run" \
  || ko "curl-shell dry-run shape wrong"

# Now real apply WITHOUT --confirm-curl-shell → curl-shell step skipped.
set +e
out="$(SOVEREIGN_OS_OVERLAY_OPERATOR_DEPS="${TMP}/with-curl.toml" \
  SOVEREIGN_OS_CONFIRM_DESTROY=YES \
  python3 "${SCRIPT}" apply --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "curl-shell without --confirm-curl-shell: rc=0 (skipped, not failed)" \
  || ko "rc unexpected ${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
ghost = next(r for r in d['results'] if r['kind'] == 'curl-shell')
assert ghost['outcome'] == 'skipped', ghost
assert '--confirm-curl-shell' in ghost['detail'], ghost
" \
  && ok "curl-shell without --confirm-curl-shell: skipped + reason cites the flag" \
  || ko "curl-shell skip-reason missing"

# ---- overlay adoption verifiable ----
out="$(python3 "${SCRIPT}" list --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
# Even with the default example, config_source must be non-empty
assert d['config_source'], d
# overlay_keys is a list (empty when defaults-only)
assert isinstance(d['overlay_keys'], list), d
" \
  && ok "overlay metadata surfaces (config_source + overlay_keys)" \
  || ko "overlay metadata missing"

# ---- human render: banner + sections ----
out_h="$(python3 "${SCRIPT}" plan 2>&1 || true)"
echo "${out_h}" | grep -q "R284 operator-deps plan" \
  && ok "plan human banner present" || ko "banner missing"

# ---- osctl bridge ----
set +e
"${OSCTL}" operator-deps list --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl operator-deps list rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R284', d
" \
  && ok "osctl bridge surfaces R284 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" operator-deps nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown operator-deps subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_operator_deps: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
