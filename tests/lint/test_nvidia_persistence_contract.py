"""R556 (E11.M19) — NVIDIA persistence mode controller contract lint.

Coda to the R551-R555 inference-latency-hygiene arc. Without
persistence mode, the NVIDIA driver tears down GPU state on the
exit of the last CUDA context, costing ~2s of re-init on the very
next first-prompt — squarely on the operator's perceived latency.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "hardware" / "nvidia-persistence.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_script_exists():
    assert SCRIPT.is_file()


def test_script_executable():
    assert os.access(SCRIPT, os.X_OK)


def test_python3_shebang():
    assert _read(SCRIPT).startswith("#!/usr/bin/env python3")


def test_documents_round_epic_anchor():
    body = _read(SCRIPT)
    assert "R556" in body
    assert "E11.M19" in body
    assert "§1g" in body


REQUIRED_VERBS = ("show", "status", "list-gpus", "enable", "disable")


def test_all_verbs_declared():
    body = _read(SCRIPT)
    for v in REQUIRED_VERBS:
        assert (f'add_parser("{v}")' in body) or (f"add_parser('{v}')" in body), v


def test_osctl_dispatches_verb():
    body = _read(OSCTL)
    assert re.search(r"^\s*nvidia-persistence\)\s*$", body, re.MULTILINE)
    assert "scripts/hardware/nvidia-persistence.py" in body


def test_show_runs_on_any_host():
    r = subprocess.run(
        ["python3", str(SCRIPT), "show"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr


def test_show_json_valid():
    r = subprocess.run(
        ["python3", str(SCRIPT), "show", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    for k in ("nvidia_smi_present", "persistenced_active", "gpus"):
        assert k in data, k


def test_list_gpus_runs():
    r = subprocess.run(
        ["python3", str(SCRIPT), "list-gpus", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "gpus" in data
    assert isinstance(data["gpus"], list)


def test_enable_requires_root_or_smi():
    """Without root the script must refuse cleanly (rc != 0,
    no traceback). On a host without nvidia-smi it also returns
    non-zero. Both branches must be exception-free."""
    r = subprocess.run(
        ["python3", str(SCRIPT), "enable"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr


def test_disable_requires_root_or_smi():
    r = subprocess.run(
        ["python3", str(SCRIPT), "disable"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr


def test_help_does_not_traceback():
    r = subprocess.run(
        ["python3", str(SCRIPT), "--help"],
        capture_output=True, text=True, check=False, timeout=5,
    )
    assert r.returncode == 0
    assert "Traceback" not in r.stderr
