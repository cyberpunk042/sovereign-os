#!/usr/bin/env bash
# scripts/validate-profiles.sh — profile schema-conformance check
#
# PLACEHOLDER — substantive implementation lands at PR 10 (TDD harness
# bootstrap). The actual validator uses a YAML/JSON-Schema library
# (python3 jsonschema or yamale; choice decided at PR 10 per substrate
# decision).
#
# When implemented, this script:
#   1. Loads schemas/profile.schema.yaml
#   2. For each profiles/*.yaml: resolve mixins + parent → effective
#      profile; schema-validate; report PASS / FAIL with file:line.
#   3. For each profiles/mixins/*.yaml: schema-validate against
#      schemas/mixin.schema.yaml (also lands at PR 10).
#   4. Returns 0 on PASS; non-zero on any FAIL (CI gate).
#
# Until then, this stub exits 0 with a notice. CI doesn't gate on
# profile validation yet.

set -euo pipefail

cat <<'EOF'
sovereign-os profile validator — PLACEHOLDER (see scripts/validate-profiles.sh header)

Schema-conformance is currently author-checked. The CI-gated
validator lands at PR 10 (TDD harness bootstrap).

For now, listing declared profiles:
EOF

# Find profiles (relative to this script's directory)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE_DIR="${REPO_ROOT}/profiles"

if [ -d "${PROFILE_DIR}" ]; then
  printf '\nProfiles found:\n'
  find "${PROFILE_DIR}" -maxdepth 1 -name '*.yaml' -type f | sort | while read -r p; do
    printf '  - %s\n' "$(basename "$p" .yaml)"
  done

  if [ -d "${PROFILE_DIR}/mixins" ]; then
    printf '\nMixins found:\n'
    find "${PROFILE_DIR}/mixins" -name '*.yaml' -type f | sort | while read -r m; do
      printf '  - %s\n' "$(basename "$m" .yaml)"
    done
  fi
fi

echo
echo "Validation skipped — implementation pending PR 10."
exit 0
