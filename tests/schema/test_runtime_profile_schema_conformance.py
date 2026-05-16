"""Layer 1 — runtime-profile YAML schema conformance (R150).

Every `profiles/runtime/*.yaml` MUST validate against
`schemas/runtime-profile.schema.yaml`. Schema authored at R150 to
materialize master spec § 18 (the 3 runtime profiles).
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
RUNTIME_DIR = REPO_ROOT / "profiles" / "runtime"
SCHEMA_FILE = REPO_ROOT / "schemas" / "runtime-profile.schema.yaml"


def _load_yaml(path: pathlib.Path):
    with path.open() as f:
        return yaml.safe_load(f)


def _all_runtime_files() -> list[pathlib.Path]:
    return sorted(RUNTIME_DIR.glob("*.yaml"))


@pytest.fixture(scope="module")
def schema():
    return _load_yaml(SCHEMA_FILE)


def test_schema_file_present():
    assert SCHEMA_FILE.is_file(), f"runtime-profile schema missing: {SCHEMA_FILE}"


def test_three_master_spec_runtime_profiles_present():
    """Master spec § 18 names exactly 3 profiles. R150 ships those 3.
    Additional profiles are operator-additive; this test pins the 3
    master-spec-mandated ones."""
    ids = {p.stem for p in _all_runtime_files()}
    for required in (
        "ultra-sovereign-efficiency",
        "high-concurrency-burst",
        "deep-context-synthesis",
    ):
        assert required in ids, \
            f"master spec § 18 mandates '{required}' but it's missing"


@pytest.mark.parametrize("rp_file", _all_runtime_files(), ids=lambda p: p.stem)
def test_runtime_profile_validates_against_schema(rp_file, schema):
    data = _load_yaml(rp_file)
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        path = " → ".join(str(p) for p in e.absolute_path)
        pytest.fail(
            f"{rp_file.name} fails schema validation at "
            f"{'<root>' if not path else path}: {e.message}"
        )


@pytest.mark.parametrize("rp_file", _all_runtime_files(), ids=lambda p: p.stem)
def test_runtime_profile_id_matches_filename(rp_file):
    data = _load_yaml(rp_file)
    declared_id = data.get("runtime_profile", {}).get("id", "")
    assert declared_id == rp_file.stem, \
        f"{rp_file.name}: runtime_profile.id is '{declared_id}'; should be '{rp_file.stem}'"


@pytest.mark.parametrize("rp_file", _all_runtime_files(), ids=lambda p: p.stem)
def test_runtime_profile_master_spec_citation_in_header(rp_file):
    """Each runtime profile must cite master spec § 18 in its header
    comment — preserves the architectural trace from the verbatim source."""
    text = rp_file.read_text()
    # First 10 lines (header comment block)
    header = "\n".join(text.splitlines()[:10])
    assert "master spec § 18" in header.lower() or "Master spec § 18" in header, \
        f"{rp_file.name} header missing master spec § 18 citation"
