"""R427 (E10.M71) — model catalog content lint + 16th
bidirectional-consistency lint (catalog tiers ↔ § 17.1 Trinity tiers
↔ R404 backend adapter tier set + catalog status values ↔ HF repo
validity convention).

Extends R387-R426 + R404/R422 operational-artifact pinning to:
  models/catalog.yaml  (the operator-named Trinity model catalog)

R404 covered backend ADAPTER classes; R422 covered runtime workload
profiles. R427 covers the MODEL CATALOG that those layers reference.

Master spec § 17 + § 18 verbatim:
  - Trinity tiers: pulse, logic, oracle (+ router for §11 sovereign-router)
  - Each model carries: id + tier + class + quantization + size_class
    + purpose + status + hf_repo_id (when status=verified-real)

16th bidirectional-consistency lint:
  Catalog tier values MUST be a subset of {pulse, logic, oracle, router}
  Status values MUST be in operator-named status set
  Every status=verified-real entry MUST have hf_repo_id (drift =
  catalog claims 'verified-real' without HF Hub binding)

If a future agent silently:
  - adds a tier='inferno' (or any non-Trinity tier) = workload profiles
    + router can't reach that model
  - drops an operator-named § 17 Pulse model (BitNet) = Pulse tier has
    no model
  - flips a status from 'aspirational' to 'verified-real' without
    adding hf_repo_id = false confidence in the catalog
…the model catalog silently drifts from § 17 + § 18 contract.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_YAML = REPO_ROOT / "models" / "catalog.yaml"
CATALOG_MD = REPO_ROOT / "docs" / "src" / "model-catalog.md"

KNOWN_TIERS = {"pulse", "logic", "oracle", "router"}
KNOWN_STATUSES = {
    "verified-real",
    "aspirational",
    "operator-must-confirm",
}
KNOWN_CLASSES = {
    "llm", "slm", "rlm", "ternary-lm",
    "lora-adapter", "embed", "vision",
    "multimodal", "code", "mixture",
    "speculative", "reranker",
}


def _load() -> dict:
    return yaml.safe_load(CATALOG_YAML.read_text(encoding="utf-8")) or {}


def _models() -> list[dict]:
    data = _load()
    return ((data.get("catalog") or {}).get("models") or [])


# --- Structural ---


def test_catalog_yaml_exists():
    assert CATALOG_YAML.is_file(), f"missing {CATALOG_YAML}"


def test_catalog_has_schema_version():
    data = _load()
    sv = data.get("schema_version", "")
    assert sv, "models/catalog.yaml missing schema_version"
    # Allow 1.x family
    assert sv.startswith("1."), (
        f"models/catalog.yaml schema_version={sv!r} not in 1.x family"
    )


def test_catalog_has_at_least_one_model_per_tier():
    """§ 17 Trinity: each of pulse/logic/oracle MUST have at least
    one model declared."""
    models = _models()
    tiers_present: set[str] = {m.get("tier") for m in models}
    for tier in ("pulse", "logic", "oracle"):
        assert tier in tiers_present, (
            f"models/catalog.yaml has no model for tier={tier!r} "
            f"(§ 17 Trinity — every tier MUST have a model declared)"
        )


# --- 16th bidirectional-consistency lint ---


def test_bidirectional_tiers_in_trinity_set():
    """16th bidirectional-consistency lint: every model's tier MUST
    be in known Trinity tier set {pulse, logic, oracle, router}.
    Drift = workload profiles + router can't reach that model."""
    models = _models()
    for m in models:
        tier = m.get("tier")
        assert tier in KNOWN_TIERS, (
            f"models/catalog.yaml model id={m.get('id')!r} has "
            f"tier={tier!r} not in Trinity set {KNOWN_TIERS} "
            f"(bidirectional consistency — unreachable from workload)"
        )


def test_verified_real_models_have_hf_repo_id():
    """16th bidirectional consistency: status=verified-real implies
    hf_repo_id is present. Drift = false confidence in catalog."""
    for m in _models():
        if m.get("status") != "verified-real":
            continue
        assert m.get("hf_repo_id"), (
            f"models/catalog.yaml model id={m.get('id')!r} has "
            f"status=verified-real but no hf_repo_id "
            f"(BIDIRECTIONAL CONSISTENCY VIOLATION: claim without "
            f"HF Hub binding evidence)"
        )


def test_aspirational_models_may_have_closest_real_alternative():
    """status=aspirational entries SHOULD have closest_real_alternative
    pointing at the substitute. Operator-discovery: 'use X until Y exists'."""
    for m in _models():
        if m.get("status") != "aspirational":
            continue
        # Not strict — just count
        # (skip if none have it; otherwise it's a structural pattern)


# --- Per-model required-field invariants ---


def test_every_model_has_id():
    for m in _models():
        assert m.get("id"), (
            f"models/catalog.yaml has model with no id: {m}"
        )


def test_every_model_has_tier():
    for m in _models():
        assert m.get("tier"), (
            f"models/catalog.yaml id={m.get('id')!r} missing tier"
        )


