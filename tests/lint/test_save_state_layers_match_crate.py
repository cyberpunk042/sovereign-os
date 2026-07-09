"""Drift-guard: the Python save-state orchestrator's `_LAYERS` MUST match the
`crates/sovereign-save-state` `SaveLayer` enum (serde kebab-case names).

The Rust crate is the single source of truth for the 5-layer save-state contract
(E0451); the Python orchestrator (`scripts/lifecycle/save-state.py`, SDD-057)
mirrors it. This lock fails if either side adds/renames/drops a layer without the
other — so a "true save-state = all 5 layers" gate cannot silently diverge.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CRATE = REPO / "crates" / "sovereign-save-state" / "src" / "lib.rs"
PY = REPO / "scripts" / "lifecycle" / "save-state.py"


def _camel_to_kebab(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def _crate_layers() -> list[str]:
    """Parse the `SaveLayer` enum variants + serde kebab-case them."""
    body = CRATE.read_text(encoding="utf-8")
    m = re.search(r"pub enum SaveLayer\s*\{(.+?)\}", body, re.DOTALL)
    assert m, "SaveLayer enum not found in the crate"
    block = m.group(1)
    assert 'rename_all = "kebab-case"' in body, "crate must serde-rename kebab-case"
    variants = re.findall(r"^\s*([A-Z][A-Za-z0-9]+)\s*,", block, re.MULTILINE)
    return [_camel_to_kebab(v) for v in variants]


def _py_layers() -> tuple[str, ...]:
    spec = importlib.util.spec_from_file_location("save_state_layers", PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._LAYERS


def test_crate_defines_five_layers():
    layers = _crate_layers()
    assert len(layers) == 5, f"expected 5 SaveLayer variants, got {layers}"
    assert set(layers) == {"zfs-snapshot", "criu-checkpoint", "replay-log",
                           "memory-record", "profile-state"}


def test_python_layers_match_crate():
    crate = set(_crate_layers())
    py = set(_py_layers())
    assert py == crate, (
        f"save-state layer drift: python {sorted(py)} vs crate {sorted(crate)} — "
        "keep scripts/lifecycle/save-state.py _LAYERS in sync with the "
        "sovereign-save-state SaveLayer enum")
