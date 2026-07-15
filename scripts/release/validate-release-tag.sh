#!/usr/bin/env bash
# Validate that a release tag is an exact projection of the canonical VERSION.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
require_git_tag=0

if [ "${1:-}" = "--require-git-tag" ]; then
  require_git_tag=1
  shift
fi

tag="${1:-}"
if [ -z "${tag}" ] || [ "$#" -ne 1 ]; then
  echo "usage: $0 [--require-git-tag] v<version>" >&2
  exit 2
fi

[ -r "${ROOT}/VERSION" ] || {
  echo "error: canonical VERSION file is missing" >&2
  exit 1
}
IFS= read -r version < "${ROOT}/VERSION"

if [[ ! "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$ ]]; then
  echo "error: invalid canonical VERSION: ${version:-<empty>}" >&2
  exit 1
fi
if [ "${tag}" != "v${version}" ]; then
  echo "error: release tag ${tag} does not match canonical VERSION v${version}" >&2
  exit 1
fi

if [ "${require_git_tag}" -eq 1 ]; then
  tag_commit="$(git -C "${ROOT}" rev-parse "${tag}^{commit}" 2>/dev/null)" || {
    echo "error: tag ${tag} does not resolve to a commit" >&2
    exit 1
  }
  head_commit="$(git -C "${ROOT}" rev-parse HEAD)"
  if [ "${tag_commit}" != "${head_commit}" ]; then
    echo "error: tag ${tag} resolves to ${tag_commit}, but checkout is ${head_commit}" >&2
    exit 1
  fi
fi

printf 'release tag valid: %s -> %s\n' "${tag}" "${version}"
