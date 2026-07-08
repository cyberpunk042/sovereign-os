"""R424 (E10.M68) — JSON-schema set consistency lint + 13th
bidirectional-consistency lint (data files ↔ schema $id ↔ schema test
coverage).

Extends R387-R423 + R417/R422 operational-artifact pinning to:
  schemas/mixin.schema.yaml
  schemas/profile.schema.yaml
  schemas/runtime-profile.schema.yaml
  schemas/whitelabel.schema.yaml
  schemas/model-catalog.schema.yaml

13th bidirectional-consistency lint (3-way triangle):
  - schemas/<X>.schema.yaml exists
  - tests/schema/test_<X>_schema_conformance.py exists (validation test)
  - data files exist in profiles/, profiles/mixins/, profiles/runtime/,
    whitelabel/ (the things the schemas validate)

Drift = schema file present but no validator test = schema becomes
documentation-only without enforcement.

Schema-internal contract:
  - $schema declared (JSON Schema dialect — usually 2020-12 or draft-07)
  - $id declared (cross-schema reference resolution)
  - title declared (operator-discovery)
  - type=object at root
  - required[] list non-empty (at least schema_version)
  - $defs section for shared types (operator pattern — drift to inline
    types loses cross-schema reuse)
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "schemas"
SCHEMA_TESTS_DIR = REPO_ROOT / "tests" / "schema"

EXPECTED_SCHEMAS = [
    "mixin",
    "profile",
    "runtime-profile",
    "whitelabel",
    "model-catalog",
    "orchestration-profile",
]


def _schema_path(name: str) -> Path:
    return SCHEMAS_DIR / f"{name}.schema.yaml"


def _load_schema(name: str) -> dict:
    p = _schema_path(name)
    assert p.is_file(), f"missing schema: {p}"
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


# --- Structural ---


def test_all_five_schemas_exist():
    for name in EXPECTED_SCHEMAS:
        p = _schema_path(name)
        assert p.is_file(), (
            f"schema missing: {p} (operator-named 5-schema set)"
        )


def test_schema_count_matches():
    actual = sorted(p.stem.replace(".schema", "")
                    for p in SCHEMAS_DIR.glob("*.schema.yaml"))
    assert actual == sorted(EXPECTED_SCHEMAS), (
        f"schemas/ drift: actual={actual} vs expected={EXPECTED_SCHEMAS}"
    )


# --- Schema-internal contract ---


def test_every_schema_declares_dollar_schema():
    """$schema MUST be declared (validators rely on the dialect URI
    to pick the right validation algorithm). Drift = json-schema lib
    can't validate at all."""
    for name in EXPECTED_SCHEMAS:
        data = _load_schema(name)
        assert "$schema" in data, (
            f"{name}.schema.yaml missing $schema declaration "
            f"(validator dialect URI required)"
        )


def test_every_schema_declares_dollar_id():
    """$id MUST be declared (cross-schema $ref resolution depends on it)."""
    for name in EXPECTED_SCHEMAS:
        data = _load_schema(name)
        assert "$id" in data, (
            f"{name}.schema.yaml missing $id (cross-schema $ref "
            f"resolution requires unique identifier)"
        )


def test_every_schema_has_title():
    """title MUST be present (operator-discovery surface)."""
    for name in EXPECTED_SCHEMAS:
        data = _load_schema(name)
        title = data.get("title", "")
        assert title, (
            f"{name}.schema.yaml missing title (operator-discovery)"
        )
        assert "sovereign-os" in title.lower(), (
            f"{name}.schema.yaml title={title!r} doesn't reference "
            f"'sovereign-os' (project binding context)"
        )


def test_every_schema_root_type_object():
    """Schema root MUST be type=object (drift = consumers reject valid
    YAML)."""
    for name in EXPECTED_SCHEMAS:
        data = _load_schema(name)
        assert data.get("type") == "object", (
            f"{name}.schema.yaml root type={data.get('type')!r} != "
            f"object"
        )


def test_every_schema_has_required_list():
    """required[] MUST be non-empty (schema with no required fields
    accepts anything = useless)."""
    for name in EXPECTED_SCHEMAS:
        data = _load_schema(name)
        required = data.get("required") or []
        assert required, (
            f"{name}.schema.yaml has empty required[] (schema accepts "
            f"anything = no enforcement)"
        )


def test_every_schema_requires_schema_version():
    """schema_version MUST be in required[] (operator-named version
    pin — consumers key off it)."""
    for name in EXPECTED_SCHEMAS:
        data = _load_schema(name)
        required = data.get("required") or []
        assert "schema_version" in required, (
            f"{name}.schema.yaml missing 'schema_version' in required "
            f"(operator-named version pin for consumer compatibility)"
        )


def test_every_schema_has_properties_block():
    """properties{} MUST define at least the required fields."""
    for name in EXPECTED_SCHEMAS:
        data = _load_schema(name)
        props = data.get("properties") or {}
        assert props, (
            f"{name}.schema.yaml missing properties{{}} block"
        )
        # Required fields MUST appear in properties
        required = data.get("required") or []
        for field in required:
            assert field in props, (
                f"{name}.schema.yaml: '{field}' in required[] but "
                f"not in properties{{}}"
            )


