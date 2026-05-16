#!/usr/bin/env bash
# scripts/whitelabel/first-boot-greeting.sh
#
# Strategy: first-boot-script per SDD-007. Whitelabel-driven greeting
# shown to operator at first boot. Reads the whitelabel manifest for
# the active branding strings and writes a /etc/motd entry.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "first-boot-greeting" "whitelabel first-boot greeting"

# Idempotent — only on first boot
flag="/var/lib/sovereign-os/first-boot-greeting.done"
if [ -f "${flag}" ]; then
  log_info "first-boot greeting already shown"
  exit 0
fi

wl_name="$(profile_field whitelabel.profile)"
: "${wl_name:=default}"
wl_file="${SOVEREIGN_OS_WHITELABEL_DIR}/${wl_name}.yaml"

if [ -f "${wl_file}" ]; then
  os_pretty_name="$(python3 -c "
import yaml
with open('${wl_file}') as f:
    d = yaml.safe_load(f)
print((d.get('branding') or {}).get('os_pretty_name', 'sovereign-os'))
")"
  motd="$(python3 -c "
import yaml
with open('${wl_file}') as f:
    d = yaml.safe_load(f)
print((d.get('branding') or {}).get('motd', ''))
")"

  if [ -n "${motd}" ]; then
    cat <<EOF

╔══════════════════════════════════════════════════════════════════╗
   Welcome to ${os_pretty_name}

${motd}
╚══════════════════════════════════════════════════════════════════╝

EOF
  fi
fi

mkdir -p "$(dirname "${flag}")"
touch "${flag}"

log_info "first-boot-greeting complete"
