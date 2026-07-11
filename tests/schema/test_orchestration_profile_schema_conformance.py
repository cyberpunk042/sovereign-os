"""Layer 1 — orchestration-profile YAML schema conformance.

Every `profiles/orchestration/*.yaml` MUST validate against
`schemas/orchestration-profile.schema.yaml`. This is the SEPARATE
orchestration-intent family surfaced by the D-21 LM Orchestration panel —
DISTINCT from the master-spec §18 runtime load-balancing profiles
(profiles/runtime/, verbatim-locked to exactly 3).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""

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
ORCH_DIR = REPO_ROOT / "profiles" / "orchestration"
SCHEMA_FILE = REPO_ROOT / "schemas" / "orchestration-profile.schema.yaml"

EXPECTED_PROFILES = {
    "full-orchestration",
    "coding-focus",
    "thinking-focus",
    "hybrid-coding-thinking",
    "full-hybrid",
}


def _load_yaml(path: pathlib.Path):
    with path.open() as f:
        return yaml.safe_load(f)


def _all_orchestration_files() -> list[pathlib.Path]:
    return sorted(ORCH_DIR.glob("*.yaml"))


@pytest.fixture(scope="module")
def schema():
    return _load_yaml(SCHEMA_FILE)


def test_schema_file_present():
    assert SCHEMA_FILE.is_file(), f"orchestration-profile schema missing: {SCHEMA_FILE}"


def test_the_five_intent_profiles_are_a_floor():
    """The operator-named 5 orchestration-intent profiles must always exist (a
    floor). The family is growable (D-21 composer), so extra operator-composed
    profiles are allowed — each is schema-validated by the parametrized test
    below, which already runs over EVERY file on disk."""
    ids = {p.stem for p in _all_orchestration_files()}
    missing = EXPECTED_PROFILES - ids
    assert not missing, f"the 5 named orchestration profiles must exist; missing: {missing}"


@pytest.mark.parametrize("op_file", _all_orchestration_files(), ids=lambda p: p.stem)
def test_orchestration_profile_validates_against_schema(op_file, schema):
    data = _load_yaml(op_file)
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        path = " → ".join(str(p) for p in e.absolute_path)
        pytest.fail(
            f"{op_file.name} fails schema validation at "
            f"{'<root>' if not path else path}: {e.message}"
        )


@pytest.mark.parametrize("op_file", _all_orchestration_files(), ids=lambda p: p.stem)
def test_orchestration_profile_id_matches_filename(op_file):
    data = _load_yaml(op_file)
    declared_id = data.get("orchestration_profile", {}).get("id", "")
    assert declared_id == op_file.stem, (
        f"{op_file.name}: orchestration_profile.id is '{declared_id}'; "
        f"should be '{op_file.stem}'"
    )


@pytest.mark.parametrize("op_file", _all_orchestration_files(), ids=lambda p: p.stem)
def test_orchestration_profile_distinct_from_runtime_family(op_file):
    """The distinct top-level key `orchestration_profile` guarantees no
    collision with the verbatim-locked §18 runtime-profile family."""
    data = _load_yaml(op_file)
    assert "orchestration_profile" in data, (
        f"{op_file.name}: missing orchestration_profile key"
    )
    assert "runtime_profile" not in data, (
        f"{op_file.name}: must NOT carry runtime_profile (that's the locked §18 family)"
    )
