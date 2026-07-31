#!/usr/bin/env bash
# scripts/iac/test-fire-timers.sh — fire the timer-driven units that have never
# run, so their first real failure happens now rather than unattended at 03:00.
#
# Converge asserts that timers are ENABLED and ACTIVE. It cannot assert that the
# work they trigger succeeds, because most of these fire daily or weekly and had
# not yet run once since the machine was rebuilt. That gap is exactly where the
# original install's problems lived: units that looked healthy and had never
# executed.
#
# Each is a oneshot; firing it early is idempotent in effect (they re-run on
# schedule regardless). zfs-scrub starts a background scrub — safe, read-only,
# and cancellable with `zpool scrub -s tank`.
#
# Run: sudo bash scripts/iac/test-fire-timers.sh
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "must run as root"; exit 1; }

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# Resolve the units a timer activates, keeping only ones never yet run.
mapfile -t _svcs < <(
  systemctl list-timers 'sovereign-*' --no-pager --no-legend 2>/dev/null \
  | awk '{print $NF}' | sort -u
)

# Fire anything that has NEVER run, or that ran and FAILED. The first version
# only looked for never-run, which made it useless for exactly the case it had
# just created: once a unit is fired and fails, it is no longer "never run", so
# re-running the script after fixing the bug reported "nothing to test-fire" and
# verified nothing. A test tool that cannot re-test what it just found broken is
# only useful once.
#
# --all re-checks everything, including units that already succeeded.
_never=()
for s in "${_svcs[@]}"; do
  _ts="$(systemctl show "$s" -p ExecMainStartTimestamp --value 2>/dev/null)"
  _st="$(systemctl show "$s" -p ExecMainStatus --value 2>/dev/null)"
  if [ "${1:-}" = "--all" ] || [ -z "${_ts}" ] || { [ -n "${_st}" ] && [ "${_st}" != 0 ]; }; then
    _never+=("$s")
  fi
done

if [ "${#_never[@]}" -eq 0 ]; then
  echo "  every timer-driven unit has run and succeeded — nothing to re-test"
  echo "  (use --all to fire them anyway)"
  exit 0
fi

say "firing ${#_never[@]} unit(s): never-run or last-run-failed"
printf '  %s\n' "${_never[@]}"

_fail=0
for s in "${_never[@]}"; do
  say "${s}"
  systemctl start "${s}" >/dev/null 2>&1
  # oneshots finish quickly; give the slower ones a moment.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    systemctl is-active --quiet "${s}" 2>/dev/null || break
    sleep 2
  done
  _st="$(systemctl show "${s}" -p ExecMainStatus --value 2>/dev/null)"
  if [ "${_st}" = 0 ]; then
    printf '  \033[32mok\033[0m   exit 0\n'
  else
    printf '  \033[31mFAIL\033[0m exit %s\n' "${_st:-?}"
    _fail=$((_fail+1))
    journalctl -u "${s}" -n 6 --no-pager 2>/dev/null \
      | grep -viE 'systemd\[1\]|Starting |Started ' | tail -4 | sed 's/^/       /'
  fi
done

say "summary"
echo "  fired ${#_never[@]}, failed ${_fail}"
[ "${_fail}" -gt 0 ] && echo "  these would have failed unattended on their next scheduled fire"
systemctl --failed --no-pager --no-legend 2>/dev/null | sed 's/^/  still failed: /'
exit 0
