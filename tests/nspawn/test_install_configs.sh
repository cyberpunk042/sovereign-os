#!/usr/bin/env bash
# tests/nspawn/test_install_configs.sh
#
# Layer 3 test for the install-time configuration files under
# config/cloud-init/ + config/preseed/. Gates SDD-013 (Q-008 installer
# experience) — image-only installs depend on these configs being
# syntactically valid + lockstep-consistent with the declared profiles.
#
# Asserts:
#   - every config/cloud-init/<id>.user-data.example.yaml parses as
#     YAML (python3 -c 'yaml.safe_load')
#   - first non-blank line is '#cloud-config' (cloud-init requirement)
#   - each cloud-init file declares a hostname matching its profile id
#     (or 'sovereign-<id>' as the documented convention)
#   - each cloud-init file declares the 'operator' user with SSH key
#   - each cloud-init writes /etc/sovereign-os/active-profile with the
#     matching profile id
#   - every profile in profiles/*.yaml has a corresponding cloud-init
#     example (lockstep coverage gate)
#   - preseed files parse as `d-i` directive lines (well-formed; we
#     don't run them)

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

ci_dir="${__REPO_ROOT}/config/cloud-init"
ps_dir="${__REPO_ROOT}/config/preseed"
profiles_dir="${__REPO_ROOT}/profiles"

[ -d "${ci_dir}" ] || { echo "FAIL: missing ${ci_dir}"; exit 1; }
[ -d "${profiles_dir}" ] || { echo "FAIL: missing ${profiles_dir}"; exit 1; }

# python3 resolver — some CI envs lack PyYAML in the first python3.
PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3="/usr/bin/python3"
  fi
fi

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_install_configs.sh"
echo

# ----------- enumerate declared profiles ---------------

mapfile -t profile_ids < <(find "${profiles_dir}" -maxdepth 1 -name '*.yaml' -type f | sort | xargs -n1 basename | sed 's/\.yaml$//')

if [ "${#profile_ids[@]}" -ge 2 ]; then
  ok "discovered ${#profile_ids[@]} profile(s): ${profile_ids[*]}"
else
  ko "expected >=2 profiles, found ${#profile_ids[@]}"
fi

# ----------- every profile has a matching cloud-init ---------------

for pid in "${profile_ids[@]}"; do
  ci_file="${ci_dir}/${pid}.user-data.example.yaml"
  if [ -f "${ci_file}" ]; then
    ok "lockstep: profile '${pid}' has cloud-init example"
  else
    ko "lockstep: profile '${pid}' MISSING cloud-init example (${ci_file})"
  fi
done

# ----------- each cloud-init file validates ---------------

for ci_file in "${ci_dir}"/*.user-data.example.yaml; do
  fname="$(basename "${ci_file}")"

  # 1. First non-blank, non-comment-only line must be #cloud-config header
  if head -1 "${ci_file}" | grep -q '^#cloud-config'; then
    ok "${fname}: starts with #cloud-config header"
  else
    ko "${fname}: missing #cloud-config header (first line)"
  fi

  # 2. YAML parses
  if "${PYTHON3}" -c "
import yaml, sys
try:
    yaml.safe_load(open('${ci_file}'))
    sys.exit(0)
except Exception as e:
    print(e, file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; then
    ok "${fname}: YAML parses"
  else
    ko "${fname}: YAML parse error"
  fi

  # 3. Declares an 'operator' user
  if grep -qE "^\s*-?\s*name:\s*operator" "${ci_file}"; then
    ok "${fname}: declares 'operator' user"
  else
    ko "${fname}: missing 'operator' user declaration"
  fi

  # 4. Has ssh_authorized_keys
  if grep -q "ssh_authorized_keys:" "${ci_file}"; then
    ok "${fname}: has ssh_authorized_keys block"
  else
    ko "${fname}: missing ssh_authorized_keys block"
  fi

  # 5. Writes /etc/sovereign-os/active-profile with a matching id
  pid="${fname%.user-data.example.yaml}"
  if "${PYTHON3}" -c "
import yaml, sys, re
data = yaml.safe_load(open('${ci_file}'))
files = data.get('write_files', []) or []
for f in files:
    if f.get('path') == '/etc/sovereign-os/active-profile':
        if (f.get('content') or '').strip() == '${pid}':
            sys.exit(0)
sys.exit(1)
"; then
    ok "${fname}: writes /etc/sovereign-os/active-profile with id='${pid}'"
  else
    ko "${fname}: missing or mismatched active-profile write"
  fi

  # 6. Hostname declared and matches profile id (loosely — operator
  # may use 'sovereign-<id>' style for headless variants)
  hostname_value="$(${PYTHON3} -c "
import yaml
data = yaml.safe_load(open('${ci_file}'))
print(data.get('hostname') or '')
")"
  if [ -n "${hostname_value}" ]; then
    if [[ "${hostname_value}" == "${pid}" || "${hostname_value}" == "sovereign-${pid}" || "${hostname_value}" == *"${pid}"* ]]; then
      ok "${fname}: hostname='${hostname_value}' references profile id"
    else
      ko "${fname}: hostname='${hostname_value}' doesn't reference profile id '${pid}'"
    fi
  else
    ko "${fname}: hostname not declared"
  fi
done

# ----------- preseed file(s) basic syntactic gate ---------------

if [ -d "${ps_dir}" ]; then
  for ps_file in "${ps_dir}"/*.preseed.example.cfg; do
    [ -f "${ps_file}" ] || continue
    fname="$(basename "${ps_file}")"

    # Must contain at least one 'd-i ...' directive
    if grep -qE "^\s*d-i\s+\S+\s+\S+" "${ps_file}"; then
      ok "${fname}: contains at least one d-i directive"
    else
      ko "${fname}: no d-i directives found (malformed preseed?)"
    fi

    # No CRLF line endings (preseed parsers are sensitive)
    if file "${ps_file}" 2>/dev/null | grep -q "CRLF"; then
      ko "${fname}: has CRLF line endings (use LF)"
    else
      ok "${fname}: LF line endings"
    fi
  done
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_install_configs: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
