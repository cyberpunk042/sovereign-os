"""wattage-heat-trend-watcher ⇄ thermal-oc-budget schema binding (E1.M36).

The trend watcher's `sample_signals()` reads CPU/GPU temps out of the
thermal-oc-budget `status --json` document. For its first ~life it pointed
at a never-created `heat-integration.py`, so `_run_json` returned None and
the watcher silently captured NO temps — yet the L3 test passed because it
only asserted the OUTPUT KEYS exist (they're initialised to None at the top
of sample_signals, so key-presence is vacuous).

The catch-all path gate (test_script_path_refs_resolve) stops the script
PATH from dangling again, but it cannot catch a SCHEMA drift: if
thermal-oc-budget renames `thermal.hottest_cpu_c`, the watcher silently
returns None again and key-presence stays green. This gate closes the
remaining angle — it locks the actual producer→consumer field binding in
both directions:

  1. thermal-oc-budget really emits thermal.hottest_cpu_c / hottest_gpu_c
     (the producer schema the watcher depends on).
  2. The watcher, fed that exact shape, actually populates cpu_temp_c /
     gpu_temp_c from it (the consumer extraction works).

A rename on EITHER side fails this test instead of silently zeroing the
operator's heat-trend surface.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WATCHER = REPO_ROOT / "scripts" / "hardware" / "wattage-heat-trend-watcher.py"
THERMAL = REPO_ROOT / "scripts" / "hardware" / "thermal-oc-budget.py"


def _load_watcher():
    spec = importlib.util.spec_from_file_location("whtw_binding", WATCHER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_producer_emits_hottest_temp_fields():
    """thermal-oc-budget status --json must carry thermal.hottest_cpu_c /
    hottest_gpu_c — the fields the watcher binds to."""
    cp = subprocess.run(
        [sys.executable, str(THERMAL), "status", "--json"],
        capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
    )
    assert cp.returncode in (0, 1), (
        f"thermal-oc-budget status --json exited {cp.returncode}: "
        f"{cp.stderr[:300]}"
    )
    import json
    doc = json.loads(cp.stdout)
    thermal = doc.get("thermal")
    assert isinstance(thermal, dict), (
        "thermal-oc-budget status --json has no `thermal` object — the "
        "watcher's heat probe binds to thermal.hottest_*_c"
    )
    for key in ("hottest_cpu_c", "hottest_gpu_c"):
        assert key in thermal, (
            f"thermal-oc-budget no longer emits thermal.{key}; the trend "
            f"watcher binds to it and will silently capture no temp. Update "
            f"the watcher's extraction (sample_signals) to the new field."
        )


def test_watcher_extracts_temps_from_producer_shape(monkeypatch):
    """Fed a realistic thermal-oc-budget shape, sample_signals() must
    populate cpu_temp_c / gpu_temp_c (not leave them None)."""
    w = _load_watcher()

    canned = {
        "scripts/hardware/power-status.py": {
            "summary": {"estimated_load_w": 240.0}},
        "scripts/hardware/thermal-oc-budget.py": {
            "thermal": {"verdict": "no-breach",
                        "hottest_cpu_c": 72.0, "hottest_gpu_c": 65.0}},
    }

    def fake_run_json(rel, args):
        return canned.get(rel)

    monkeypatch.setattr(w, "_run_json", fake_run_json)
    out = w.sample_signals()
    assert out["wattage_w"] == 240.0, (
        f"watcher failed to extract wattage from power-status: {out}")
    assert out["cpu_temp_c"] == 72.0, (
        f"watcher failed to extract cpu temp from thermal.hottest_cpu_c — "
        f"producer→consumer binding broken: {out}")
    assert out["gpu_temp_c"] == 65.0, (
        f"watcher failed to extract gpu temp from thermal.hottest_gpu_c — "
        f"producer→consumer binding broken: {out}")


def test_watcher_tolerates_missing_thermal_fields(monkeypatch):
    """Defence: a null/empty thermal object must leave temps None, not
    raise — the watcher is a best-effort recurrent probe."""
    w = _load_watcher()
    monkeypatch.setattr(
        w, "_run_json",
        lambda rel, args: {"thermal": {"hottest_cpu_c": None,
                                       "hottest_gpu_c": None}}
        if "thermal" in rel else None,
    )
    out = w.sample_signals()
    assert out["cpu_temp_c"] is None and out["gpu_temp_c"] is None
