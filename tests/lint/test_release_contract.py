"""Contracts for reproducible, attestable sovereign-os releases."""

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
VERSION = ROOT / "VERSION"
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
RELEASE_DIR = ROOT / "scripts" / "release"
DOC = ROOT / "docs" / "release.md"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing release artifact: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def test_canonical_version_is_release_tag_compatible():
    version = _read(VERSION).strip()
    assert re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?",
        version,
    )


def test_release_workflow_has_read_only_validation_and_tag_only_publication():
    workflow = _read(WORKFLOW)
    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "tags:" in workflow and "'v*'" in workflow
    assert workflow.count("contents: write") == 1
    assert "contents: read" in workflow
    assert "id-token: write" in workflow
    assert "attestations: write" in workflow
    assert "if: startsWith(github.ref, 'refs/tags/v')" in workflow
    assert "--require-git-tag" in workflow
    assert "--verify-tag" in workflow
    assert 'version="${GITHUB_REF_NAME#v}"' in workflow
    assert "gh release create" in workflow

    uses = re.findall(r"^\s*uses:\s*[^@\s]+@([^\s]+)", workflow, re.MULTILINE)
    assert uses
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in uses), uses


def test_release_bundle_is_rebuilt_and_smoked_before_publication():
    workflow = _read(WORKFLOW)
    assert "build-release.sh dist" in workflow
    assert "build-release.sh dist-rebuild" in workflow
    assert "diff -qr dist dist-rebuild" in workflow
    assert "smoke-release.sh dist" in workflow
    assert workflow.index("smoke-release.sh dist") < workflow.index("gh release create")
    assert "subject-path:" in workflow
    assert "sbom-path:" in workflow


def test_release_scripts_are_syntax_valid_and_fail_closed():
    shell_scripts = (
        RELEASE_DIR / "validate-release-tag.sh",
        RELEASE_DIR / "build-release.sh",
        RELEASE_DIR / "smoke-release.sh",
    )
    result = subprocess.run(
        ["bash", "-n", *(str(path) for path in shell_scripts)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(RELEASE_DIR / "generate-release-metadata.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    validator = _read(RELEASE_DIR / "validate-release-tag.sh")
    builder = _read(RELEASE_DIR / "build-release.sh")
    smoke = _read(RELEASE_DIR / "smoke-release.sh")
    assert 'if [ "${tag}" != "v${version}" ]' in validator
    assert "tracked working-tree changes" in builder
    assert "SOURCE_DATE_EPOCH" in builder
    assert "gzip -n -9" in builder
    assert "sha256sum -c SHA256SUMS" in smoke
    assert "unsafe archive member" in smoke
    assert "make -C" in smoke and "install" in smoke and "uninstall" in smoke


def test_operator_release_documentation_covers_trust_verification():
    doc = _read(DOC)
    for required in (
        "signed annotated",
        "SHA256SUMS",
        "SPDX 2.3",
        "in-toto/SLSA",
        "gh attestation verify",
        "scripts/release/smoke-release.sh",
        "Rust workspace package versions",
    ):
        assert required in doc