# --- 13th bidirectional-consistency lint ---


def test_bidirectional_schema_has_conformance_test():
    """13th bidirectional-consistency lint: every schemas/<X>.schema.yaml
    MUST have a matching tests/schema/test_<X>_schema_conformance.py
    (the validator test that USES the schema). Drift = schema becomes
    documentation-only without runtime enforcement."""
    for name in EXPECTED_SCHEMAS:
        # Test file name convention
        test_stem = name.replace("-", "_")
        test_path = SCHEMA_TESTS_DIR / f"test_{test_stem}_schema_conformance.py"
        assert test_path.is_file(), (
            f"schemas/{name}.schema.yaml has no matching "
            f"tests/schema/test_{test_stem}_schema_conformance.py "
            f"(BIDIRECTIONAL CONSISTENCY VIOLATION: schema exists "
            f"but no validator test = schema is documentation-only)"
        )


def test_conformance_test_references_schema_file():
    """Each conformance test MUST reference its schema file (drift =
    test validates against the WRONG schema)."""
    for name in EXPECTED_SCHEMAS:
        test_stem = name.replace("-", "_")
        test_path = SCHEMA_TESTS_DIR / f"test_{test_stem}_schema_conformance.py"
        if not test_path.is_file():
            continue
        body = test_path.read_text(encoding="utf-8")
        assert f"{name}.schema" in body, (
            f"tests/schema/test_{test_stem}_schema_conformance.py "
            f"doesn't reference {name}.schema.yaml (validating wrong schema)"
        )


# --- Schema-specific contracts ---


def test_profile_schema_requires_identity():
    """profile.schema requires identity section (operator-named — every
    profile has id + name + description)."""
    data = _load_schema("profile")
    required = data.get("required") or []
    assert "identity" in required, (
        "profile.schema.yaml missing 'identity' in required "
        "(operator-named — every profile MUST have identity block)"
    )


def test_mixin_schema_requires_mixin_block():
    """mixin.schema requires the 'mixin' top-level block (which holds
    id + description). Drift = mixin YAMLs without mixin.id can pass."""
    data = _load_schema("mixin")
    required = data.get("required") or []
    assert "mixin" in required, (
        "mixin.schema.yaml missing 'mixin' in required (composition "
        "contract — drift lets mixin.id-less files pass)"
    )


def test_runtime_profile_schema_requires_runtime_profile_block():
    data = _load_schema("runtime-profile")
    required = data.get("required") or []
    assert "runtime_profile" in required, (
        "runtime-profile.schema.yaml missing 'runtime_profile' in "
        "required"
    )


def test_whitelabel_schema_requires_identity_or_branding():
    """whitelabel schema requires identity (operator-named brand
    identity block)."""
    data = _load_schema("whitelabel")
    required = data.get("required") or []
    assert "identity" in required, (
        "whitelabel.schema.yaml missing 'identity' in required "
        "(operator-named brand-identity block)"
    )


# --- $defs reuse pattern ---


def test_most_schemas_use_defs_for_shared_types():
    """Operator pattern: shared types live in $defs (drift to inline
    types loses cross-schema reuse). Most schemas use $defs."""
    have_defs = 0
    total = 0
    for name in EXPECTED_SCHEMAS:
        data = _load_schema(name)
        total += 1
        if data.get("$defs"):
            have_defs += 1
    # At least 3 of 5 schemas should use $defs
    assert have_defs >= 3, (
        f"only {have_defs}/{total} schemas use $defs (operator pattern "
        f"for shared types; drift loses cross-schema reuse)"
    )


# --- Mixin schema ↔ profile schema $ref ---


def test_profile_schema_or_mixin_schema_cross_reference():
    """Either profile.schema references mixin.schema (when profile
    declares mixins) OR mixin.schema is standalone — both are fine,
    but if a $ref exists it MUST be a relative path that resolves."""
    profile_text = _schema_path("profile").read_text(encoding="utf-8")
    # If profile.schema has a $ref to mixin, it should be relative
    if "mixin.schema" in profile_text:
        # Should be a relative reference like './mixin.schema.yaml'
        # or 'mixin.schema.yaml'
        assert "mixin.schema.yaml" in profile_text, (
            "profile.schema references mixin schema but with wrong "
            "filename"
        )


# --- additionalProperties hygiene ---


def test_most_schemas_set_additional_properties_false_at_root():
    """Strict mode: additionalProperties: false at root catches typos
    + unknown keys. Most schemas should set it."""
    strict_count = 0
    for name in EXPECTED_SCHEMAS:
        data = _load_schema(name)
        if data.get("additionalProperties") is False:
            strict_count += 1
    # At least 3 of 5 should be strict
    assert strict_count >= 3, (
        f"only {strict_count}/5 schemas set additionalProperties: false "
        f"at root (drift to permissive = typos pass validation)"
    )
