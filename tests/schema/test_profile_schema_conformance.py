"""Layer 1 — profile YAML schema-conformance against schemas/profile.schema.yaml."""

from __future__ import annotations

import pathlib

import pytest

try:
    import yaml
except ImportError:
    pytest.skip("python3-yaml not installed", allow_module_level=True)

try:
    import jsonschema
except ImportError:
    pytest.skip("python3-jsonschema not installed", allow_module_level=True)


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PROFILE_DIR = REPO_ROOT / "profiles"
SCHEMA_FILE = REPO_ROOT / "schemas" / "profile.schema.yaml"


def _load_yaml(path: pathlib.Path):
    with path.open() as f:
        return yaml.safe_load(f)


def _all_profile_files() -> list[pathlib.Path]:
    return sorted(PROFILE_DIR.glob("*.yaml"))


@pytest.fixture(scope="module")
def schema():
    return _load_yaml(SCHEMA_FILE)


@pytest.mark.parametrize("profile_file", _all_profile_files(), ids=lambda p: p.stem)
def test_profile_validates_against_schema(profile_file, schema):
    """Every profiles/*.yaml must validate against schemas/profile.schema.yaml."""
    instance = _load_yaml(profile_file)
    jsonschema.Draft202012Validator(schema).validate(instance)


@pytest.mark.parametrize("profile_file", _all_profile_files(), ids=lambda p: p.stem)
def test_profile_id_matches_filename(profile_file):
    """The identity.id field must match the YAML filename (without .yaml)."""
    instance = _load_yaml(profile_file)
    assert instance["identity"]["id"] == profile_file.stem


@pytest.mark.parametrize("profile_file", _all_profile_files(), ids=lambda p: p.stem)
def test_profile_required_features_non_empty_when_required_block_present(profile_file):
    """If the profile declares CPU required features, the list must not be empty."""
    instance = _load_yaml(profile_file)
    features = (
        (instance.get("hardware") or {})
        .get("cpu", {})
        .get("features", {})
        .get("required")
    )
    if features is not None:
        assert isinstance(features, list)
        assert len(features) > 0, "required features list must be non-empty"


def test_sain01_zfs_context_sync_always():
    """sain-01 MUST declare sync=always on tank/context (race-free state fabric)."""
    sain01 = _load_yaml(PROFILE_DIR / "sain-01.yaml")
    datasets = sain01["hardware"]["storage"]["datasets"]
    ctx = next((d for d in datasets if "context" in d.get("name", "")), None)
    assert ctx is not None, "sain-01 must declare a tank/context dataset"
    assert ctx.get("sync") == "always", "tank/context must have sync=always"


def test_sain01_vfio_companion_present():
    """All role=vfio GPUs must declare vfio_companion."""
    sain01 = _load_yaml(PROFILE_DIR / "sain-01.yaml")
    gpus = sain01["hardware"]["gpu"]
    vfio_gpus = [g for g in gpus if g.get("role") == "vfio"]
    assert vfio_gpus, "sain-01 must declare at least one vfio GPU"
    for g in vfio_gpus:
        assert g.get("vfio_companion"), f"GPU {g.get('model')} missing vfio_companion"


def test_sain01_m2_2_empty_constraint_declared():
    """sain-01 must declare the m2_2_empty PCIe blocker (ASUS ProArt X870E)."""
    sain01 = _load_yaml(PROFILE_DIR / "sain-01.yaml")
    constraints = sain01["hardware"]["motherboard"]["pcie_constraints"]
    assert any(
        c.get("check") == "m2_2_empty" and c.get("severity") == "blocker"
        for c in constraints
    ), "sain-01 must declare m2_2_empty as blocker"
