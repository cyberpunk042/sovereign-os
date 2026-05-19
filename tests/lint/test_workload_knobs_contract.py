"""R555 (E11.M18) — workload-knobs umbrella contract lint.

Closes the inference-latency-hygiene OS-knob arc started by R551
(MPS), R552 (HugePages), R553 (THP), R554 (IRQ). Where R551-R554
ship four independent operator-callable primitives, R555 wires
them as ONE atomic per-mode bundle so flipping workload-mode is
a single verb, not four-command juggling.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOBS_PY = REPO_ROOT / "scripts" / "intelligence" / "workload-knobs.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_script_exists():
    assert KNOBS_PY.is_file()


def test_script_executable():
    assert os.access(KNOBS_PY, os.X_OK)


def test_python3_shebang():
    assert _read(KNOBS_PY).startswith("#!/usr/bin/env python3")


def test_documents_round_epic_anchor():
    body = _read(KNOBS_PY)
    assert "R555" in body
    assert "E11.M18" in body
    assert "§1g" in body


def test_references_underlying_controllers():
    body = _read(KNOBS_PY)
    for ref in ("nvidia-mps.py", "hugepages-sizer.py",
                "thp-mode.py", "irq-affinity.py", "workload-mode.py"):
        assert ref in body, ref


REQUIRED_VERBS = ("show", "status", "plan", "list-bundles", "apply")


def test_all_verbs_declared():
    body = _read(KNOBS_PY)
    for v in REQUIRED_VERBS:
        assert (f'add_parser("{v}")' in body) or (f"add_parser('{v}')" in body), v


def test_osctl_dispatches_verb():
    body = _read(OSCTL)
    assert re.search(r"^\s*workload-knobs\)\s*$", body, re.MULTILINE)
    assert "scripts/intelligence/workload-knobs.py" in body


def test_show_runs_on_any_host():
    r = subprocess.run(
        ["python3", str(KNOBS_PY), "show"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr


def test_show_json_valid():
    r = subprocess.run(
        ["python3", str(KNOBS_PY), "show", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    for k in ("round", "sdd_vector", "active_mode", "valid_modes"):
        assert k in data, k


REQUIRED_BUNDLES = ("idle", "inference-ready", "training", "oc-burst")


def test_all_four_workload_modes_have_bundles():
    r = subprocess.run(
        ["python3", str(KNOBS_PY), "list-bundles", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    for slug in REQUIRED_BUNDLES:
        assert slug in data, slug
        # Each bundle must cover all four R551-R554 axes.
        for axis in ("mps", "hugepages", "thp", "irq"):
            assert axis in data[slug], f"{slug}/{axis}"
        assert "rationale" in data[slug]


def test_inference_ready_bundle_uses_inference_thp_policy():
    """inference-ready mode MUST use the THP `inference` policy —
    that's the latency-predictable preset shipped in R553. Any other
    choice contradicts the bundle's stated purpose."""
    r = subprocess.run(
        ["python3", str(KNOBS_PY), "list-bundles", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    data = json.loads(r.stdout)
    inf = data["inference-ready"]
    assert inf["thp"]["action"] == "policy"
    assert inf["thp"]["args"] == ["inference"]


def test_inference_ready_pins_irq_to_housekeeping():
    """Without IRQ pinning the inference cores get preempted by NIC
    RX / NVMe completion / USB poll. inference-ready and training
    MUST both apply IRQ affinity."""
    r = subprocess.run(
        ["python3", str(KNOBS_PY), "list-bundles", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    data = json.loads(r.stdout)
    for mode in ("inference-ready", "training"):
        irq = data[mode]["irq"]
        assert irq["action"] == "apply", mode
        assert "housekeeping" in irq, mode


def test_plan_emits_bundle_for_known_mode():
    r = subprocess.run(
        ["python3", str(KNOBS_PY), "plan", "training", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["mode"] == "training"
    assert data["known"] is True
    for axis in ("mps", "hugepages", "thp", "irq"):
        assert axis in data


def test_plan_rejects_unknown_mode():
    r = subprocess.run(
        ["python3", str(KNOBS_PY), "plan", "nonexistent"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr


def test_apply_requires_triple_gate():
    """Bare `apply training` without --apply + --confirm-knob-set
    MUST refuse — fans out to four root-required mutators."""
    r = subprocess.run(
        ["python3", str(KNOBS_PY), "apply", "training"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr


def test_apply_rejects_unknown_mode_before_gate():
    r = subprocess.run(
        ["python3", str(KNOBS_PY), "apply", "nonexistent",
         "--apply", "--confirm-knob-set"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
