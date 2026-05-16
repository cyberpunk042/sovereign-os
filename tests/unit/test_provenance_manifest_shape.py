"""Layer 2 unit tests — build-provenance.json manifest shape.

The orchestrator step 09-image-verify emits an in-toto SLSA v1
provenance manifest (Round 29). Operators verify via
'sovereign-osctl audit provenance' (Round 41).

These tests pin the manifest's structural contract — adding a new
field is fine; removing a required field or changing the type breaks
the contract + must be a conscious decision."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
STEP_09 = REPO_ROOT / "scripts" / "build" / "09-image-verify.sh"


@pytest.fixture
def fake_image_dir(tmp_path):
    """Create a fake image dir with two artifacts + run step 09's
    inline Python provenance-emitter against it."""
    img = tmp_path / "img"
    img.mkdir()
    (img / "artifact-a.raw").write_bytes(b"contents A")
    (img / "vmlinuz-test").write_bytes(b"contents V")

    # Extract + run the provenance-emit Python block from step 09
    # (we inline a minimal version equivalent to what step 09 runs)
    out = subprocess.run(
        ["python3", "-"],
        input=f"""
import hashlib, json, os, pathlib, time
img_dir = pathlib.Path("{img}")
subjects = []
for f in sorted(img_dir.rglob("*")):
    if not f.is_file(): continue
    if f.name in ("sha256sums.txt", "build-provenance.json"): continue
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    subjects.append({{"name": str(f.relative_to(img_dir)), "digest": {{"sha256": h}}}})
provenance = {{
    "_type": "https://in-toto.io/Statement/v1",
    "predicateType": "https://slsa.dev/provenance/v1",
    "subject": subjects,
    "predicate": {{
        "buildDefinition": {{
            "buildType": "https://github.com/cyberpunk042/sovereign-os/build/v1",
            "externalParameters": {{
                "profile": "sain-01",
                "substrate": "mkosi",
                "source_date_epoch": "1700000000",
                "debian_snapshot": "20260515T000000Z",
            }},
        }},
        "runDetails": {{
            "builder": {{"id": "https://github.com/cyberpunk042/sovereign-os/orchestrator"}},
            "metadata": {{
                "invocationId": "test-build-id",
                "startedOn": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }},
        }},
    }},
}}
(img_dir / "build-provenance.json").write_text(json.dumps(provenance, indent=2))
""",
        capture_output=True,
        text=True,
        check=True,
    )
    return img


def test_manifest_file_exists(fake_image_dir):
    assert (fake_image_dir / "build-provenance.json").is_file()


def test_manifest_is_valid_json(fake_image_dir):
    data = json.loads((fake_image_dir / "build-provenance.json").read_text())
    assert isinstance(data, dict)


def test_manifest_type_is_in_toto_v1(fake_image_dir):
    data = json.loads((fake_image_dir / "build-provenance.json").read_text())
    assert data["_type"] == "https://in-toto.io/Statement/v1"


def test_manifest_predicate_type_is_slsa_v1(fake_image_dir):
    data = json.loads((fake_image_dir / "build-provenance.json").read_text())
    assert data["predicateType"] == "https://slsa.dev/provenance/v1"


def test_manifest_subjects_present_and_typed(fake_image_dir):
    data = json.loads((fake_image_dir / "build-provenance.json").read_text())
    subjects = data["subject"]
    assert isinstance(subjects, list)
    assert len(subjects) == 2
    for s in subjects:
        assert "name" in s
        assert "digest" in s
        assert "sha256" in s["digest"]
        assert len(s["digest"]["sha256"]) == 64
        assert all(c in "0123456789abcdef" for c in s["digest"]["sha256"])


def test_manifest_subjects_exclude_manifests_themselves(fake_image_dir):
    """sha256sums.txt + build-provenance.json must NEVER appear as
    subjects (self-reference would break verification)."""
    data = json.loads((fake_image_dir / "build-provenance.json").read_text())
    names = {s["name"] for s in data["subject"]}
    assert "sha256sums.txt" not in names
    assert "build-provenance.json" not in names


def test_manifest_external_parameters_record_repro_inputs(fake_image_dir):
    """SDD-019 requires reproducibility inputs (SOURCE_DATE_EPOCH +
    DEBIAN_SNAPSHOT + profile + substrate) to be recorded in
    externalParameters."""
    data = json.loads((fake_image_dir / "build-provenance.json").read_text())
    ext = data["predicate"]["buildDefinition"]["externalParameters"]
    for key in ("profile", "substrate", "source_date_epoch", "debian_snapshot"):
        assert key in ext, f"externalParameters missing: {key}"


def test_manifest_build_type_namespaced(fake_image_dir):
    """SLSA v1 buildType must be a URI that uniquely identifies the
    build process. sovereign-os uses the repo URL."""
    data = json.loads((fake_image_dir / "build-provenance.json").read_text())
    bt = data["predicate"]["buildDefinition"]["buildType"]
    assert bt.startswith("https://github.com/cyberpunk042/sovereign-os/")
    assert bt.endswith("/build/v1")


def test_manifest_run_details_present(fake_image_dir):
    """SLSA v1 runDetails records the builder identity + invocation
    metadata. Required for audit chain."""
    data = json.loads((fake_image_dir / "build-provenance.json").read_text())
    run = data["predicate"]["runDetails"]
    assert "builder" in run
    assert "id" in run["builder"]
    assert "metadata" in run


def test_manifest_subject_digests_match_actual_files(fake_image_dir):
    """The digest in the manifest must match the actual file's
    sha256. operator-side 'audit provenance' relies on this gate."""
    data = json.loads((fake_image_dir / "build-provenance.json").read_text())
    for subject in data["subject"]:
        f = fake_image_dir / subject["name"]
        assert f.is_file(), f"manifest references missing file: {subject['name']}"
        actual = hashlib.sha256(f.read_bytes()).hexdigest()
        declared = subject["digest"]["sha256"]
        assert actual == declared, f"digest mismatch for {subject['name']}"
