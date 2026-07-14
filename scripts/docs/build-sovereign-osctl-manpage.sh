#!/usr/bin/env bash
# Regenerate or verify the committed sovereign-osctl(1) roff artifact.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE="${ROOT}/docs/man/sovereign-osctl.1.md"
TARGET="${ROOT}/docs/man/sovereign-osctl.1"
MODE="${1:-build}"

command -v pandoc >/dev/null 2>&1 || {
  echo "error: pandoc is required to regenerate the man page" >&2
  exit 1
}

tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT
pandoc -s -t man "${SOURCE}" -o "${tmp}"

case "${MODE}" in
  build)
    install -m 644 "${tmp}" "${TARGET}"
    echo "generated ${TARGET}"
    ;;
  check)
    if ! cmp -s "${tmp}" "${TARGET}"; then
      echo "error: ${TARGET} is stale; run make man" >&2
      diff -u "${TARGET}" "${tmp}" || true
      exit 1
    fi
    echo "man page is current"
    ;;
  *)
    echo "usage: $0 [build|check]" >&2
    exit 2
    ;;
esac
