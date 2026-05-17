#!/usr/bin/env bash
# R333 (E2.M24) — config restore companion to R332 L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/diagnostics/config-restore.py"
SNAP_SCRIPT="${REPO_ROOT}/scripts/diagnostics/config-snapshot.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# Helper: build a snapshot from a fresh overlay dir + return paths.
make_snapshot() {
    local src_dir
    src_dir=$(mktemp -d)
    cat > "${src_dir}/sample-a.toml" <<'TOML'
key1 = 42
key2 = "hello"
TOML
    cat > "${src_dir}/sample-b.toml" <<'TOML'
flag = false
TOML
    local snap
    snap=$(mktemp --suffix=.json)
    python3 "${SNAP_SCRIPT}" capture --overlay-dir "${src_dir}" --json > "${snap}"
    echo "${src_dir}|${snap}"
}

# ── 1. verify --json envelope ──────────────────────────────
parts=$(make_snapshot); src_dir="${parts%|*}"; snap="${parts##*|}"
tgt_dir=$(mktemp -d)
out="$(python3 "${SCRIPT}" verify --snapshot "${snap}" --target-dir "${tgt_dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R333'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M24'
for k in ('snapshot_path', 'snapshot_captured_at', 'snapshot_host',
          'target_dir', 'overlay_count', 'verified', 'any_sha256_mismatch'):
    assert k in d, k
" || fail "envelope"
rm -rf "${src_dir}" "${tgt_dir}" "${snap}"
pass "1. verify --json envelope (round/sdd_vector/verified/...)"

# ── 2. sha256 round-trips on each overlay ─────────────────
parts=$(make_snapshot); src_dir="${parts%|*}"; snap="${parts##*|}"
tgt_dir=$(mktemp -d)
out="$(python3 "${SCRIPT}" verify --snapshot "${snap}" --target-dir "${tgt_dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['any_sha256_mismatch'] is False
for v in d['verified']:
    assert v['sha256_match'] is True
    assert v['snapshot_sha256'] == v['decoded_sha256']
" || fail "sha256"
rm -rf "${src_dir}" "${tgt_dir}" "${snap}"
pass "2. sha256 round-trips on each overlay"

# ── 3. diff_vs_current reports new-file for empty target ──
parts=$(make_snapshot); src_dir="${parts%|*}"; snap="${parts##*|}"
tgt_dir=$(mktemp -d)
out="$(python3 "${SCRIPT}" verify --snapshot "${snap}" --target-dir "${tgt_dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for v in d['verified']:
    assert v['diff_vs_current'] == 'new-file', v
" || fail "new-file"
rm -rf "${src_dir}" "${tgt_dir}" "${snap}"
pass "3. diff_vs_current=new-file for empty target dir"

# ── 4. diff_vs_current reports identical when same content ──
parts=$(make_snapshot); src_dir="${parts%|*}"; snap="${parts##*|}"
# Target == source: identical content
out="$(python3 "${SCRIPT}" verify --snapshot "${snap}" --target-dir "${src_dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for v in d['verified']:
    assert v['diff_vs_current'] == 'identical', v
" || fail "identical"
rm -rf "${src_dir}" "${snap}"
pass "4. diff_vs_current=identical when target has same content"

# ── 5. apply without gates → dry-run (no writes) ────────
parts=$(make_snapshot); src_dir="${parts%|*}"; snap="${parts##*|}"
tgt_dir=$(mktemp -d)
state=$(mktemp -u)
SOVEREIGN_OS_APPLY_AUDIT_PATH="${state}" \
python3 "${SCRIPT}" apply --snapshot "${snap}" --target-dir "${tgt_dir}" --json >/dev/null 2>&1 || true
# tgt_dir should still be empty.
[[ -z "$(ls -A "${tgt_dir}")" ]] || fail "dry-run must not write to target_dir"
rm -rf "${src_dir}" "${tgt_dir}" "${snap}" "${state}"
pass "5. apply without gates → dry-run + no files written to target"

# ── 6. apply with all 3 gates writes files + matches sha256 ──
parts=$(make_snapshot); src_dir="${parts%|*}"; snap="${parts##*|}"
tgt_dir=$(mktemp -d)
state=$(mktemp -u)
RC=0
SOVEREIGN_OS_APPLY_AUDIT_PATH="${state}" \
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
python3 "${SCRIPT}" apply --snapshot "${snap}" --target-dir "${tgt_dir}" \
    --apply --confirm-restore --json >/dev/null 2>&1 || RC=$?
[[ "${RC}" == "0" ]] || fail "expected rc=0; got ${RC}"
# tgt_dir must now have the overlays.
[[ -f "${tgt_dir}/sample-a.toml" ]] || fail "sample-a.toml not restored"
[[ -f "${tgt_dir}/sample-b.toml" ]] || fail "sample-b.toml not restored"
# Verify the restored files match the source bytes.
diff -q "${src_dir}/sample-a.toml" "${tgt_dir}/sample-a.toml" >/dev/null \
    || fail "restored sample-a.toml differs from source"
diff -q "${src_dir}/sample-b.toml" "${tgt_dir}/sample-b.toml" >/dev/null \
    || fail "restored sample-b.toml differs from source"
rm -rf "${src_dir}" "${tgt_dir}" "${snap}" "${state}"
pass "6. apply with all 3 gates writes files matching source bytes"

# ── 7. apply writes to R327 audit log ─────────────────────
parts=$(make_snapshot); src_dir="${parts%|*}"; snap="${parts##*|}"
tgt_dir=$(mktemp -d)
state=$(mktemp -u)
SOVEREIGN_OS_APPLY_AUDIT_PATH="${state}" \
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
python3 "${SCRIPT}" apply --snapshot "${snap}" --target-dir "${tgt_dir}" \
    --apply --confirm-restore --json >/dev/null 2>&1 || true
[[ -f "${state}" ]] || fail "audit log must exist after apply"
grep -q '"verb": "config-restore apply"' "${state}" \
    || fail "audit log missing verb=config-restore apply"
grep -q '"round_origin": "R333"' "${state}" \
    || fail "audit log missing round_origin=R333"
rm -rf "${src_dir}" "${tgt_dir}" "${snap}" "${state}"
pass "7. apply records to R327 audit log (verb + round_origin)"

# ── 8. Idempotent: re-apply when target identical → no rewrite ──
parts=$(make_snapshot); src_dir="${parts%|*}"; snap="${parts##*|}"
tgt_dir=$(mktemp -d)
state=$(mktemp -u)
# First apply: writes.
SOVEREIGN_OS_APPLY_AUDIT_PATH="${state}" SOVEREIGN_OS_CONFIRM_DESTROY=YES \
python3 "${SCRIPT}" apply --snapshot "${snap}" --target-dir "${tgt_dir}" \
    --apply --confirm-restore --json >/dev/null
# Capture mtime of one overlay.
mtime_before=$(stat -c %Y "${tgt_dir}/sample-a.toml")
sleep 1
# Second apply: should report identical + not rewrite.
out2="$(SOVEREIGN_OS_APPLY_AUDIT_PATH=${state} SOVEREIGN_OS_CONFIRM_DESTROY=YES \
    python3 "${SCRIPT}" apply --snapshot "${snap}" --target-dir "${tgt_dir}" \
    --apply --confirm-restore --json)"
echo "${out2}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# All overlays should be 'identical' → no write
for r in d['results']:
    assert r['wrote'] is False
    assert 'identical' in r['reason']
" || fail "idempotent shape"
mtime_after=$(stat -c %Y "${tgt_dir}/sample-a.toml")
[[ "${mtime_before}" == "${mtime_after}" ]] || fail "mtime changed; expected no rewrite"
rm -rf "${src_dir}" "${tgt_dir}" "${snap}" "${state}"
pass "8. idempotent re-apply: identical-content overlays not rewritten"

# ── 9. Tampered snapshot → sha256 mismatch caught ─────────
parts=$(make_snapshot); src_dir="${parts%|*}"; snap="${parts##*|}"
# Tamper: change one byte in body_b64 of first overlay.
python3 -c "
import json
d = json.loads(open('${snap}').read())
# Re-base64-encode tampered bytes: prepend a single byte.
import base64
o = d['overlays'][0]
tampered = b'X' + base64.b64decode(o['body_b64'])
o['body_b64'] = base64.b64encode(tampered).decode()
# Leave sha256 unchanged (the original) → mismatch
with open('${snap}', 'w') as f:
    f.write(json.dumps(d))
"
tgt_dir=$(mktemp -d)
RC=0
out="$(python3 "${SCRIPT}" verify --snapshot "${snap}" --target-dir "${tgt_dir}" --json)" || RC=$?
[[ "${RC}" == "1" ]] || fail "expected rc=1 for sha256 mismatch; got ${RC}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['any_sha256_mismatch'] is True
# At least one overlay should have sha256_match=False.
assert any(not v['sha256_match'] for v in d['verified'])
" || fail "mismatch detection"
rm -rf "${src_dir}" "${tgt_dir}" "${snap}"
pass "9. tampered snapshot → sha256 mismatch detected (rc=1)"

# ── 10. sovereign-osctl config-restore dispatch ───────────
parts=$(make_snapshot); src_dir="${parts%|*}"; snap="${parts##*|}"
tgt_dir=$(mktemp -d)
out_disp="$(bash "${OSCTL}" config-restore verify --snapshot "${snap}" --target-dir "${tgt_dir}" --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R333'
" || fail "osctl dispatch"
rm -rf "${src_dir}" "${tgt_dir}" "${snap}"
pass "10. sovereign-osctl config-restore dispatches"

echo "ALL OK"
