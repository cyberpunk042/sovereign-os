#!/usr/bin/env bash
# tests/nspawn/test_kernel_tuning.sh — R239 (SDD-026 Z-14).
# Per-workload kernel sysctl + cmdline tuning presets.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/kernel/tuning.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
EXAMPLE="${__REPO_ROOT}/config/kernel-tuning.toml.example"

echo "tests/nspawn/test_kernel_tuning.sh"
echo

[ -x "${SCRIPT}" ] && ok "tuning.py executable" \
  || { ko "missing tuning.py"; exit 1; }
[ -f "${EXAMPLE}" ] && ok "kernel-tuning.toml.example shipped" \
  || ko "example config missing"
grep -q "R239" "${SCRIPT}" && ok "tuning.py cites R239" || ko "R239 ref missing"
grep -q "^  kernel)" "${OSCTL}" \
  && ok "osctl bridges 'kernel'" || ko "osctl dispatch missing"
grep -q "kernel apply" "${OSCTL}" \
  && ok "osctl help documents 'kernel apply'" || ko "osctl help missing"

TMP="$(mktemp -d -t r239.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
cat > "${TMP}/cfg.toml" <<'TOML'
[presets.test-defaults]
summary = "test defaults"
[presets.test-defaults.sysctl]
"vm.swappiness" = 30
"net.core.somaxconn" = 4096

[presets.test-burst]
summary = "test burst — many keys + cmdline hints"
[presets.test-burst.sysctl]
"vm.swappiness" = 1
"vm.dirty_ratio" = 5
[presets.test-burst.cmdline_hints]
description = "test cmdline:"
hints = ["transparent_hugepage=madvise", "isolcpus=2-5"]
TOML
export SOVEREIGN_OS_KERNEL_TUNING="${TMP}/cfg.toml"

# ---- list --json: 2 presets ----
set +e
out="$(python3 "${SCRIPT}" list --json 2>/dev/null)"
set -e
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R239', d
names=sorted(p['preset'] for p in d['presets'])
assert names==['test-burst','test-defaults'], names
" \
  && ok "list --json enumerates 2 test presets" \
  || ko "list shape wrong: ${out:0:200}"

# ---- show --preset test-burst: per-key diff with state ----
set +e
out="$(python3 "${SCRIPT}" show --preset test-burst --json 2>/dev/null)"
set -e
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R239', d
p=d['presets']['test-burst']
keys=sorted(r['key'] for r in p['diff'])
assert keys==['vm.dirty_ratio','vm.swappiness'], keys
c=p['counts']
assert c['total']==2, c
# match+diverges+unreadable should sum to total
assert c['match']+c['diverges']+c['unreadable']==c['total'], c
" \
  && ok "show --preset emits per-key diff + counts" \
  || ko "show shape wrong"

# ---- show --preset unknown → rc=2 ----
set +e
python3 "${SCRIPT}" show --preset nope > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "show --preset unknown → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- apply --dry-run: every key reports outcome=dry-run, no writes ----
set +e
out="$(python3 "${SCRIPT}" apply test-burst --dry-run --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "apply --dry-run rc=0" || ko "dry-run rc=${rc}"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['dry_run'] is True, d
assert d['preset']=='test-burst', d
assert all(r['outcome']=='dry-run' for r in d['results']), d
assert d['applied_count']==0, d
assert d['failed_count']==0, d
" \
  && ok "apply --dry-run records dry-run outcomes only" \
  || ko "dry-run shape wrong"

# ---- apply (no --dry-run) without root → rc=2 with actionable cmds ----
if [ "$(id -u)" -ne 0 ]; then
  set +e
  out_apply="$(python3 "${SCRIPT}" apply test-burst 2>&1)"
  rc_apply=$?
  set -e
  [ "${rc_apply}" -eq 2 ] && ok "apply without root → rc=2" \
    || ko "expected rc=2, got ${rc_apply}"
  echo "${out_apply}" | grep -q "sudo sysctl -w vm.swappiness=1" \
    && ok "apply emits actionable shell cmds" || ko "no actionable cmds"
fi

# ---- apply unknown preset → rc=2 ----
set +e
python3 "${SCRIPT}" apply ghost > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "apply unknown preset → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- cmdline-hints test-burst: lists hints + one-liner ----
set +e
out="$(python3 "${SCRIPT}" cmdline-hints test-burst --json 2>/dev/null)"
set -e
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R239', d
assert d['preset']=='test-burst', d
assert d['hints']==['transparent_hugepage=madvise','isolcpus=2-5'], d
" \
  && ok "cmdline-hints --json carries declared hints" \
  || ko "cmdline-hints shape wrong"

# ---- cmdline-hints human render has one-liner ----
out_h="$(python3 "${SCRIPT}" cmdline-hints test-burst)"
echo "${out_h}" | grep -q "transparent_hugepage=madvise isolcpus=2-5" \
  && ok "cmdline-hints human render includes one-liner" \
  || ko "one-liner missing"

# ---- cmdline-hints unknown preset → rc=2 ----
set +e
python3 "${SCRIPT}" cmdline-hints nope > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "cmdline-hints unknown → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- osctl bridge ----
set +e
"${OSCTL}" kernel list --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl kernel list rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R239', d
" \
  && ok "osctl bridge surfaces R239 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" kernel nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown kernel subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_kernel_tuning: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