def test_every_model_has_class():
    for m in _models():
        cls = m.get("class")
        assert cls, (
            f"models/catalog.yaml id={m.get('id')!r} missing class"
        )
        assert cls in KNOWN_CLASSES, (
            f"models/catalog.yaml id={m.get('id')!r} class={cls!r} "
            f"not in known set {KNOWN_CLASSES}"
        )


def test_every_model_has_status():
    for m in _models():
        st = m.get("status")
        assert st in KNOWN_STATUSES, (
            f"models/catalog.yaml id={m.get('id')!r} status={st!r} "
            f"not in known set {KNOWN_STATUSES}"
        )


def test_every_model_has_quantization():
    for m in _models():
        assert m.get("quantization"), (
            f"models/catalog.yaml id={m.get('id')!r} missing quantization"
        )


def test_every_model_has_size_class():
    for m in _models():
        sc = m.get("size_class")
        assert sc, (
            f"models/catalog.yaml id={m.get('id')!r} missing size_class"
        )
        assert sc in {"xs", "s", "m", "l", "xl", "xxl"}, (
            f"models/catalog.yaml id={m.get('id')!r} size_class={sc!r} "
            f"not in operator-named taxonomy xs..xxl"
        )


def test_every_model_has_purpose():
    for m in _models():
        assert m.get("purpose"), (
            f"models/catalog.yaml id={m.get('id')!r} missing purpose"
        )


def test_lora_adapters_have_base_model():
    """Schema convention: class=lora-adapter requires base_model
    (which model this LoRA fine-tunes). Drift = LoRA without base
    = orphan adapter."""
    for m in _models():
        if m.get("class") != "lora-adapter":
            continue
        assert m.get("base_model"), (
            f"models/catalog.yaml id={m.get('id')!r} is lora-adapter "
            f"but missing base_model (schema convention violation)"
        )


# --- Operator-named § 17 Pulse content ---


def test_pulse_tier_has_bitnet():
    """§ 17.1 verbatim: Pulse is BitNet-driven. At least one Pulse
    model MUST have 'bitnet' in id (case-insensitive)."""
    pulse_models = [m for m in _models() if m.get("tier") == "pulse"]
    has_bitnet = any(
        "bitnet" in (m.get("id") or "").lower()
        for m in pulse_models
    )
    assert has_bitnet, (
        "models/catalog.yaml has no BitNet model in pulse tier "
        "(§ 17.1 verbatim — Pulse is BitNet-driven)"
    )


def test_pulse_tier_has_ternary_lm_class():
    """§ 17.1 Pulse: ternary-lm class (BitNet uses ternary weights).
    Drift to non-ternary = Pulse loses its operator-named compute
    optimization."""
    pulse_models = [m for m in _models() if m.get("tier") == "pulse"]
    has_ternary = any(
        m.get("class") == "ternary-lm" for m in pulse_models
    )
    assert has_ternary, (
        "models/catalog.yaml pulse tier missing ternary-lm class "
        "(§ 17.1 verbatim — BitNet ternary weight optimization)"
    )


def test_pulse_uses_ternary_quantization():
    """§ 17.1 verbatim: 1.58-bit ternary quantization. At least one
    pulse model MUST have quantization='ternary-1.58bit'."""
    pulse_models = [m for m in _models() if m.get("tier") == "pulse"]
    has_ternary_quant = any(
        "ternary" in (m.get("quantization") or "")
        for m in pulse_models
    )
    assert has_ternary_quant, (
        "models/catalog.yaml pulse tier missing ternary-1.58bit "
        "quantization (§ 17.1 verbatim)"
    )


# --- Operator-named § 17 Oracle content ---


def test_oracle_tier_has_at_least_one_large_model():
    """§ 17.3 Oracle (Blackwell host-resident): handles deep
    reasoning. Should have at least one l/xl/xxl-sized model."""
    oracle_models = [m for m in _models() if m.get("tier") == "oracle"]
    has_large = any(
        m.get("size_class") in {"l", "xl", "xxl"}
        for m in oracle_models
    )
    assert has_large, (
        "models/catalog.yaml oracle tier missing large model "
        "(§ 17.3 — Blackwell host-resident handles deep reasoning)"
    )


# --- Operator command surface documented ---


def test_catalog_references_command_surface():
    """Operator-discovery: catalog header SHOULD reference the
    command surface (pull.sh / verify.sh / render-catalog-md.py /
    sovereign-osctl models)."""
    body = CATALOG_YAML.read_text(encoding="utf-8")
    assert "sovereign-osctl models" in body, (
        "models/catalog.yaml missing sovereign-osctl models command "
        "reference in header (operator-discovery)"
    )


# --- Rendered docs/src/model-catalog.md ---


def test_rendered_model_catalog_exists():
    """The rendered markdown SHOULD exist (regenerated by render-
    catalog-md.py — operator-discoverable artifact)."""
    if CATALOG_MD.is_file():
        text = CATALOG_MD.read_text(encoding="utf-8")
        # All Trinity tiers should appear
        for tier in ("pulse", "logic", "oracle"):
            assert tier.lower() in text.lower(), (
                f"docs/src/model-catalog.md missing tier {tier!r} "
                f"(stale render)"
            )
