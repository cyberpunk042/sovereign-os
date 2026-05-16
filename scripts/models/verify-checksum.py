#!/usr/bin/env python3
"""scripts/models/verify-checksum.py — verify a model artifact's
sha256 against its manifest declaration (R190).

Closes SDD-019 T-3 partially: full `selfdefctl models fetch` deferred
to cycle 3 (needs HTTP + token plumbing). This round addresses the
VERIFY half — operators who downloaded an artifact manually (e.g.
`huggingface-cli download`) can now confirm integrity against the
manifest's `artifact_sha256` field.

Use:

  $ python3 scripts/models/verify-checksum.py \
      --manifest /etc/selfdef/models/bitnet-2b/model.toml \
      --artifact /mnt/vault/models/bitnet-2b/ggml-model-i2_s.gguf

  ✓ /mnt/vault/models/bitnet-2b/ggml-model-i2_s.gguf
    expected: 3a7b...d3
    actual:   3a7b...d3 (match)

Exit codes:
  0  artifact sha256 matches manifest
  1  digest mismatch (operator action needed)
  2  manifest missing artifact_sha256 (cannot verify)
  3  argument/IO error
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def parse_manifest_sha256(manifest_path: Path) -> str | None:
    """Tiny TOML reader for the SD-R34 model.toml shape — same pattern
    as scripts/models/selfdef-models.py. Returns the artifact_sha256
    value or None when absent."""
    if not manifest_path.exists():
        return None
    section: str | None = None
    for raw in manifest_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip(",")
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        if section == "model" and k == "artifact_sha256":
            return v
    return None


def compute_sha256(path: Path) -> str:
    """Stream-read so we don't load multi-GiB artifacts into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(
        description="Verify a model artifact's sha256 against its manifest (R190)"
    )
    p.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path to the model.toml manifest (selfdef SD-R34 format)",
    )
    p.add_argument(
        "--artifact",
        type=Path,
        required=True,
        help="Path to the downloaded artifact (e.g. model.gguf)",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the human-readable output; rely on exit code only",
    )
    args = p.parse_args()

    if not args.manifest.exists():
        sys.stderr.write(f"ERROR: manifest not found: {args.manifest}\n")
        return 3
    if not args.artifact.exists():
        sys.stderr.write(f"ERROR: artifact not found: {args.artifact}\n")
        return 3
    if not args.artifact.is_file():
        sys.stderr.write(f"ERROR: artifact is not a regular file: {args.artifact}\n")
        return 3

    expected = parse_manifest_sha256(args.manifest)
    if not expected:
        if not args.quiet:
            sys.stderr.write(
                f"WARN  R190: manifest {args.manifest} has no artifact_sha256;"
                " cannot verify (re-pin the manifest before deploying)\n"
            )
        return 2

    actual = compute_sha256(args.artifact)
    matched = actual == expected
    if not args.quiet:
        marker = "✓" if matched else "✗"
        print(f"{marker} {args.artifact}")
        print(f"  expected: {expected}")
        print(f"  actual:   {actual}" + (" (match)" if matched else " (MISMATCH)"))
    return 0 if matched else 1


if __name__ == "__main__":
    sys.exit(main())
