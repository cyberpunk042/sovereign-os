#!/usr/bin/env bash
# Regenerate or verify every committed sovereign-osctl(1) roff artifact.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE="${1:-build}"

command -v pandoc >/dev/null 2>&1 || {
  echo "error: pandoc is required to regenerate the man-page suite" >&2
  exit 1
}

case "${MODE}" in build|check) ;; *)
  echo "usage: $0 [build|check]" >&2
  exit 2
esac

status=0
shopt -s nullglob
sources=("${ROOT}"/docs/man/sovereign-osctl*.1.md)
(("${#sources[@]}" >= 8)) || {
  echo "error: expected the sovereign-osctl main page plus seven topic pages" >&2
  exit 1
}

for source in "${sources[@]}"; do
  target="${source%.md}"
  tmp="$(mktemp)"
  trap 'rm -f "${tmp}"' EXIT
  pandoc -s -t man "${source}" -o "${tmp}"

  if [ "${MODE}" = build ]; then
    install -m 644 "${tmp}" "${target}"
    echo "generated ${target}"
  elif ! cmp -s "${tmp}" "${target}"; then
    echo "error: ${target} is stale; run make man" >&2
    diff -u "${target}" "${tmp}" || true
    status=1
  else
    echo "current ${target}"
  fi
  rm -f "${tmp}"
  trap - EXIT
done

exit "${status}"
