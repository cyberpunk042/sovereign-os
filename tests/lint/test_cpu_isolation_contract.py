"""R557 (E11.M20) — CPU isolation cmdline emitter contract lint.

Completes the inference-latency-hygiene OS-knob arc by adding the
trifecta — isolcpus / nohz_full / rcu_nocbs — that R554 IRQ pinning
alone cannot achieve. R557 ensures the three CPU sets always match
(the #1 operator footgun) and never edits GRUB directly.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "hardware" / "cpu-isolation.py"
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
    assert "R557" in body
    assert "E11.M20" in body
    assert "§1g" in body


def test_documents_sovereignty_boundary():
    """Script MUST NOT edit GRUB directly — that's the operator-
    signed sovereignty boundary established in R552."""
    body = _read(SCRIPT)
    assert "NEVER edit GRUB" in body or "never touches GRUB" in body or \
        "NEVER touches GRUB" in body, "missing sovereignty-boundary doc"


REQUIRED_VERBS = ("show", "status", "list-cpus", "recommend", "emit-cmdline")


def test_all_verbs_declared():
    body = _read(SCRIPT)
    for v in REQUIRED_VERBS:
        assert (f'add_parser("{v}")' in body) or (f"add_parser('{v}')" in body), v


def test_osctl_dispatches_verb():
    body = _read(OSCTL)
    assert re.search(r"^\s*cpu-isolation\)\s*$", body, re.MULTILINE)
    assert "scripts/hardware/cpu-isolation.py" in body


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
    for k in ("online_count", "online_list", "cmdline", "current"):
        assert k in data, k
    for k in ("isolcpus", "nohz_full", "rcu_nocbs"):
        assert k in data["current"], k


def test_list_cpus_runs():
    r = subprocess.run(
        ["python3", str(SCRIPT), "list-cpus", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["online_count"] >= 1


def test_recommend_trifecta_matches():
    """The three params MUST be identical sets — that's the whole
    point of R557."""
    r = subprocess.run(
        ["python3", str(SCRIPT), "recommend",
         "--inference-cpus", "2-3", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    if data.get("error"):
        # Host has too few CPUs; skip semantic check.
        return
    params = data["params"]
    assert params["isolcpus"] == params["nohz_full"] == params["rcu_nocbs"]
    # Fragment must contain all three keys.
    frag = data["cmdline_fragment"]
    for key in ("isolcpus=", "nohz_full=", "rcu_nocbs="):
        assert key in frag, key


def test_recommend_rejects_all_cpus():
    """Asking to isolate every online CPU must error — at least one
    CPU must remain for housekeeping."""
    r = subprocess.run(
        ["python3", str(SCRIPT), "recommend",
         "--inference-cpus", "0-99", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    # Either rc != 0 OR the JSON carries an error field.
    data = json.loads(r.stdout) if r.stdout.startswith("{") else {}
    assert r.returncode != 0 or "error" in data
    assert "Traceback" not in r.stderr


def test_recommend_rejects_bad_spec():
    r = subprocess.run(
        ["python3", str(SCRIPT), "recommend",
         "--inference-cpus", "not-a-cpu"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr


def test_recommend_rejects_offline_cpu():
    """Asking to isolate a CPU index that isn't online must error
    out, not silently include a non-existent CPU."""
    r = subprocess.run(
        ["python3", str(SCRIPT), "recommend",
         "--inference-cpus", "999", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    data = json.loads(r.stdout) if r.stdout.startswith("{") else {}
    assert data.get("error") or r.returncode != 0


def test_emit_cmdline_to_custom_target():
    """Emit to a tmpdir target — verifies the write path + content
    without needing root (default /etc path)."""
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "cpu-isolation.cmdline"
        r = subprocess.run(
            ["python3", str(SCRIPT), "emit-cmdline",
             "--inference-cpus", "1",
             "--target", str(target), "--json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        assert r.returncode == 0, r.stderr
        assert target.is_file()
        body = target.read_text()
        assert "isolcpus=1" in body
        assert "nohz_full=1" in body
        assert "rcu_nocbs=1" in body
        assert "R557" in body
