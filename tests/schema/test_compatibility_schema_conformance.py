"""Layer 1 — compatibility registry YAML schema conformance (2026-07-19).

`config/compatibility.yaml` MUST validate against
`schemas/compatibility.schema.yaml`. Schema authored for the
cross-system compatibility module (operator directive 2026-07-19,
PR #245): requires / conflicts_with / forces_off / one_of rules over
the control-systems registry, per-rule severity, mandatory
reason + remediation. The deeper gates (registry-reference resolution,
bit-universe roundtrip, severity semantics, CLI rc contract) live in
tests/lint/test_compatibility_rules.py; this file is the
schema-conformance half of the bidirectional-consistency pair
(tests/lint/test_schemas_consistency.py).
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
REGISTRY_FILE = REPO_ROOT / "config" / "compatibility.yaml"
SCHEMA_FILE = REPO_ROOT / "schemas" / "compatibility.schema.yaml"


def _load_yaml(path: pathlib.Path):
    with path.open() as f:
        return yaml.safe_load(f)


def test_schema_file_present():
    assert SCHEMA_FILE.exists(), f"schema missing: {SCHEMA_FILE}"


def test_registry_file_present():
    assert REGISTRY_FILE.exists(), f"registry missing: {REGISTRY_FILE}"


def test_registry_validates_against_schema():
    schema = _load_yaml(SCHEMA_FILE)
    registry = _load_yaml(REGISTRY_FILE)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(registry), key=lambda e: e.path)
    assert not errors, "\n".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def test_every_verb_shape_is_consistent():
    """one_of rules carry `targets`; requires/conflicts_with/forces_off
    carry `target` or `targets` — never neither."""
    registry = _load_yaml(REGISTRY_FILE)
    for rule in registry["compatibility"]["rules"]:
        has_target = "target" in rule or "targets" in rule
        assert has_target, f"{rule['id']}: no target(s)"
        if rule["verb"] == "one_of":
            assert "targets" in rule, f"{rule['id']}: one_of needs `targets`"
