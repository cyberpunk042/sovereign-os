#!/usr/bin/env bash
# scripts/git-hooks/install.sh — symlink the sovereign-os git hooks
# into .git/hooks/. Idempotent.
#
# Usage:
#   scripts/git-hooks/install.sh           install all available hooks
#   scripts/git-hooks/install.sh pre-commit  install one specific hook
#
# Operator's direct-push-to-main workflow makes the pre-commit gate
# the only pre-merge enforcement layer; installing is recommended.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(git rev-parse --show-toplevel)"

cd "${__REPO_ROOT}"

hooks_dir=".git/hooks"
[ -d "${hooks_dir}" ] || { echo "error: not a git repo"; exit 1; }

# Available hooks (files in __SCRIPT_DIR excluding install.sh + README)
declare -a available
while IFS= read -r -d '' f; do
  base="$(basename "${f}")"
  case "${base}" in
    install.sh|README.md) continue ;;
  esac
  available+=("${base}")
done < <(find "${__SCRIPT_DIR}" -maxdepth 1 -type f -print0)

if [ "$#" -gt 0 ]; then
  to_install=("$@")
else
  to_install=("${available[@]}")
fi

for hook in "${to_install[@]}"; do
  src="${__SCRIPT_DIR}/${hook}"
  dst="${hooks_dir}/${hook}"
  if [ ! -f "${src}" ]; then
    echo "✗ unknown hook: ${hook} (available: ${available[*]})"
    exit 1
  fi
  chmod +x "${src}"
  # Use relative-to-.git symlink for repo-portability
  rel="$(realpath --relative-to="${hooks_dir}" "${src}")"
  ln -sf "${rel}" "${dst}"
  echo "✓ installed: ${hook} → ${rel}"
done

echo
echo "Installed hooks gate every commit per the sovereign-os pre-commit"
echo "contract. To bypass for one commit: git commit --no-verify"
