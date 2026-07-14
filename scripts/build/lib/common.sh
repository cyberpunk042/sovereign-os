#!/usr/bin/env bash
# scripts/build/lib/common.sh — shared helpers + strict-mode setup.
# Source from every step script and the orchestrator.

if [ -n "${__SOVEREIGN_OS_COMMON_LIB_LOADED:-}" ]; then
  return 0
fi
__SOVEREIGN_OS_COMMON_LIB_LOADED=1

# Discover the sovereign-os root (relative to this lib file). Two layouts
# exist (caught on the first installed-CLI run 2026-06-12 — doctor died
# silently looking for /usr/profiles/):
#   in-repo:    <root>/scripts/build/lib/common.sh   → root is 3 up
#   installed:  <PREFIX>/lib/sovereign-os/lib/common.sh (make install
#               flattens) → root is 1 up (profiles/ is a SIBLING of lib/)
# A pre-set SOVEREIGN_OS_ROOT (e.g. from sovereign-osctl's own context
# detection) always wins.
__LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "${SOVEREIGN_OS_ROOT:-}" ]; then
  # Split declare+export so a failed `cd ... && pwd` is caught by `set -e`
  # (an `export X=$(cmd)` masks the subshell's non-zero exit — SC2155).
  if [ -d "${__LIB_DIR}/../profiles" ]; then
    SOVEREIGN_OS_ROOT="$(cd "${__LIB_DIR}/.." && pwd)"
  else
    SOVEREIGN_OS_ROOT="$(cd "${__LIB_DIR}/../../.." && pwd)"
  fi
fi
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

# Serialize boot-config regeneration across concurrently-running first-boot hooks.
#
# R1 (SDD-998): `update-initramfs -u` is NOT safe to run in parallel — two
# invocations race on the same /boot/initrd.img-* build dir + atomic rename and
# can leave a truncated/half-written initramfs → the box does not boot. Three
# first-boot oneshots regenerate initramfs (nvidia-driver-bind, vfio-bind,
# zfs-arc-clamp) and are all pulled in together by sovereign-firstboot.target
# with no ordering between them (their only After= is friction-audit), so systemd
# starts them in parallel and their initramfs rebuilds overlap. update-grub has
# the same single-writer property on grub.cfg. `boot_regen` funnels every such
# call through one flock so they run strictly one-at-a-time.
SOVEREIGN_OS_BOOT_REGEN_LOCK="${SOVEREIGN_OS_BOOT_REGEN_LOCK:-/run/lock/sovereign-os-boot-regen.lock}"

boot_regen() {
  # boot_regen <cmd> [args...] — run a boot-config regeneration command
  # (update-initramfs / update-grub) under the shared serialization lock.
  # `-w 300` keeps a wedged holder from hanging first boot forever (it fails
  # the wait instead, and the caller's `|| log_warn` records it). If flock is
  # unavailable (minimal image), run directly — a missing lock must never mean
  # a skipped regeneration.
  if command -v flock >/dev/null 2>&1; then
    flock -w 300 "${SOVEREIGN_OS_BOOT_REGEN_LOCK}" "$@"
  else
    "$@"
  fi
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
