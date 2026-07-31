#!/usr/bin/env bash
# scripts/iac/lib/iac.sh — converge primitives.
#
# Every mutation in this tree goes through one of the ensure_* helpers below.
# They all follow the same contract:
#   - decide whether the system already matches the desired state
#   - if it does            → record OK   and do nothing
#   - if it does not        → record CHANGED and apply (unless --dry-run)
#   - if applying fails     → record FAIL and keep going
# That contract is what makes `converge.sh` idempotent and re-runnable: a
# second run on an unchanged machine must report 0 changed.
#
# shellcheck shell=bash

# ---- counters (consumed by converge.sh's final report) ----
IAC_OK=0; IAC_CHANGED=0; IAC_FAIL=0; IAC_SKIP=0
IAC_CHANGES=(); IAC_FAILURES=(); IAC_SKIPS=()

: "${IAC_DRY_RUN:=0}"
: "${IAC_VERBOSE:=0}"

# ---- output ----
if [ -t 1 ]; then
  _C_OK=$'\033[32m'; _C_CH=$'\033[33m'; _C_ER=$'\033[31m'
  _C_SK=$'\033[90m'; _C_HD=$'\033[1m';  _C_Z=$'\033[0m'
else
  _C_OK=; _C_CH=; _C_ER=; _C_SK=; _C_HD=; _C_Z=
fi

iac_module_header() { printf '\n%s── %s %s\n' "${_C_HD}" "$*" "${_C_Z}"; }
iac_info()  { printf '     %s\n' "$*"; }
iac_debug() { [ "${IAC_VERBOSE}" = 1 ] && printf '     %s· %s%s\n' "${_C_SK}" "$*" "${_C_Z}" || true; }

ok()      { IAC_OK=$((IAC_OK+1));         printf '  %sok%s      %s\n' "${_C_OK}" "${_C_Z}" "$*"; }
changed() { IAC_CHANGED=$((IAC_CHANGED+1)); IAC_CHANGES+=("$*")
            printf '  %schanged%s %s\n' "${_C_CH}" "${_C_Z}" "$*"; }
fail()    { IAC_FAIL=$((IAC_FAIL+1));     IAC_FAILURES+=("$*")
            printf '  %sFAIL%s    %s\n' "${_C_ER}" "${_C_Z}" "$*"; }
skip()    { IAC_SKIP=$((IAC_SKIP+1));     IAC_SKIPS+=("$*")
            printf '  %sskip%s    %s\n' "${_C_SK}" "${_C_Z}" "$*"; }

# ---- dry-run aware execution ----
# run <description> <cmd...> — run a command as part of a CHANGED action.
# In dry-run it prints what it would do and returns success.
run() {
  local desc="$1"; shift
  if [ "${IAC_DRY_RUN}" = 1 ]; then
    iac_debug "[${desc}] would run: $*"
    return 0
  fi
  if "$@" >/dev/null 2>&1; then
    iac_debug "[${desc}] ok: $*"
    return 0
  fi
  iac_debug "[${desc}] FAILED: $*"
  return 1
}

need_root() {
  [ "$(id -u)" -eq 0 ] || { printf '%sconverge must run as root%s\n' "${_C_ER}" "${_C_Z}" >&2; exit 1; }
}

# ---- profile access: the profile IS the desired-state spec ----
# We deliberately read the SAME file the sovereign-os hooks read, so converge
# and the runtime can never disagree about intent.
: "${IAC_PROFILE_ID:=$( [ -r /etc/sovereign-os/active-profile ] && cat /etc/sovereign-os/active-profile || echo sain-01 )}"
: "${IAC_PROFILE_FILE:=/opt/sovereign-os/profiles/${IAC_PROFILE_ID}.yaml}"

