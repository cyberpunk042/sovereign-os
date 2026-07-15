#!/usr/bin/env bash
# Build a deterministic source-release bundle from the current Git commit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${1:-${ROOT}/dist}"

case "${OUT_DIR}" in
  ""|/|.|..) echo "error: unsafe output directory: ${OUT_DIR:-<empty>}" >&2; exit 2 ;;
esac

[ -r "${ROOT}/VERSION" ] || {
  echo "error: canonical VERSION file is missing" >&2
  exit 1
}
IFS= read -r version < "${ROOT}/VERSION"
release_tag="${RELEASE_TAG:-v${version}}"
bash "${ROOT}/scripts/release/validate-release-tag.sh" "${release_tag}"

git -C "${ROOT}" diff --quiet || {
  echo "error: tracked working-tree changes would not be included in the release" >&2
  exit 1
}
git -C "${ROOT}" diff --cached --quiet || {
  echo "error: staged changes would not be included in the release" >&2
  exit 1
}

commit="$(git -C "${ROOT}" rev-parse HEAD)"
epoch="${SOURCE_DATE_EPOCH:-$(git -C "${ROOT}" show -s --format=%ct "${commit}")}"
if [[ ! "${epoch}" =~ ^[0-9]+$ ]]; then
  echo "error: SOURCE_DATE_EPOCH must be an integer, got: ${epoch}" >&2
  exit 1
fi

repository="${SOVEREIGN_OS_REPOSITORY:-https://github.com/cyberpunk042/sovereign-os}"
base="sovereign-os-${version}"
archive="${OUT_DIR}/${base}.tar.gz"
sbom="${OUT_DIR}/${base}.spdx.json"
provenance="${OUT_DIR}/${base}.provenance.json"

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}"

git -C "${ROOT}" archive   --format=tar   --prefix="${base}/"   "${commit}"   | gzip -n -9 > "${archive}"

python3 "${ROOT}/scripts/release/generate-release-metadata.py"   --version "${version}"   --commit "${commit}"   --epoch "${epoch}"   --repository "${repository}"   --artifact "${archive}"   --cargo-lock "${ROOT}/Cargo.lock"   --sbom "${sbom}"   --provenance "${provenance}"

(
  cd "${OUT_DIR}"
  sha256sum     "$(basename "${archive}")"     "$(basename "${sbom}")"     "$(basename "${provenance}")"     > SHA256SUMS
)

printf 'release bundle: %s\n' "${OUT_DIR}"
printf '  version:      %s\n' "${version}"
printf '  commit:       %s\n' "${commit}"
printf '  source epoch: %s\n' "${epoch}"
printf '  artifact:     %s\n' "${archive}"
printf '  SBOM:         %s\n' "${sbom}"
printf '  provenance:   %s\n' "${provenance}"
printf '  checksums:    %s/SHA256SUMS\n' "${OUT_DIR}"
