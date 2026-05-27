#!/usr/bin/env bash
# scripts/build/lib/common.sh — shared helpers + strict-mode setup.
# Source from every step script and the orchestrator.

if [ -n "${__SOVEREIGN_OS_COMMON_LIB_LOADED:-}" ]; then
  return 0
fi
__SOVEREIGN_OS_COMMON_LIB_LOADED=1

# Discover repo root (relative to this lib file)
__LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Split declare+export so a failed `cd ... && pwd` is caught by `set -e`
# (an `export X=$(cmd)` masks the subshell's non-zero exit — SC2155).
SOVEREIGN_OS_ROOT="$(cd "${__LIB_DIR}/../../.." && pwd)"
export SOVEREIGN_OS_ROOT

# Standard layout
export SOVEREIGN_OS_PROFILES_DIR="${SOVEREIGN_OS_ROOT}/profiles"
export SOVEREIGN_OS_WHITELABEL_DIR="${SOVEREIGN_OS_ROOT}/whitelabel"
export SOVEREIGN_OS_SCHEMAS_DIR="${SOVEREIGN_OS_ROOT}/schemas"
export SOVEREIGN_OS_SCRIPTS_DIR="${SOVEREIGN_OS_ROOT}/scripts"

# Source siblings (state + logging) using known location to avoid
# subshell-path-discovery race.
# shellcheck source=./state.sh
. "${__LIB_DIR}/state.sh"
# shellcheck source=./logging.sh
. "${__LIB_DIR}/logging.sh"

# Strict mode for all scripts that source this lib
set -euo pipefail

# Trap to convert uncaught errors into clean failure log entries.
__sovereign_os_trap_err() {
  local line="$1" status="$2" cmd="$3"
  log_error "command failed: '${cmd}' (line ${line}, exit ${status})"
}
trap '__sovereign_os_trap_err "${LINENO}" "$?" "${BASH_COMMAND}"' ERR

# Helpers ---------------------------------------------------------------------

require_command() {
  # require_command <name> [<install-hint>]
  if ! command -v "$1" >/dev/null 2>&1; then
    log_error "missing required command: $1${2:+ (install: $2)}"
    exit 1
  fi
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    log_error "this step must run as root (sudo $0 ...)"
    exit 1
  fi
}

require_not_root() {
  if [ "$(id -u)" -eq 0 ]; then
    log_error "this step must NOT run as root"
    exit 1
  fi
}

require_file() {
  if [ ! -f "$1" ]; then
    log_error "missing required file: $1"
    exit 1
  fi
}

require_dir() {
  if [ ! -d "$1" ]; then
    log_error "missing required directory: $1"
    exit 1
  fi
}

load_profile() {
  # load_profile <profile-id> → exports SOVEREIGN_OS_PROFILE_FILE
  local id="$1"
  local f="${SOVEREIGN_OS_PROFILES_DIR}/${id}.yaml"
  require_file "$f"
  export SOVEREIGN_OS_PROFILE_ID="${id}"
  export SOVEREIGN_OS_PROFILE_FILE="$f"
  log_info "loaded profile: ${id} (${f})"
}

profile_field() {
  # profile_field <yaml-path> — extract a field from the active
  # profile. yaml-path is dot-separated (e.g. "identity.name",
  # "hardware.cpu.march"). Uses python3 yaml; no yq dependency.
  python3 - "$@" <<'PY'
import sys
try:
    import yaml
except ImportError:
    print("error: python3-yaml not installed", file=sys.stderr)
    sys.exit(2)
import os
path = sys.argv[1]
with open(os.environ["SOVEREIGN_OS_PROFILE_FILE"]) as f:
    data = yaml.safe_load(f)
node = data
for k in path.split("."):
    if isinstance(node, list):
        node = node[int(k)]
    else:
        node = node.get(k) if isinstance(node, dict) else None
    if node is None:
        print("", end="")
        sys.exit(0)
if isinstance(node, (list, dict)):
    import json
    print(json.dumps(node))
else:
    print(node)
PY
}

# Confirmation prompt (interactive only)
confirm() {
  # confirm <prompt> [<default-yes|default-no>] → returns 0 on yes
  local prompt="$1" default="${2:-default-no}"
  if [ -n "${SOVEREIGN_OS_NONINTERACTIVE:-}" ]; then
    [ "${default}" = "default-yes" ]
    return $?
  fi
  if [ "${default}" = "default-yes" ]; then
    read -rp "${prompt} [Y/n] " ans
    ans="${ans:-y}"
  else
    read -rp "${prompt} [y/N] " ans
    ans="${ans:-n}"
  fi
  [[ "${ans}" =~ ^[Yy]([Ee][Ss])?$ ]]
}