# profile_get <dotted.path> [default] — echo a scalar from the profile.
# Lists are emitted newline-separated. Missing paths echo the default (or "").
profile_get() {
  python3 - "$1" "${2-}" <<'PY' 2>/dev/null || true
import os, sys, yaml
path, default = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
try:
    with open(os.environ["IAC_PROFILE_FILE"]) as f:
        node = yaml.safe_load(f)
except Exception:
    print(default); sys.exit(0)
for k in path.split("."):
    if isinstance(node, dict):
        node = node.get(k)
    elif isinstance(node, list) and k.isdigit():
        node = node[int(k)] if int(k) < len(node) else None
    else:
        node = None
    if node is None:
        print(default); sys.exit(0)
if isinstance(node, list):
    print("\n".join(str(x) for x in node))
elif isinstance(node, bool):
    print("true" if node else "false")
else:
    print(node)
PY
}

# ---- file convergence ----
# ensure_file <path> <mode> <owner:group> — content on stdin.
# Writes only when the content or metadata actually differs.
ensure_file() {
  local path="$1" mode="${2:-0644}" owner="${3:-root:root}"
  local new; new="$(cat)"
  local label="file ${path}"

  if [ -f "${path}" ] && [ "$(cat "${path}" 2>/dev/null)" = "${new}" ]; then
    local cur_mode cur_own
    cur_mode="$(stat -c '%a' "${path}" 2>/dev/null)"
    cur_own="$(stat -c '%U:%G' "${path}" 2>/dev/null)"
    if [ "${cur_mode}" = "${mode#0}" ] || [ "0${cur_mode}" = "${mode}" ]; then
      if [ "${cur_own}" = "${owner}" ]; then ok "${label}"; return 0; fi
    fi
  fi

  if [ "${IAC_DRY_RUN}" = 1 ]; then changed "${label}"; return 0; fi

  install -d "$(dirname "${path}")" 2>/dev/null || true
  if printf '%s\n' "${new}" > "${path}.iac-tmp" 2>/dev/null \
     && chmod "${mode}" "${path}.iac-tmp" 2>/dev/null \
     && chown "${owner}" "${path}.iac-tmp" 2>/dev/null \
     && mv -f "${path}.iac-tmp" "${path}" 2>/dev/null; then
    changed "${label}"
  else
    rm -f "${path}.iac-tmp" 2>/dev/null || true
    fail "${label} — could not write"
  fi
}

ensure_dir() {
  local path="$1" mode="${2:-0755}" owner="${3:-root:root}"
  if [ -d "${path}" ]; then ok "dir ${path}"; return 0; fi
  if [ "${IAC_DRY_RUN}" = 1 ]; then changed "dir ${path}"; return 0; fi
  if install -d -m "${mode}" -o "${owner%%:*}" -g "${owner##*:}" "${path}" 2>/dev/null; then
    changed "dir ${path}"
  else
    fail "dir ${path} — could not create"
  fi
}

