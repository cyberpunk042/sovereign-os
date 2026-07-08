"""power-profiles.toml.example ⇄ code config-knob discoverability (R345).

`scripts/power/profiles.py:load_profiles` seeds a default `cfg` dict of
operator-settable top-level knobs (R345/E2.M33/SDD-035 workload-mode
coordinator adoption) and merges any same-named keys from the operator's
power-profiles.toml overlay. An operator who never sees these knobs in the
shipped `power-profiles.toml.example` can't discover they exist — the same
silent config-discoverability gap that hid `[graceful_shutdown] enabled`
(SDD-029) for power.toml.

This gate binds the example to the code: every top-level knob the loader
reads (the keys of load_profiles' default cfg) MUST be documented in
power-profiles.toml.example, AND the documented value must equal the code
default (so the example doesn't advertise a non-default surprise). Uses the
REAL cfg keys from the code — no `.get()` heuristic — so it can't
false-positive on unrelated dict access.
"""
from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = REPO_ROOT / "scripts" / "power" / "profiles.py"
EXAMPLE = REPO_ROOT / "config" / "power-profiles.toml.example"


def _default_cfg() -> dict:
    spec = importlib.util.spec_from_file_location("power_profiles_knob", PROFILES)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _profiles, _meta, cfg = mod.load_profiles(None)
    return cfg


def _example() -> dict:
    return tomllib.load(EXAMPLE.open("rb"))


def test_example_parses():
    doc = _example()
    assert doc.get("profiles"), "example has no [[profiles]] — parse/structure broken"


def test_every_code_knob_is_documented_in_example():
    cfg = _default_cfg()
    doc = _example()
    missing = sorted(k for k in cfg if k not in doc)
    assert not missing, (
        f"load_profiles reads operator config knob(s) {missing} that are NOT "
        f"documented in power-profiles.toml.example — operators can't "
        f"discover them. Add each as a top-level key (before the [[profiles]] "
        f"array-tables) with a comment + the code default."
    )


def test_documented_knob_values_match_code_defaults():
    cfg = _default_cfg()
    doc = _example()
    mismatched = {
        k: (doc[k], cfg[k]) for k in cfg
        if k in doc and doc[k] != cfg[k]
    }
    assert not mismatched, (
        f"power-profiles.toml.example documents knob value(s) that differ "
        f"from the code default {mismatched} (example value, code default). "
        f"The example should show the real default so copying it is a no-op."
    )
