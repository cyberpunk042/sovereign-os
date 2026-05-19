"""R553 (E11.M16) — Transparent HugePage controller contract lint.

Orthogonal to R552: R552 reserves *static* hugepages; R553 controls
the *opportunistic* THP path. The `inference` policy preset
(enabled=madvise, defrag=defer) eliminates compaction-stall jitter
that breaks sustained-burst / peak-inference latency budgets.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
THP_PY = REPO_ROOT / "scripts" / "hardware" / "thp-mode.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_thp_mode_script_exists():
    assert THP_PY.is_file(), f"missing {THP_PY}"


def test_thp_mode_executable():
    assert os.access(THP_PY, os.X_OK), f"{THP_PY} not executable"


def test_thp_mode_python3_shebang():
    assert _read(THP_PY).startswith("#!/usr/bin/env python3")


def test_thp_mode_documents_round_epic_anchor():
    body = _read(THP_PY)
    assert "R553" in body, "missing R553"
    assert "E11.M16" in body, "missing E11.M16"
    assert "§1g" in body, "missing §1g operator anchor"


REQUIRED_VERBS = ("show", "status", "set", "set-defrag",
                  "policy", "list-policies")


def test_all_verbs_declared():
    body = _read(THP_PY)
    for v in REQUIRED_VERBS:
        assert (f'add_parser("{v}")' in body) or (f"add_parser('{v}')" in body), (
            f"missing add_parser({v!r})"
        )


def test_osctl_dispatches_thp_mode_verb():
    body = _read(OSCTL)
    assert re.search(r"^\s*thp-mode\)\s*$", body, re.MULTILINE), (
        "sovereign-osctl missing `thp-mode)` dispatch entry"
    )
    assert "scripts/hardware/thp-mode.py" in body, (
        "sovereign-osctl thp-mode verb does not call thp-mode.py"
    )


def test_show_runs_on_any_host():
    r = subprocess.run(
        ["python3", str(THP_PY), "show"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    assert "Transparent HugePage" in r.stdout, r.stdout
    assert "Traceback" not in r.stderr, r.stderr


def test_show_json_valid():
    r = subprocess.run(
        ["python3", str(THP_PY), "show", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    for k in ("thp_available", "enabled", "defrag", "policies"):
        assert k in data, f"missing {k}"


REQUIRED_POLICIES = ("inference", "bench", "aggressive")


def test_required_policies_present():
    r = subprocess.run(
        ["python3", str(THP_PY), "list-policies", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    for slug in REQUIRED_POLICIES:
        assert slug in data, f"policy {slug!r} missing"
        assert "enabled" in data[slug]
        assert "defrag" in data[slug]


def test_inference_policy_uses_madvise_defer():
    """inference policy MUST be enabled=madvise, defrag=defer — that's
    the latency-predictable preset. Any other config defeats R553's
    purpose."""
    r = subprocess.run(
        ["python3", str(THP_PY), "list-policies", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    data = json.loads(r.stdout)
    inf = data["inference"]
    assert inf["enabled"] == "madvise", inf
    assert inf["defrag"] == "defer", inf


def test_set_rejects_invalid_mode():
    r = subprocess.run(
        ["python3", str(THP_PY), "set", "weird"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr


def test_set_defrag_rejects_invalid_mode():
    r = subprocess.run(
        ["python3", str(THP_PY), "set-defrag", "weird"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr


def test_policy_rejects_unknown_slug():
    r = subprocess.run(
        ["python3", str(THP_PY), "policy", "nonexistent"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