# ---- systemd convergence ----
# ensure_unit_state <unit> <masked|disabled|enabled> [started|stopped]
ensure_unit_state() {
  local unit="$1" want="$2" run_state="${3:-}"
  local cur; cur="$(systemctl is-enabled "${unit}" 2>/dev/null || true)"
  local label="unit ${unit} → ${want}"

  case "${want}" in
    masked)
      if [ "${cur}" = "masked" ]; then ok "${label}"
      else
        if run "mask" systemctl stop "${unit}" ; then :; fi
        if run "mask" systemctl mask "${unit}"; then changed "${label}"; else fail "${label}"; fi
      fi
      ;;
    disabled)
      # A masked unit is not "disabled" — unmask first so the operator can start
      # it by hand without fighting a leftover /dev/null symlink.
      if [ "${cur}" = "masked" ]; then
        if run "unmask" systemctl unmask "${unit}"; then changed "unit ${unit} unmasked"; else fail "unit ${unit} unmask"; fi
        cur="$(systemctl is-enabled "${unit}" 2>/dev/null || true)"
      fi
      if [ "${cur}" = "disabled" ] || [ "${cur}" = "static" ] || [ -z "${cur}" ]; then ok "${label}"
      else
        if run "disable" systemctl disable "${unit}"; then changed "${label}"; else fail "${label}"; fi
      fi
      ;;
    enabled)
      if [ "${cur}" = "masked" ]; then
        if run "unmask" systemctl unmask "${unit}"; then changed "unit ${unit} unmasked"; else fail "unit ${unit} unmask"; fi
        cur=""
      fi
      if [ "${cur}" = "enabled" ]; then ok "${label}"
      else
        if run "enable" systemctl enable "${unit}"; then changed "${label}"; else fail "${label}"; fi
      fi
      ;;
    *) fail "ensure_unit_state: unknown desired state '${want}'"; return 1 ;;
  esac

  case "${run_state}" in
    started)
      # "started" means STAYS started. Three separate units in this codebase
      # (sovereign-gatewayd, nut-driver@, sovereign-open-computer) carry
      # Restart= and will respawn forever on a bad config or a half-finished
      # provision. `systemctl start` returns success for all of them — it only
      # reports that the job was queued, not that the service survived. Every
      # time converge trusted that, it handed back a machine quietly burning
      # PIDs while reporting "converged".
      #
      # So: start it, let it settle, and confirm it is BOTH active AND not
      # accumulating restarts. If it will not hold, stop it — a quiet
      # diagnosable machine beats a silent restart loop — and fail loudly.
      if systemctl is-active --quiet "${unit}" 2>/dev/null; then
        ok "unit ${unit} active"
      elif ! run "start" systemctl start "${unit}"; then
        fail "unit ${unit} start"
      elif [ "${IAC_DRY_RUN}" = 1 ]; then
        changed "unit ${unit} started"
      else
        local _r0 _r1 _settled=0
        _r0="$(systemctl show "${unit}" -p NRestarts --value 2>/dev/null || echo 0)"
        for _ in 1 2 3 4 5 6; do
          sleep 1
          systemctl is-active --quiet "${unit}" 2>/dev/null && { _settled=1; break; }
        done
        _r1="$(systemctl show "${unit}" -p NRestarts --value 2>/dev/null || echo 0)"

        if [ "${_settled}" = 1 ] && [ "${_r1}" -le "${_r0}" ] 2>/dev/null; then
          changed "unit ${unit} started"
        elif [ "${_settled}" = 1 ]; then
          # Active, but it restarted to get there — it is flapping, not healthy.
          systemctl stop "${unit}" >/dev/null 2>&1 || true
          fail "unit ${unit} is flapping (${_r0}→${_r1} restarts) — stopped it; see: journalctl -u ${unit}"
        else
          systemctl stop "${unit}" >/dev/null 2>&1 || true
          # Prefer a line that looks like a DIAGNOSIS over merely the last line —
          # picking the tail blindly reported a service's own startup banner
          # ("=== Starting 'sovereign' [prod] …") as though it were the error.
          local _why _jrnl
          _jrnl="$(journalctl -u "${unit}" -n 25 --no-pager 2>/dev/null \
                   | grep -viE 'systemd\[1\]:|Scheduled restart|^-- ')"
          _why="$(printf '%s\n' "${_jrnl}" \
                  | grep -iE 'error|fail|cannot|could not|denied|refused|not found|no such|missing|unable' \
                  | grep -oE '[^]]*$' | tail -1)"
          # Fall back to the last line only when nothing self-identifies as an error.
          [ -n "${_why}" ] || _why="$(printf '%s\n' "${_jrnl}" | grep -oE '[^]]*$' | tail -1)"
          fail "unit ${unit} will not stay up — stopped it${_why:+ — ${_why}}"
        fi
      fi
      ;;
    stopped)
      if ! systemctl is-active --quiet "${unit}" 2>/dev/null; then ok "unit ${unit} inactive"
      elif run "stop" systemctl stop "${unit}"; then changed "unit ${unit} stopped"
      else fail "unit ${unit} stop"; fi
      ;;
  esac
}

# ensure_dropin <unit> <name> — drop-in content on stdin.
# Drop-ins live in /etc/systemd/system/<unit>.d/ which dpkg never owns, so they
# survive package upgrades. Prefer this over editing a shipped unit file.
ensure_dropin() {
  local unit="$1" name="$2"
  ensure_file "/etc/systemd/system/${unit}.d/${name}.conf" 0644 root:root
}

iac_daemon_reload() {
  [ "${IAC_DRY_RUN}" = 1 ] && return 0
  systemctl daemon-reload 2>/dev/null || true
}
