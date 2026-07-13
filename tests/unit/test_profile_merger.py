"""Layer 2 — profile mixin merger (Q-002 substantive closure).

Validates tools/profile_merger.py: deterministic merge of
mixins + parent + child per SDD-004 § Inheritance model.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

yaml = pytest.importorskip("yaml")
from tools import profile_merger  # noqa: E402


# ----------- merge_two scalar precedence -----------

def test_overlay_scalar_overrides_base():
    out = profile_merger.merge_two({"x": 1}, {"x": 2})
    assert out["x"] == 2


def test_strict_mode_raises_on_mixin_conflict():
    with pytest.raises(profile_merger.MergeError):
        profile_merger.merge_two(
            {"x": 1}, {"x": 2}, strict_scalar_conflict=True
        )


def test_strict_mode_passes_when_scalars_agree():
    out = profile_merger.merge_two(
        {"x": 1}, {"x": 1}, strict_scalar_conflict=True
    )
    assert out["x"] == 1


# ----------- list append semantics -----------

def test_list_append():
    out = profile_merger.merge_two({"l": ["a", "b"]}, {"l": ["c"]})
    assert out["l"] == ["a", "b", "c"]


def test_list_dedup():
    out = profile_merger.merge_two({"l": ["a", "b"]}, {"l": ["b", "c"]})
    assert out["l"] == ["a", "b", "c"]


# ----------- map deep-merge -----------

def test_map_deep_merge():
    out = profile_merger.merge_two(
        {"m": {"a": 1, "b": 2}}, {"m": {"b": 3, "c": 4}}
    )
    assert out["m"] == {"a": 1, "b": 3, "c": 4}


def test_nested_map():
    out = profile_merger.merge_two(
        {"m": {"sub": {"x": 1, "y": 2}}}, {"m": {"sub": {"y": 3}}}
    )
    assert out["m"]["sub"]["y"] == 3
    assert out["m"]["sub"]["x"] == 1


# ----------- type-mismatch (overlay wins) -----------

def test_type_mismatch_overlay_wins():
    out = profile_merger.merge_two({"x": [1, 2]}, {"x": "string"})
    assert out["x"] == "string"


# ----------- packages.deny removes matches -----------

def test_deny_removes_from_base():
    profile = {
        "packages": {
            "base": ["a", "b", "popularity-contest"],
            "deny": ["popularity-contest"],
        }
    }
    out = profile_merger.apply_deny_list(profile)
    assert "popularity-contest" not in out["packages"]["base"]
    assert "a" in out["packages"]["base"]
    assert "b" in out["packages"]["base"]


def test_deny_removes_from_role():
    profile = {
        "packages": {
            "role": {"workstation": ["a", "snapd", "b"]},
            "deny": ["snapd"],
        }
    }
    out = profile_merger.apply_deny_list(profile)
    assert "snapd" not in out["packages"]["role"]["workstation"]


def test_deny_empty_is_noop():
    profile = {"packages": {"base": ["a"]}}
    out = profile_merger.apply_deny_list(profile)
    assert out["packages"]["base"] == ["a"]


# ----------- resolve() against real profiles -----------

def test_resolve_sain01_succeeds():
    """The actual sain-01 profile + its 3 mixins resolves without error."""
    effective = profile_merger.resolve("sain-01")
    assert effective["identity"]["id"] == "sain-01"


def test_resolve_sain01_has_mixin_contributions():
    """role-workstation mixin should contribute packages.role.workstation."""
    effective = profile_merger.resolve("sain-01")
    role = effective["packages"].get("role") or {}
    workstation = role.get("workstation") or []
    # role-workstation mixin contributes podman, python3-pip etc.
    assert "podman" in workstation


def test_resolve_sain01_deny_strips_phone_home():
    """popularity-contest etc. should be absent from effective base/profile lists."""
    effective = profile_merger.resolve("sain-01")
    base = effective["packages"].get("base") or []
    profile_pkgs = effective["packages"].get("profile") or []
    for forbidden in ("popularity-contest", "apport", "whoopsie", "snapd"):
        assert forbidden not in base, f"{forbidden} leaked into base"
        assert forbidden not in profile_pkgs, f"{forbidden} leaked into profile"


def test_resolve_sain01_keeps_hardware_block():
    """Hardware block from sain-01 profile must survive merge.

    SDD-993 three-card reality: RTX 5090 (internal primary) + RTX 4090 (OcuLink
    eGPU) + RTX PRO 6000 (future upgrade path — kept additively, not discarded)."""
    effective = profile_merger.resolve("sain-01")
    assert effective["hardware"]["cpu"]["march"] == "znver5"
    gpus = effective["hardware"]["gpu"]
    assert len(gpus) == 3
    models = [g.get("model") for g in gpus]
    assert "rtx-5090" in models and "rtx-4090" in models
    # the RTX 5090 is the declared internal primary
    assert any(g.get("model") == "rtx-5090" and g.get("role") == "primary" for g in gpus)


def test_resolve_old_workstation_succeeds():
    """Alternate profile also resolves cleanly."""
    effective = profile_merger.resolve("old-workstation")
    assert effective["identity"]["id"] == "old-workstation"


# ----------- cycle detection -----------

def test_cycle_detection_in_parent_chain(tmp_path, monkeypatch):
    """Synthetic test: create two profiles that parent each other."""
    pd = tmp_path / "profiles"
    pd.mkdir()
    md = pd / "mixins"
    md.mkdir()
    (pd / "a.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "identity": {"id": "a", "parent": "b"},
            }
        )
    )
    (pd / "b.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "identity": {"id": "b", "parent": "a"},
            }
        )
    )
    monkeypatch.setattr(profile_merger, "PROFILE_DIR", pd)
    monkeypatch.setattr(profile_merger, "MIXIN_DIR", md)

    with pytest.raises(RuntimeError, match="cycle"):
        profile_merger.resolve("a")


# ----------- mixin merge strictness -----------

def test_two_mixins_disagreeing_on_scalar_fails(tmp_path, monkeypatch):
    pd = tmp_path / "profiles"
    pd.mkdir()
    md = pd / "mixins"
    md.mkdir()

    (md / "m1.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "mixin": {"id": "m1"},
                "observability": {"telemetry_sink": "prometheus-local"},
            }
        )
    )
    (md / "m2.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "mixin": {"id": "m2"},
                "observability": {"telemetry_sink": "otel"},  # conflict
            }
        )
    )
    (pd / "x.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "mixins": ["m1", "m2"],
                "identity": {"id": "x", "parent": None},
            }
        )
    )

    monkeypatch.setattr(profile_merger, "PROFILE_DIR", pd)
    monkeypatch.setattr(profile_merger, "MIXIN_DIR", md)

    with pytest.raises(profile_merger.MergeError, match="scalar conflict"):
        profile_merger.resolve("x")
