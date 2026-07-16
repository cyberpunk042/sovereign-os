"""SDD-715 — LoRA-adapter serving coherence (M046 E0442 LoRA-as-profiles).

The M046 foundry inventories + gates + promotes adapters; SDD-715 adds the
*serving* half. These invariants keep the catalog's adapter↔base↔profile graph
honest so a bound adapter is actually loadable:

  1. Every `class: lora-adapter` entry's `base_model` resolves to a REAL catalog
     model id (stronger than test_model_catalog_content's presence-only check) —
     an adapter whose base doesn't exist can never be served.
  2. If an adapter declares `runtime_profile_bindings`, every bound runtime
     profile must actually SERVE the adapter's base_model (a hardcoded-`model`
     allocation for that base) — E0442 "profiles decide overlays": an overlay
     on a base the profile doesn't run is incoherent. (Profiles that bind a
     tier by `tier_intent` instead of a hardcoded model are skipped — the base
     is resolved at runtime by the VRAM-aware selector, not statically here.)
  3. The llama.cpp backend adapter exposes `--lora` — the mechanism that makes
     a bound adapter loadable at all (SDD-715).
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "models" / "catalog.yaml"
RUNTIME_DIR = REPO_ROOT / "profiles" / "runtime"
LLAMA_ADAPTER = REPO_ROOT / "scripts" / "inference" / "backends" / "llama_cpp.py"


def _catalog_entries() -> list[dict]:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    out: list[dict] = []

    def walk(o):
        if isinstance(o, dict):
            if "id" in o and "engine" in o:
                out.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return out


def _profile_served_models(profile_id: str) -> set[str]:
    p = RUNTIME_DIR / f"{profile_id}.yaml"
    if not p.is_file():
        return set()
    rp = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("runtime_profile") or {}
    return {a["model"] for a in (rp.get("allocations") or []) if a.get("model")}


def test_base_model_carrying_entries_resolve():
    """Any entry that declares base_model (lora-adapter, and SDD-717's
    speculative draft + vision-projector companions) must point at a REAL
    catalog model — an overlay/draft/projector on a non-existent base can
    never be served."""
    entries = _catalog_entries()
    ids = {e["id"] for e in entries}
    with_base = [e for e in entries if e.get("base_model")]
    assert with_base, "expected at least one base_model-carrying entry"
    for a in with_base:
        base = a.get("base_model")
        assert base in ids, (
            f"{a.get('class')} {a['id']!r} base_model={base!r} does not resolve "
            f"to a real catalog model id (orphan — can never be served)"
        )


def test_bound_profile_serves_the_base():
    for a in (e for e in _catalog_entries() if e.get("base_model")):
        base = a.get("base_model")
        for profile_id in a.get("runtime_profile_bindings") or []:
            p = RUNTIME_DIR / f"{profile_id}.yaml"
            assert p.is_file(), (
                f"lora-adapter {a['id']!r} bound to runtime profile "
                f"{profile_id!r} which doesn't exist"
            )
            served = _profile_served_models(profile_id)
            # Skip only when the profile hardcodes NO models at all (pure
            # tier_intent) — then base resolution is a runtime concern.
            if not served:
                continue
            assert base in served, (
                f"{a.get('class')} {a['id']!r} (base {base!r}) is bound to "
                f"profile {profile_id!r}, but that profile does not serve "
                f"{base!r} (serves {sorted(served)}) — E0442 companion-on-"
                f"unserved-base (LoRA overlay / speculative draft / vision proj)"
            )


def test_llama_cpp_adapter_supports_lora_overlay():
    body = LLAMA_ADAPTER.read_text(encoding="utf-8")
    assert "--lora" in body and "lora_path" in body, (
        "llama_cpp.py must expose --lora / lora_path so a bound adapter is "
        "actually loadable (SDD-715 serving half of the M046 foundry)"
    )
