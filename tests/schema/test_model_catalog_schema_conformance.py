"""Layer 1 — model catalog YAML schema conformance (R156).

`models/catalog.yaml` MUST validate against
`schemas/model-catalog.schema.yaml`. Schema authored at R156 to
materialize the operator-facing canonical declaration of which models
The Genesis Trinity (master spec § 17) intends to host across pulse/
logic/oracle tiers.
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
CATALOG_FILE = REPO_ROOT / "models" / "catalog.yaml"
SCHEMA_FILE = REPO_ROOT / "schemas" / "model-catalog.schema.yaml"


def _load_yaml(path: pathlib.Path):
    with path.open() as f:
        return yaml.safe_load(f)


def test_schema_file_present():
    assert SCHEMA_FILE.exists(), f"schema missing: {SCHEMA_FILE}"


def test_catalog_file_present():
    assert CATALOG_FILE.exists(), f"catalog missing: {CATALOG_FILE}"


def test_catalog_validates_against_schema():
    schema = _load_yaml(SCHEMA_FILE)
    catalog = _load_yaml(CATALOG_FILE)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(catalog), key=lambda e: e.path)
    assert not errors, "\n".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def test_at_least_one_model_per_trinity_tier_declared():
    """Master spec § 17 names Pulse + Logic + Oracle. At least one
    catalog entry per tier — even if some are aspirational — to keep
    the trinity surface honest."""
    catalog = _load_yaml(CATALOG_FILE)
    tiers = {m["tier"] for m in catalog["catalog"]["models"]}
    for required in ("pulse", "logic", "oracle"):
        assert required in tiers, f"no catalog entry for tier={required}"


def test_verified_real_entries_have_hf_repo_id():
    """status=verified-real MUST carry hf_repo_id (schema enforces; this
    is the operator-readable cross-check)."""
    catalog = _load_yaml(CATALOG_FILE)
    for m in catalog["catalog"]["models"]:
        if m["status"] == "verified-real":
            assert m.get("hf_repo_id"), (
                f"verified-real entry {m['id']} missing hf_repo_id"
            )


def test_runtime_profile_bindings_reference_real_profiles():
    """Every runtime_profile_bindings entry must map to a real
    profiles/runtime/*.yaml file."""
    catalog = _load_yaml(CATALOG_FILE)
    runtime_dir = REPO_ROOT / "profiles" / "runtime"
    real_profile_ids = {p.stem for p in runtime_dir.glob("*.yaml")}
    for m in catalog["catalog"]["models"]:
        for binding in m.get("runtime_profile_bindings", []):
            assert binding in real_profile_ids, (
                f"model {m['id']} binds to runtime profile "
                f"'{binding}' which has no profiles/runtime/{binding}.yaml"
            )


def test_master_spec_section_citation_present_on_all_entries():
    """Operator words sacrosanct — every model must carry a master spec
    section citation so the operator can trace the provenance."""
    catalog = _load_yaml(CATALOG_FILE)
    for m in catalog["catalog"]["models"]:
        assert m.get("master_spec_section"), (
            f"{m['id']} missing master_spec_section citation"
        )


def test_aspirational_entries_carry_closest_real_alternative():
    """status=aspirational entries MUST point operator at a real
    substitute so they aren't left at a dead-end."""
    catalog = _load_yaml(CATALOG_FILE)
    for m in catalog["catalog"]["models"]:
        if m["status"] == "aspirational":
            assert m.get("closest_real_alternative"), (
                f"aspirational entry {m['id']} missing "
                f"closest_real_alternative — operator left at dead-end"
            )


# ---- R212 taxonomy lints --------------------------------------------------


def test_r212_schema_version_is_1_1_0():
    """R212 bumped the schema to 1.1.0 alongside the class/quantization/
    size_class/purpose/vram_gib_min/context_window_tokens/base_model
    additions."""
    catalog = _load_yaml(CATALOG_FILE)
    assert catalog["schema_version"] == "1.1.0", (
        f"expected schema_version 1.1.0 (R212), got {catalog['schema_version']!r}"
    )


def test_r212_every_model_declares_class():
    """R212 taxonomy: every model carries `class` so operators can
    filter the catalog by what KIND of model it is."""
    catalog = _load_yaml(CATALOG_FILE)
    missing = [m["id"] for m in catalog["catalog"]["models"] if not m.get("class")]
    assert not missing, f"models missing R212 `class` field: {missing}"


def test_r212_every_model_declares_quantization():
    """R212 taxonomy: every model carries `quantization` so operators
    see which numeric format the catalog declares it lands as."""
    catalog = _load_yaml(CATALOG_FILE)
    missing = [
        m["id"] for m in catalog["catalog"]["models"] if not m.get("quantization")
    ]
    assert not missing, f"models missing R212 `quantization`: {missing}"


def test_r212_every_model_declares_size_class():
    catalog = _load_yaml(CATALOG_FILE)
    missing = [
        m["id"] for m in catalog["catalog"]["models"] if not m.get("size_class")
    ]
    assert not missing, f"models missing R212 `size_class`: {missing}"


def test_r212_every_model_declares_purpose():
    catalog = _load_yaml(CATALOG_FILE)
    missing = [
        m["id"]
        for m in catalog["catalog"]["models"]
        if not (m.get("purpose") or [])
    ]
    assert not missing, f"models missing non-empty `purpose` array: {missing}"


def test_r212_lora_adapters_carry_base_model():
    """R212 schema rule: class=lora-adapter MUST set base_model.
    This pins the operator-readable invariant."""
    catalog = _load_yaml(CATALOG_FILE)
    for m in catalog["catalog"]["models"]:
        if m.get("class") == "lora-adapter":
            assert m.get("base_model"), (
                f"LoRA adapter {m['id']} missing `base_model`"
            )


def test_r212_catalog_spans_diverse_taxonomy():
    """Operator directive: 'all the best selection of models adapted
    for various size and at various quantization or for various
    specific purpose'. Pin that diversity at L1 so a future operator
    pruning the catalog can't silently collapse the taxonomy."""
    catalog = _load_yaml(CATALOG_FILE)
    classes = {m.get("class") for m in catalog["catalog"]["models"]}
    quants = {m.get("quantization") for m in catalog["catalog"]["models"]}
    sizes = {m.get("size_class") for m in catalog["catalog"]["models"]}
    # At least 6 distinct classes, 4 distinct quantizations,
    # 3 distinct size_classes — keeps the catalog honestly diverse.
    assert len(classes) >= 6, f"catalog has only {len(classes)} classes: {classes}"
    assert len(quants) >= 4, (
        f"catalog has only {len(quants)} quantizations: {quants}"
    )
    assert len(sizes) >= 3, f"catalog has only {len(sizes)} size_classes: {sizes}"
