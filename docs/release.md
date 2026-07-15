# Release process

The root `VERSION` file is the canonical version for the installed operator
surface, release tags, source bundles, manual headers, and
`sovereign-osctl version`. During Stage 2, this is intentionally distinct
from unpublished Rust workspace package versions. A future Stage-3 release
decision may unify those version domains.

## Creating a release

1. Start from a green commit on `main`.
2. Update `VERSION`, the changelog, and versioned manual headers in one pull
   request. Run `make man` when the version changes.
3. Create a tag whose name is exactly `v$(cat VERSION)`. A signed annotated
   tag is recommended:

   ```bash
   version="$(<VERSION)"
   git tag -s "v${version}" -m "sovereign-os v${version}"
   git push origin "v${version}"
   ```

4. The `release` workflow validates that the tag points to the checked-out
   commit and exactly matches `VERSION`. It builds the source bundle twice,
   rejects byte drift, runs the staged-install smoke test, creates GitHub
   artifact attestations, and publishes the assets.

Manual workflow dispatch and release-related pull requests run packaging and
smoke validation but never attest or publish.

Versions below `1.0.0` are published as GitHub prereleases, matching the
current pre-Stage-3 lifecycle.

## Release assets

A release contains:

- `sovereign-os-<version>.tar.gz`: deterministic archive of tracked source at
  the tagged commit.
- `sovereign-os-<version>.spdx.json`: SPDX 2.3 source SBOM containing the root
  package and the complete Cargo.lock package inventory.
- `sovereign-os-<version>.provenance.json`: deterministic in-toto/SLSA
  provenance statement tying the archive and SBOM to the commit and build
  parameters.
- `SHA256SUMS`: checksums for the archive, SBOM, and provenance statement.
- GitHub-hosted, OIDC-signed build-provenance and SBOM attestations.

The deterministic provenance file is useful offline. The GitHub attestation is
the cryptographically signed claim and should be used for trust verification.

## Consumer verification

After downloading every release asset:

```bash
sha256sum -c SHA256SUMS
gh attestation verify "sovereign-os-<version>.tar.gz" \
  --repo cyberpunk042/sovereign-os
```

To reproduce the local bundle from the tagged checkout:

```bash
export SOURCE_DATE_EPOCH="$(git show -s --format=%ct HEAD)"
export RELEASE_TAG="$(git describe --tags --exact-match)"
bash scripts/release/build-release.sh dist
bash scripts/release/smoke-release.sh dist
```

The smoke contract verifies checksum and metadata integrity, archive path
safety, script syntax, a staged installation, the installed CLI version, all
manual pages, shell-completion artifacts, and uninstall symmetry.
