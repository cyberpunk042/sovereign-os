#!/usr/bin/env bash
# scripts/iac/converge.sh — make this machine match its profile.
#
# Day-2 convergence for sovereign-os. Declarative in the sense that matters:
# the desired state lives in data (profiles/<id>.yaml provisioning.* plus
# converge.conf for documented machine truths), and the modules only enforce.
#
# Re-runnable by contract: a second run on an unchanged machine reports
# "0 changed". If it doesn't, a module is not idempotent and that's a bug.
#
# WHY THIS EXISTS
#   Package upgrades silently revert package-owned files. dpkg --verify already
#   flags profiles/sain-01.yaml as modified (??5??????) — it is NOT a conffile,
#   so `apt upgrade sovereign-os-cockpit` will overwrite it and take the GPU
#   power cap with it. Converge is the loop that puts it back.
#
# USAGE
#   sudo ./converge.sh                 # converge everything gated on
#   sudo ./converge.sh --dry-run       # show what would change, touch nothing
#   sudo ./converge.sh --only 30       # run one module (prefix match)
#   sudo ./converge.sh --list          # list modules and their gates
#   sudo ./converge.sh --verbose       # show each underlying command
set -uo pipefail

IAC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export IAC_DIR

# shellcheck source=./lib/iac.sh
. "${IAC_DIR}/lib/iac.sh"

# ---- args ----
ONLY=""; LIST=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run|-n) IAC_DRY_RUN=1 ;;
    --verbose|-v) IAC_VERBOSE=1 ;;
    --only)       ONLY="${2:-}"; shift ;;
    --only=*)     ONLY="${1#*=}" ;;
    --list|-l)    LIST=1 ;;
    --profile)    IAC_PROFILE_ID="${2:-}"; IAC_PROFILE_FILE="/opt/sovereign-os/profiles/${2:-}.yaml"; shift ;;
    --help|-h)    sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
    *) printf 'unknown argument: %s (try --help)\n' "$1" >&2; exit 2 ;;
  esac
  shift
done
export IAC_DRY_RUN IAC_VERBOSE IAC_PROFILE_ID IAC_PROFILE_FILE

# ---- config ----
# shellcheck source=./converge.conf
[ -r "${IAC_DIR}/converge.conf" ] && . "${IAC_DIR}/converge.conf"

if [ "${LIST}" = 1 ]; then
  printf 'modules in %s:\n\n' "${IAC_DIR}/modules"
  for m in "${IAC_DIR}"/modules/*.sh; do
    [ -f "$m" ] || continue
    n="$(basename "$m" .sh)"
    desc="$(sed -n '2s/^# *//p' "$m")"
    gate_var="$(sed -n 's/^# *gate: *\([A-Za-z_][A-Za-z0-9_]*\).*/\1/p' "$m" | head -1)"
    gate_val="${!gate_var:-1}"
    [ -n "${gate_var}" ] && state="$( [ "${gate_val}" = 1 ] && echo on || echo OFF )" || state="on"
    printf '  %-26s [%s]  %s\n' "$n" "$state" "$desc"
  done
  exit 0
fi

need_root

[ -r "${IAC_PROFILE_FILE}" ] || {
  printf 'profile not readable: %s\n' "${IAC_PROFILE_FILE}" >&2; exit 1; }

printf '%ssovereign-os converge%s\n' "${_C_HD}" "${_C_Z}"
printf '  profile : %s (%s)\n' "${IAC_PROFILE_ID}" "${IAC_PROFILE_FILE}"
printf '  host    : %s   kernel %s\n' "$(hostname)" "$(uname -r)"
[ "${IAC_DRY_RUN}" = 1 ] && printf '  %sMODE    : DRY RUN — nothing will be modified%s\n' "${_C_CH}" "${_C_Z}"

# ---- run modules in lexical (numeric-prefix) order ----
ran=0
matched=0
for module in "${IAC_DIR}"/modules/*.sh; do
  [ -f "${module}" ] || continue
  name="$(basename "${module}" .sh)"

  if [ -n "${ONLY}" ] && [[ "${name}" != "${ONLY}"* ]]; then continue; fi
  # Matched the --only filter. Tracked separately from `ran`, because a module
  # that matched but is gated OFF is not "no such module" — reporting it that
  # way made `--only 95` look like a typo when it had correctly refused to run.
  matched=$((matched+1))

  # `# gate: VAR` in the module header names the converge.conf switch.
  gate_var="$(sed -n 's/^# *gate: *\([A-Za-z_][A-Za-z0-9_]*\).*/\1/p' "${module}" | head -1)"
  if [ -n "${gate_var}" ] && [ "${!gate_var:-1}" != 1 ]; then
    iac_module_header "${name}"
    skip "module disabled (${gate_var}=0 in converge.conf)"
    continue
  fi

  iac_module_header "${name}"
  # shellcheck source=/dev/null
  . "${module}"
  ran=$((ran+1))
done

if [ -n "${ONLY}" ] && [ "${matched}" -eq 0 ]; then
  printf '\nno module matched --only %s\n' "${ONLY}" >&2
  exit 2
fi

iac_daemon_reload

# ---- report ----
printf '\n%s── converge report %s\n' "${_C_HD}" "${_C_Z}"
printf '  ok      %d\n' "${IAC_OK}"
printf '  changed %d\n' "${IAC_CHANGED}"
printf '  skipped %d\n' "${IAC_SKIP}"
printf '  failed  %d\n' "${IAC_FAIL}"

if [ "${IAC_CHANGED}" -gt 0 ]; then
  printf '\n  changes:\n'
  for c in "${IAC_CHANGES[@]}"; do printf '    %s%s%s\n' "${_C_CH}" "${c}" "${_C_Z}"; done
fi
if [ "${IAC_SKIP}" -gt 0 ]; then
  printf '\n  skipped:\n'
  for s in "${IAC_SKIPS[@]}"; do printf '    %s%s%s\n' "${_C_SK}" "${s}" "${_C_Z}"; done
fi
if [ "${IAC_FAIL}" -gt 0 ]; then
  printf '\n  failures:\n'
  for f in "${IAC_FAILURES[@]}"; do printf '    %s%s%s\n' "${_C_ER}" "${f}" "${_C_Z}"; done
  printf '\n%sconverge INCOMPLETE%s\n' "${_C_ER}" "${_C_Z}"
  exit 1
fi

if [ "${IAC_DRY_RUN}" = 1 ]; then
  printf '\n%sdry run complete — re-run without --dry-run to apply%s\n' "${_C_CH}" "${_C_Z}"
elif [ "${IAC_CHANGED}" -eq 0 ]; then
  printf '\n%sconverged — machine already matches profile%s\n' "${_C_OK}" "${_C_Z}"
else
  printf '\n%sconverged — %d change(s) applied%s\n' "${_C_OK}" "${IAC_CHANGED}" "${_C_Z}"
  printf 'run again to confirm idempotency (expect: 0 changed)\n'
fi
