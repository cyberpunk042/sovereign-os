#!/usr/bin/env bash
# tests/nspawn/test_weaver_atomic_state.sh
#
# Layer 3 test for R154 — scripts/weaver/atomic-state.py
# (master spec § 21 Atomic State Transition Protocol).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/weaver/atomic-state.py"

echo "tests/nspawn/test_weaver_atomic_state.sh"
echo

if [ -f "${SCRIPT}" ]; then
  ok "atomic-state.py present"
else
  ko "missing"; exit 1
fi

# ---------- syntactic sanity ----------
if python3 -c "import ast; ast.parse(open('${SCRIPT}').read())" 2>/dev/null; then
  ok "python3 parses the file"
else
  ko "python3 parse error"
fi

# ---------- master spec citation ----------
if grep -q "master spec § 21" "${SCRIPT}"; then
  ok "script cites master spec § 21"
else
  ko "master spec § 21 citation missing"
fi

# State-fabric files (master spec § 7.1)
for name in IDENTITY.md SOUL.md AGENTS.md CLAUDE.md; do
  if grep -q "${name}" "${SCRIPT}"; then
    ok "STATE_FILES includes ${name}"
  else
    ko "STATE_FILES missing ${name}"
  fi
done

# Master spec § 21.1 keywords
for kw in O_DIRECT O_SYNC O_TRUNC os.rename "atomic" "4K" "BLOCK = 4096"; do
  if grep -q "${kw}" "${SCRIPT}"; then
    ok "script mentions ${kw}"
  else
    ko "script missing ${kw}"
  fi
done

# ---------- DRY-RUN ----------
TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "${TMPDIR_TEST}"' EXIT

set +e
out="$(WEAVER_CONTEXT_DIR="${TMPDIR_TEST}" WEAVER_DRY_RUN=1 \
       python3 "${SCRIPT}" write IDENTITY.md --from-stdin <<< "dry-run payload" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "DRY-RUN" <<< "${out}"; then
  ok "DRY-RUN exit 0 + surfaces DRY-RUN intent"
else
  ko "DRY-RUN broken (rc=${rc} out=${out:0:200})"
fi
if grep -q "O_DIRECT" <<< "${out}" && grep -q "atomic rename" <<< "${out}"; then
  ok "DRY-RUN surfaces O_DIRECT + atomic rename intent"
else
  ko "DRY-RUN intent message missing"
fi
# DRY-RUN must NOT actually write the file
if [ ! -f "${TMPDIR_TEST}/IDENTITY.md" ]; then
  ok "DRY-RUN did not produce a real file"
else
  ko "DRY-RUN produced an unexpected file"
fi

# ---------- write → read roundtrip ----------
set +e
out="$(WEAVER_CONTEXT_DIR="${TMPDIR_TEST}" \
       python3 "${SCRIPT}" write IDENTITY.md --from-stdin <<< "# IDENTITY content" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && [ -f "${TMPDIR_TEST}/IDENTITY.md" ]; then
  ok "write committed IDENTITY.md"
else
  ko "write failed (rc=${rc} out=${out:0:200})"
fi

# 4K-aligned file size (master spec § 21.1 NVMe physical block alignment)
fsize="$(stat -c '%s' "${TMPDIR_TEST}/IDENTITY.md")"
if [ "$((fsize % 4096))" -eq 0 ]; then
  ok "committed file is 4K-aligned (${fsize} bytes)"
else
  ko "file NOT 4K-aligned: ${fsize}"
fi

# Read strips trailing padding
back="$(WEAVER_CONTEXT_DIR="${TMPDIR_TEST}" python3 "${SCRIPT}" read IDENTITY.md)"
if [ "${back}" = "# IDENTITY content" ]; then
  ok "read strips trailing padding (roundtrip preserves content)"
else
  ko "roundtrip lost content: '${back}'"
fi

# ---------- write all 4 state-fabric files ----------
allok=1
for f in IDENTITY.md SOUL.md AGENTS.md CLAUDE.md; do
  if ! WEAVER_CONTEXT_DIR="${TMPDIR_TEST}" \
       python3 "${SCRIPT}" write "${f}" --from-stdin <<< "# ${f} content" >/dev/null 2>&1; then
    allok=0
  fi
done
if [ "${allok}" -eq 1 ]; then
  ok "all 4 state-fabric files write atomically"
else
  ko "at least one state-fabric file write failed"
fi

# ---------- list ----------
out="$(WEAVER_CONTEXT_DIR="${TMPDIR_TEST}" python3 "${SCRIPT}" list 2>&1)"
for f in IDENTITY.md SOUL.md AGENTS.md CLAUDE.md; do
  if grep -q "${f}" <<< "${out}"; then
    ok "list surfaces ${f}"
  else
    ko "list missing ${f}"
  fi
done

# ---------- write rejects unknown state file ----------
set +e
out="$(WEAVER_CONTEXT_DIR="${TMPDIR_TEST}" \
       python3 "${SCRIPT}" write NOPE.md --from-stdin <<< "x" 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ]; then
  ok "write rejects unknown state file"
else
  ko "unknown file accepted (rc=${rc})"
fi

# ---------- write from --from-file ----------
src="$(mktemp)"
echo "# payload from file" > "${src}"
set +e
WEAVER_CONTEXT_DIR="${TMPDIR_TEST}" \
  python3 "${SCRIPT}" write SOUL.md --from-file "${src}" >/dev/null 2>&1
rc=$?
set -e
rm -f "${src}"
back="$(WEAVER_CONTEXT_DIR="${TMPDIR_TEST}" python3 "${SCRIPT}" read SOUL.md)"
if [ "${rc}" -eq 0 ] && [ "${back}" = "# payload from file" ]; then
  ok "--from-file path works (write→read roundtrip)"
else
  ko "--from-file broken (rc=${rc} back='${back}')"
fi

# ---------- read missing returns empty (no crash) ----------
TMP2="$(mktemp -d)"
back="$(WEAVER_CONTEXT_DIR="${TMP2}" python3 "${SCRIPT}" read CLAUDE.md 2>&1 || true)"
if [ -z "${back}" ]; then
  ok "read of absent file returns empty (no crash)"
else
  ko "read of absent file returned: '${back}'"
fi
rm -rf "${TMP2}"

echo
total=$((pass + fail))
echo "test_weaver_atomic_state: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
