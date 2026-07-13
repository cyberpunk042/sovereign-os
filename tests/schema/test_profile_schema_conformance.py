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
    """VFIO sandbox is OPT-IN (SDD-993 + operator directive 2026-07-13: "not in
    a VM by default"). The default posture is host-resident/bare-metal, so no GPU
    carries role=vfio by default — but the opt-in machinery must be READY: the
    4090 (the sandboxable eGPU) must declare `vfio_companion` so that flipping it
    to `role: vfio` binds cleanly. And any GPU that IS opted into vfio must carry
    a companion."""
    sain01 = _load_yaml(PROFILE_DIR / "sain-01.yaml")
    gpus = sain01["hardware"]["gpu"]
    # opt-in readiness: the 4090 sandbox candidate declares its companion
    egpu = next((g for g in gpus if g.get("model") == "rtx-4090"), None)
    assert egpu is not None, "sain-01 must declare the RTX 4090 (OcuLink eGPU)"
    assert egpu.get("vfio_companion"), (
        "the RTX 4090 must declare vfio_companion so the opt-in VFIO sandbox "
        "binds cleanly when enabled (role: vfio)"
    )
    # every GPU actually opted into vfio must carry a companion
    for g in gpus:
        if g.get("role") == "vfio":
            assert g.get("vfio_companion"), f"GPU {g.get('model')} missing vfio_companion"


def test_sain01_m2_2_constraint_declared():
    """sain-01 must declare an M.2_2 PCIe constraint (ASUS ProArt X870E).

    SDD-993: the 4090 moved to an OcuLink eGPU, so M.2_2 now HOSTS the
    OcuLink-to-M.2 adapter (the old must-remain-empty x8/x8 bifurcation rule is
    retired — one internal GPU runs full x16). The profile must still DECLARE an
    M.2_2 constraint — now `m2_2_oculink_egpu` (info), not `m2_2_empty` (blocker).
    """
    sain01 = _load_yaml(PROFILE_DIR / "sain-01.yaml")
    constraints = sain01["hardware"]["motherboard"]["pcie_constraints"]
    assert any(
        c.get("check") == "m2_2_oculink_egpu"
        for c in constraints
    ), "sain-01 must declare the m2_2_oculink_egpu constraint (SDD-993)"
