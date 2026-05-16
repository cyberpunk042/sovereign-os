#!/usr/bin/env bash
# tests/nspawn/test_perimeter_check_overlap.sh
#
# Layer 3 test for R165 — scripts/perimeter/check-overlap.py +
# sovereign-osctl perimeter check-overlap (selfdef SDD-015 mirror).
#
# Validates the mirror of selfdef's perimeter coexistence check on
# the sovereign-os side: detects duplicate metadata.name + non-
# sovereign-os policies asserting host-scoped on fenced syscalls.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/perimeter/check-overlap.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_perimeter_check_overlap.sh"
echo

[ -x "${SCRIPT}" ] && ok "check-overlap.py executable" || { ko "missing"; exit 1; }
[ -x "${OSCTL}" ] && ok "sovereign-osctl executable" || ko "osctl missing"

# Script cites selfdef SDD-015 (cross-repo provenance)
grep -q "SDD-015" "${SCRIPT}" && ok "script cites selfdef SDD-015 (cross-repo mirror)" \
  || ko "SDD-015 citation missing"

# python3 + yaml available
python3 -c "import yaml" 2>/dev/null && ok "python3-yaml importable" \
  || ko "python3-yaml not installed"

# ---------- empty dir → PASS, rc=0 ----------
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
set +e
out="$(python3 "${SCRIPT}" --policies-dir "${TMP}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && grep -q "PASS" <<< "${out}" \
  && ok "empty policies dir → rc=0 + PASS" \
  || ko "empty dir broken (rc=${rc})"

# ---------- non-existent dir → PASS, rc=0 (operator without Tetragon) ----------
set +e
out="$(python3 "${SCRIPT}" --policies-dir /no/such/path 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "non-existent dir → rc=0 (graceful)" \
  || ko "missing-dir path broken (rc=${rc})"

# ---------- sovereign-kernel-fence alone → PASS ----------
cat > "${TMP}/sovereign-kernel-fence.yaml" <<'EOF'
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: sovereign-kernel-fence
spec:
  kprobes:
    - call: sys_execve
EOF
set +e
out="$(python3 "${SCRIPT}" --policies-dir "${TMP}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "sovereign-kernel-fence alone → rc=0 (host-scoped is OK from sovereign-os itself)" \
  || ko "sovereign-policy-alone path broken"

# ---------- agent-guard host-scoped sys_execve → FAIL ----------
cat > "${TMP}/agent-guard-bad.yaml" <<'EOF'
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: agent-guard-bad
spec:
  kprobes:
    - call: sys_execve
EOF
set +e
out="$(python3 "${SCRIPT}" --policies-dir "${TMP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "agent-guard-bad" <<< "${out}" \
  && grep -q "matchNamespaces=container" <<< "${out}"; then
  ok "agent-guard host-scoped sys_execve → rc=1 + actionable fix message"
else
  ko "agent-guard-bad path: rc=${rc} out=${out:0:200}"
fi

# ---------- container-scoped agent-guard → no FAIL (allowed) ----------
rm -f "${TMP}/agent-guard-bad.yaml"
cat > "${TMP}/agent-guard-shell-exec.yaml" <<'EOF'
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: agent-guard-shell-exec
spec:
  kprobes:
    - call: sys_execve
      selectors:
        - matchNamespaces:
            - operator: In
              values: [container]
EOF
set +e
out="$(python3 "${SCRIPT}" --policies-dir "${TMP}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && grep -q "PASS" <<< "${out}" \
  && ok "container-scoped agent-guard with sys_execve → rc=0 (boundary respected)" \
  || ko "container-scoped path broken: rc=${rc}"

# ---------- duplicate metadata.name → FAIL ----------
cat > "${TMP}/agent-guard-dup-a.yaml" <<'EOF'
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: agent-guard-etc-write
spec:
  kprobes:
    - call: sys_openat
      selectors:
        - matchNamespaces:
            - operator: In
              values: [container]
EOF
cp "${TMP}/agent-guard-dup-a.yaml" "${TMP}/agent-guard-dup-b.yaml"
set +e
out="$(python3 "${SCRIPT}" --policies-dir "${TMP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "duplicate metadata.name" <<< "${out}"; then
  ok "duplicate metadata.name → rc=1 + clear finding"
else
  ko "duplicate-name path broken (rc=${rc})"
fi

# Cleanup dup state for next phase
rm -f "${TMP}/agent-guard-dup-a.yaml" "${TMP}/agent-guard-dup-b.yaml"

# ---------- --warn-only downgrades exit ----------
cat > "${TMP}/agent-guard-bad-2.yaml" <<'EOF'
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: agent-guard-bad-2
spec:
  kprobes:
    - call: sys_execve
EOF
set +e
out="$(python3 "${SCRIPT}" --policies-dir "${TMP}" --warn-only 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && grep -q "FAIL" <<< "${out}" \
  && ok "--warn-only: emits FAIL line but rc=0" \
  || ko "warn-only path: rc=${rc}"

# ---------- --json output ----------
set +e
out="$(python3 "${SCRIPT}" --policies-dir "${TMP}" --json 2>&1)"
set -e
if python3 -c "import json; d=json.loads('''${out}'''); assert 'findings' in d; assert 'policies' in d; assert 'pass' in d" 2>/dev/null; then
  ok "--json output parseable + has expected keys"
else
  ko "--json output broken"
fi

# ---------- third-party policy host-scoped on fenced syscall → FAIL ----------
rm -f "${TMP}/agent-guard-bad-2.yaml" "${TMP}/agent-guard-shell-exec.yaml"
cat > "${TMP}/random-third-party.yaml" <<'EOF'
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: random-third-party
spec:
  kprobes:
    - call: sys_execve
EOF
set +e
out="$(python3 "${SCRIPT}" --policies-dir "${TMP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "third-party" <<< "${out}"; then
  ok "third-party host-scoped sys_execve → rc=1 (author=third-party flagged)"
else
  ko "third-party path: rc=${rc}"
fi

# ---------- bad YAML skipped, real findings still reported ----------
rm -f "${TMP}/random-third-party.yaml" "${TMP}/sovereign-kernel-fence.yaml"
echo "this is: not: valid: [[" > "${TMP}/bad.yaml"
cat > "${TMP}/agent-guard-good.yaml" <<'EOF'
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: agent-guard-good
spec:
  kprobes:
    - call: sys_openat
      selectors:
        - matchNamespaces:
            - operator: In
              values: [container]
EOF
set +e
out="$(python3 "${SCRIPT}" --policies-dir "${TMP}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && grep -q "PASS" <<< "${out}" \
  && ok "bad YAML skipped (logged to stderr); good policy still passes" \
  || ko "bad-yaml + good-policy path: rc=${rc}"

# ---------- sovereign-osctl perimeter check-overlap dispatches ----------
set +e
out="$("${OSCTL}" perimeter check-overlap --policies-dir "${TMP}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && grep -q "PASS" <<< "${out}" \
  && ok "sovereign-osctl perimeter check-overlap dispatches the script" \
  || ko "osctl perimeter check-overlap broken: rc=${rc}"

echo
total=$((pass + fail))
echo "test_perimeter_check_overlap: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
