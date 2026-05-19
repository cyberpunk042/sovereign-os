"""R554 (E11.M17) — IRQ affinity controller contract lint.

Completes the inference-latency-hygiene OS-knob arc started by R551
(MPS), R552 (HugePages), R553 (THP). Hardware interrupts on
inference cores cost ~5-10 µs each plus L1 cache trashing — fatal
for sub-millisecond synchronous decode budgets.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
IRQ_PY = REPO_ROOT / "scripts" / "hardware" / "irq-affinity.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_script_exists():
    assert IRQ_PY.is_file()


def test_script_executable():
    assert os.access(IRQ_PY, os.X_OK)


def test_python3_shebang():
    assert _read(IRQ_PY).startswith("#!/usr/bin/env python3")


def test_documents_round_epic_anchor():
    body = _read(IRQ_PY)
    assert "R554" in body
    assert "E11.M17" in body
    assert "§1g" in body


REQUIRED_VERBS = ("show", "status", "list-irqs", "recommend", "apply")


def test_all_verbs_declared():
    body = _read(IRQ_PY)
    for v in REQUIRED_VERBS:
        assert (f'add_parser("{v}")' in body) or (f"add_parser('{v}')" in body), v


def test_osctl_dispatches_verb():
    body = _read(OSCTL)
    assert re.search(r"^\s*irq-affinity\)\s*$", body, re.MULTILINE)
    assert "scripts/hardware/irq-affinity.py" in body


def test_show_runs_on_any_host():
    r = subprocess.run(
        ["python3", str(IRQ_PY), "show"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr


def test_show_json_valid():
    r = subprocess.run(
        ["python3", str(IRQ_PY), "show", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "proc_irq_present" in data
    assert "irqs" in data


def test_recommend_with_housekeeping_cpus():
    r = subprocess.run(
        ["python3", str(IRQ_PY), "recommend",
         "--housekeeping-cpus", "0-1", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    if data["proc_irq_present"]:
        assert data["housekeeping_cpus"] == [0, 1]
        assert data["housekeeping_list"] == "0-1"
        assert "plan" in data
        assert "noop_count" in data
        assert "change_count" in data


def test_recommend_requires_housekeeping_cpus():
    r = subprocess.run(
        ["python3", str(IRQ_PY), "recommend"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr


def test_apply_requires_housekeeping_cpus():
    r = subprocess.run(
        ["python3", str(IRQ_PY), "apply"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr


def test_cpu_list_parser_roundtrip_via_recommend():
    """The CPU list '0,2-4,7' must parse and re-render compactly."""
    r = subprocess.run(
        ["python3", str(IRQ_PY), "recommend",
         "--housekeeping-cpus", "0,2-4,7", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    if data["proc_irq_present"]:
        assert data["housekeeping_cpus"] == [0, 2, 3, 4, 7]
        assert data["housekeeping_list"] == "0,2-4,7"


def test_recommend_bad_cpu_spec_rejected():
    r = subprocess.run(
        ["python3", str(IRQ_PY), "recommend",
         "--housekeeping-cpus", "not-a-cpu", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
