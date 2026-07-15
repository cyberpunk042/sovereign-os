#!/usr/bin/env bash
# Exercise the release surface after a real install into a disposable Debian system.
set -euo pipefail

ROOT="${1:-$(pwd)}"
PREFIX="/usr/local"
MAN_ROOT="${PREFIX}/share/man"
MAN1="${MAN_ROOT}/man1"
BASH_COMPLETION="${PREFIX}/share/bash-completion/completions/sovereign-osctl"
ZSH_COMPLETION="${PREFIX}/share/zsh/site-functions/_sovereign-osctl"
FISH_COMPLETION="${PREFIX}/share/fish/vendor_completions.d/sovereign-osctl.fish"
CLI="${PREFIX}/bin/sovereign-osctl"
LIB="${PREFIX}/lib/sovereign-os"

if [ "${EUID}" -ne 0 ]; then
  echo "error: installed-system smoke must run as root inside a disposable container" >&2
  exit 1
fi
for command in make python3 man mandb whatis bash zsh fish sha256sum; do
  command -v "${command}" >/dev/null || {
    echo "error: required command is unavailable: ${command}" >&2
    exit 1
  }
done
for path in "${CLI}" "${LIB}" "${BASH_COMPLETION}" "${ZSH_COMPLETION}" "${FISH_COMPLETION}"; do
  [ ! -e "${path}" ] || {
    echo "error: refusing to overwrite pre-existing path in smoke container: ${path}" >&2
    exit 1
  }
done

work="$(mktemp -d)"
cleanup() {
  make -C "${ROOT}" uninstall PREFIX="${PREFIX}" >/dev/null 2>&1 || true
  rm -rf "${work}"
}
trap cleanup EXIT

installed_manifest() {
  {
    find "${LIB}" -type f -print
    find "${MAN1}" -maxdepth 1 -type f -name 'sovereign-osctl*.1' -print
    printf '%s\n' "${CLI}" "${BASH_COMPLETION}" "${ZSH_COMPLETION}" "${FISH_COMPLETION}"
  } | LC_ALL=C sort -u | while IFS= read -r path; do
    [ -f "${path}" ] || {
      echo "error: installed manifest path is missing: ${path}" >&2
      return 1
    }
    stat -c '%a %U:%G %n' "${path}"
    sha256sum "${path}"
  done
}

make -C "${ROOT}" install PREFIX="${PREFIX}" >/dev/null
installed_manifest > "${work}/first.manifest"

version="$(<"${ROOT}/VERSION")"
sovereign-osctl version --json > "${work}/version.json"
python3 - "${work}/version.json" "${version}" <<'PY'
import json
from pathlib import Path
import sys

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["sovereign_osctl_version"] == sys.argv[2]
PY

# Build the real man-db cache, then prove lookup, whatis parsing, and rendering.
mandb --create --quiet "${MAN_ROOT}"
page="$(man --where --manpath "${MAN_ROOT}" sovereign-osctl)"
[ "${page}" = "${MAN1}/sovereign-osctl.1" ] || {
  echo "error: man resolved an unexpected page: ${page}" >&2
  exit 1
}
whatis --manpath "${MAN_ROOT}" sovereign-osctl | grep -Eq '^sovereign-osctl \(1\)'
MANPAGER=cat PAGER=cat man --manpath "${MAN_ROOT}" sovereign-osctl > "${work}/manual.txt"
grep -q 'sovereign-osctl' "${work}/manual.txt"

# Ask each shell's native loader to discover and use the installed completion.
printf 'checking completion syntax\n'
zsh -n "${ZSH_COMPLETION}"
fish -n "${FISH_COMPLETION}"
printf 'checking Bash completion discovery\n'
bash --noprofile --norc -c '
  set -euo pipefail
  source /usr/share/bash-completion/bash_completion
  loader_status=0
  _completion_loader sovereign-osctl || loader_status=$?
  [[ ${loader_status} -eq 0 || ${loader_status} -eq 124 ]]
  complete -p sovereign-osctl | grep -q "_sovereign_osctl_complete"
  COMP_WORDS=(sovereign-osctl he)
  COMP_CWORD=1
  _sovereign_osctl_complete
  printf "%s\n" "${COMPREPLY[@]}" | grep -Fxq help
'
printf 'checking Zsh completion discovery\n'
zsh -f -c '
  set -eu
  fpath=(/usr/local/share/zsh/site-functions $fpath)
  autoload -Uz compinit
  compinit -D
  [[ "${_comps[sovereign-osctl]}" == "_sovereign-osctl" ]]
  autoload -Uz _sovereign-osctl
  autoload +X _sovereign-osctl
  whence -w _sovereign-osctl | grep -q "function"
'
printf 'checking Fish completion discovery\n'
fish -c '
  printf "fish completion paths:\\n"
  printf "  %s\\n" $fish_complete_path
  printf "fish candidates:\\n"
  complete -C "sovereign-osctl he"
' > "${work}/fish-completion.txt"
cat -- "${work}/fish-completion.txt"
grep -Eq '^help([[:space:]]|$)' "${work}/fish-completion.txt"
printf 'all completion loaders passed\\n'

# A second install must be byte-for-byte and mode-for-mode identical.
make -C "${ROOT}" install PREFIX="${PREFIX}" >/dev/null
installed_manifest > "${work}/second.manifest"
diff -u "${work}/first.manifest" "${work}/second.manifest"

make -C "${ROOT}" uninstall PREFIX="${PREFIX}" >/dev/null
for path in "${CLI}" "${LIB}" "${BASH_COMPLETION}" "${ZSH_COMPLETION}" "${FISH_COMPLETION}"; do
  [ ! -e "${path}" ] || {
    echo "error: uninstall left installed path: ${path}" >&2
    exit 1
  }
done
if find "${MAN1}" -maxdepth 1 -type f -name 'sovereign-osctl*.1' -print -quit | grep -q .; then
  echo "error: uninstall left sovereign-osctl manual pages" >&2
  exit 1
fi
mandb --quiet "${MAN_ROOT}"
if man --where --manpath "${MAN_ROOT}" sovereign-osctl >/dev/null 2>&1; then
  echo "error: man still resolves sovereign-osctl after uninstall" >&2
  exit 1
fi

printf 'clean installed-system smoke passed: sovereign-os %s\n' "${version}"
