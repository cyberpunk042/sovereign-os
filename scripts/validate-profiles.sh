#!/usr/bin/env bash
# scripts/validate-profiles.sh — profile schema-conformance + merger check
#
# Validates every profiles/*.yaml against schemas/profile.schema.yaml
# AND resolves mixins via tools/profile_merger.py, schema-validating
# the effective (merged) profile too.
#
# Exit 0 on PASS for every profile; non-zero on any FAIL.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE_DIR="${REPO_ROOT}/profiles"
SCHEMA="${REPO_ROOT}/schemas/profile.schema.yaml"

# ---------- python3 resolver ----------
PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml, jsonschema" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml, jsonschema" >/dev/null 2>&1; then
    PYTHON3="/usr/bin/python3"
  fi
fi

# Quick dep check
"${PYTHON3}" -c "import yaml, jsonschema" 2>/dev/null || {
  echo "error: missing python3 deps (yaml + jsonschema)"
  echo "  install: pip install pyyaml jsonschema"
  exit 2
}

fail=0
total=0

for p in "${PROFILE_DIR}"/*.yaml; do
  [ -e "$p" ] || continue
  id="$(basename "$p" .yaml)"
  total=$((total + 1))

  # 1. Raw-profile schema check
  if ! "${PYTHON3}" -c "
import yaml, jsonschema, sys
schema = yaml.safe_load(open('${SCHEMA}'))
instance = yaml.safe_load(open('${p}'))
jsonschema.Draft202012Validator(schema).validate(instance)
" 2>&1; then
    echo "FAIL ${id}: raw profile fails schema validation"
    fail=$((fail + 1))
    continue
  fi

  # 2. Mixin-resolved profile schema check
  if ! "${PYTHON3}" -c "
import sys
sys.path.insert(0, '${REPO_ROOT}')
import yaml, jsonschema
from tools import profile_merger
schema = yaml.safe_load(open('${SCHEMA}'))
effective = profile_merger.resolve('${id}')
jsonschema.Draft202012Validator(schema).validate(effective)
" 2>&1; then
    echo "FAIL ${id}: mixin-resolved profile fails schema validation"
    fail=$((fail + 1))
    continue
  fi

  echo "PASS ${id}"
done

echo
if [ "${fail}" -eq 0 ]; then
  echo "validate-profiles: PASS (${total} profiles)"
  exit 0
else
  echo "validate-profiles: ${fail} of ${total} FAILED"
  exit 1
fi
