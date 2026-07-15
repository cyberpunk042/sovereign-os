#!/usr/bin/env python3
"""Generate deterministic SPDX and in-toto metadata for a source release."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tomllib
from urllib.parse import quote


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def spdx_id(name: str, version: str, source: str) -> str:
    identity = f"{name}\0{version}\0{source}".encode()
    suffix = hashlib.sha256(identity).hexdigest()[:16]
    safe_name = "".join(char if char.isalnum() else "-" for char in name).strip("-")
    return f"SPDXRef-Cargo-{safe_name}-{suffix}"


def timestamp(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cargo_packages(lock_path: Path) -> list[dict[str, object]]:
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    packages: list[dict[str, object]] = []
    for package in sorted(
        lock.get("package", []),
        key=lambda item: (
            str(item.get("name", "")),
            str(item.get("version", "")),
            str(item.get("source", "")),
        ),
    ):
        name = str(package["name"])
        version = str(package["version"])
        source = str(package.get("source", "workspace"))
        entry: dict[str, object] = {
            "SPDXID": spdx_id(name, version, source),
            "name": name,
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "copyrightText": "NOASSERTION",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": (
                        f"pkg:cargo/{quote(name, safe='')}@{quote(version, safe='')}"
                    ),
                }
            ],
        }
        checksum = package.get("checksum")
        if checksum:
            entry["checksums"] = [
                {"algorithm": "SHA256", "checksumValue": str(checksum)}
            ]
        packages.append(entry)
    return packages


def build_spdx(
    version: str,
    commit: str,
    epoch: int,
    repository: str,
    lock_path: Path,
) -> dict[str, object]:
    root_id = "SPDXRef-Package-sovereign-os"
    dependencies = cargo_packages(lock_path)
    root_package: dict[str, object] = {
        "SPDXID": root_id,
        "name": "sovereign-os",
        "versionInfo": version,
        "downloadLocation": f"git+{repository}.git@{commit}",
        "filesAnalyzed": False,
        "licenseConcluded": "AGPL-3.0-or-later",
        "licenseDeclared": "AGPL-3.0-or-later",
        "copyrightText": "NOASSERTION",
        "externalRefs": [
            {
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": f"pkg:generic/sovereign-os@{quote(version, safe='')}",
            },
            {
                "referenceCategory": "OTHER",
                "referenceType": "vcs",
                "referenceLocator": f"git+{repository}.git@{commit}",
            },
        ],
    }
    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": root_id,
        }
    ]
    relationships.extend(
        {
            "spdxElementId": root_id,
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": str(package["SPDXID"]),
        }
        for package in dependencies
    )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"sovereign-os-{version}-source",
        "documentNamespace": (
            f"{repository}/releases/tag/v{version}/spdx/{commit}"
        ),
        "creationInfo": {
            "created": timestamp(epoch),
            "creators": ["Tool: sovereign-os/scripts/release/generate-release-metadata.py"],
            "licenseListVersion": "3.25",
        },
        "documentDescribes": [root_id],
        "packages": [root_package, *dependencies],
        "relationships": relationships,
    }


def build_provenance(
    version: str,
    commit: str,
    epoch: int,
    repository: str,
    artifact: Path,
    sbom: Path,
) -> dict[str, object]:
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": artifact.name, "digest": {"sha256": sha256(artifact)}},
            {"name": sbom.name, "digest": {"sha256": sha256(sbom)}},
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": f"{repository}/.github/workflows/release.yml@v1",
                "externalParameters": {
                    "version": version,
                    "tag": f"v{version}",
                    "sourceDateEpoch": epoch,
                },
                "internalParameters": {},
                "resolvedDependencies": [
                    {
                        "uri": f"git+{repository}.git@{commit}",
                        "digest": {"gitCommit": commit},
                    }
                ],
            },
            "runDetails": {
                "builder": {
                    "id": f"{repository}/.github/workflows/release.yml@refs/tags/v{version}"
                },
                "metadata": {"invocationId": commit},
            },
        },
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--version", required=True)
    result.add_argument("--commit", required=True)
    result.add_argument("--epoch", required=True, type=int)
    result.add_argument("--repository", required=True)
    result.add_argument("--artifact", required=True, type=Path)
    result.add_argument("--cargo-lock", required=True, type=Path)
    result.add_argument("--sbom", required=True, type=Path)
    result.add_argument("--provenance", required=True, type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    if not args.artifact.is_file():
        raise SystemExit(f"artifact not found: {args.artifact}")
    if not args.cargo_lock.is_file():
        raise SystemExit(f"Cargo.lock not found: {args.cargo_lock}")
    write_json(
        args.sbom,
        build_spdx(
            args.version,
            args.commit,
            args.epoch,
            args.repository,
            args.cargo_lock,
        ),
    )
    write_json(
        args.provenance,
        build_provenance(
            args.version,
            args.commit,
            args.epoch,
            args.repository,
            args.artifact,
            args.sbom,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
