"""Layer 1 — mixin YAML schema conformance (Round 124).

Mixin files under `profiles/mixins/*.yaml` ALL reference
`schemas/mixin.schema.yaml` via the `yaml-language-server` editor hint.
The schema didn't exist until Round 124 — IDE-level validation silently
failed, no CI gate validated mixin structure.

This test validates every mixin file against the schema. Catches:
  - Missing required keys (schema_version, mixin.id, mixin.description)
  - Wrong types (e.g., packages.base as object instead of array)
  - Invalid hook declarations
  - Schema_version that doesn't match major.minor.patch pattern
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
MIXINS_DIR = REPO_ROOT / "profiles" / "mixins"
SCHEMA_FILE = REPO_ROOT / "schemas" / "mixin.schema.yaml"


def _load_yaml(path: pathlib.Path):
    with path.open() as f:
        return yaml.safe_load(f)


def _all_mixin_files() -> list[pathlib.Path]:
    return sorted(MIXINS_DIR.glob("*.yaml"))


@pytest.fixture(scope="module")
def schema():
    return _load_yaml(SCHEMA_FILE)


def test_schema_file_present():
    assert SCHEMA_FILE.is_file(), f"mixin schema missing: {SCHEMA_FILE}"


def test_mixin_dir_present_and_populated():
    assert MIXINS_DIR.is_dir(), f"mixins dir missing: {MIXINS_DIR}"
    files = _all_mixin_files()
    assert len(files) >= 5, f"expected ≥5 mixins, found {len(files)}"


@pytest.mark.parametrize("mixin_file", _all_mixin_files(), ids=lambda p: p.stem)
def test_mixin_validates_against_schema(mixin_file, schema):
    """Every mixin YAML conforms to schemas/mixin.schema.yaml."""
    data = _load_yaml(mixin_file)
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        # Make the failure operator-actionable
        path = " → ".join(str(p) for p in e.absolute_path)
        pytest.fail(
            f"{mixin_file.name} fails schema validation at "
            f"{'<root>' if not path else path}: {e.message}"
        )


@pytest.mark.parametrize("mixin_file", _all_mixin_files(), ids=lambda p: p.stem)
def test_mixin_id_matches_filename(mixin_file):
    """Convention: the mixin's `mixin.id` MUST equal the filename stem."""
    data = _load_yaml(mixin_file)
    mixin_id = data.get("mixin", {}).get("id", "")
    assert mixin_id == mixin_file.stem, \
        f"{mixin_file.name}: mixin.id is '{mixin_id}', expected '{mixin_file.stem}'"


@pytest.mark.parametrize("mixin_file", _all_mixin_files(), ids=lambda p: p.stem)
def test_mixin_yaml_language_server_directive_present(mixin_file):
    """Editor-side validation depends on the yaml-language-server hint
    pointing at the schema. Round 124 catches the case where the hint
    points at a missing file."""
    text = mixin_file.read_text()
    assert "yaml-language-server: $schema=" in text, \
        f"{mixin_file.name} missing yaml-language-server directive"
    assert "mixin.schema.yaml" in text, \
        f"{mixin_file.name} yaml-language-server hint doesn't reference mixin.schema.yaml"
