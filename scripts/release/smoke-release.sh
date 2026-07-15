#!/usr/bin/env bash
# Verify a release bundle as a consumer would, including a staged install.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST="${1:-${ROOT}/dist}"

[ -d "${DIST}" ] || { echo "error: release directory not found: ${DIST}" >&2; exit 1; }
[ -r "${ROOT}/VERSION" ] || { echo "error: VERSION missing" >&2; exit 1; }
IFS= read -r version < "${ROOT}/VERSION"
base="sovereign-os-${version}"
archive="${DIST}/${base}.tar.gz"
sbom="${DIST}/${base}.spdx.json"
provenance="${DIST}/${base}.provenance.json"
checksums="${DIST}/SHA256SUMS"

for path in "${archive}" "${sbom}" "${provenance}" "${checksums}"; do
  [ -s "${path}" ] || { echo "error: missing or empty release artifact: ${path}" >&2; exit 1; }
done

(
  cd "${DIST}"
  sha256sum -c SHA256SUMS
)

python3 - "${archive}" "${sbom}" "${provenance}" "${version}" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
import tarfile

archive, sbom_path, provenance_path = map(Path, sys.argv[1:4])
version = sys.argv[4]

def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()

with tarfile.open(archive, "r:gz") as bundle:
    expected_root = f"sovereign-os-{version}"
    names = bundle.getnames()
    if not names:
        raise SystemExit("source archive is empty")
    for name in names:
        parts = Path(name).parts
        if not parts or parts[0] != expected_root or name.startswith("/") or ".." in parts:
            raise SystemExit(f"unsafe archive member: {name}")

sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
assert sbom["spdxVersion"] == "SPDX-2.3"
assert sbom["dataLicense"] == "CC0-1.0"
assert sbom["name"] == f"sovereign-os-{version}-source"
root = next(p for p in sbom["packages"] if p["name"] == "sovereign-os")
assert root["versionInfo"] == version
assert len(sbom["packages"]) > 100, "Cargo.lock dependency inventory unexpectedly small"

provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
assert provenance["_type"] == "https://in-toto.io/Statement/v1"
assert provenance["predicateType"] == "https://slsa.dev/provenance/v1"
subjects = {item["name"]: item["digest"]["sha256"] for item in provenance["subject"]}
assert subjects[archive.name] == digest(archive)
assert subjects[sbom_path.name] == digest(sbom_path)
assert provenance["predicate"]["buildDefinition"]["externalParameters"]["version"] == version
PY

work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT
tar -xzf "${archive}" -C "${work}"
source_root="${work}/${base}"

[ "$(<"${source_root}/VERSION")" = "${version}" ] || {
  echo "error: archived VERSION does not match ${version}" >&2
  exit 1
}

bash -n   "${source_root}/scripts/sovereign-osctl"   "${source_root}/scripts/docs/build-sovereign-osctl-manpage.sh"   "${source_root}/scripts/release/build-release.sh"   "${source_root}/scripts/release/smoke-release.sh"   "${source_root}/scripts/release/validate-release-tag.sh"
python3 -m py_compile "${source_root}/scripts/release/generate-release-metadata.py"

stage="${work}/stage"
make -C "${source_root}" install DESTDIR="${stage}" PREFIX=/usr >/dev/null
installed_root="${stage}/usr"
installed_lib="${installed_root}/lib/sovereign-os"
installed_cli="${installed_root}/bin/sovereign-osctl"

SOVEREIGN_OS_LIB="${installed_lib}" "${installed_cli}" version --json   > "${work}/version.json"
python3 - "${work}/version.json" "${version}" <<'PY'
import json
from pathlib import Path
import sys

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["sovereign_osctl_version"] == sys.argv[2]
PY

man_count="$(find "${installed_root}/share/man/man1" -maxdepth 1 -name 'sovereign-osctl*.1' | wc -l)"
[ "${man_count}" -ge 8 ] || {
  echo "error: staged release installed only ${man_count} sovereign-osctl manpages" >&2
  exit 1
}
bash -n "${installed_root}/share/bash-completion/completions/sovereign-osctl"
[ -s "${installed_root}/share/zsh/site-functions/_sovereign-osctl" ]
[ -s "${installed_root}/share/fish/vendor_completions.d/sovereign-osctl.fish" ]

make -C "${source_root}" uninstall DESTDIR="${stage}" PREFIX=/usr >/dev/null
[ ! -e "${installed_cli}" ] || { echo "error: uninstall left ${installed_cli}" >&2; exit 1; }
[ ! -e "${installed_lib}" ] || { echo "error: uninstall left ${installed_lib}" >&2; exit 1; }

printf 'release smoke passed: sovereign-os %s\n' "${version}"
