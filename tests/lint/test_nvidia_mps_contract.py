"""R551 (E11.M14) — NVIDIA MPS controller contract lint.

Operator §1g (verbatim, sacrosanct):
  "Multi mode AI, multiple mode for the AI loadout and load-out switch"

The RTX PRO 6000 (Blackwell workstation SKU) does NOT ship MIG per
scripts/hardware/gpu-possibility-catalog.py — so MPS is the only
NVIDIA-blessed path to concurrently share each GPU across multiple
inference processes (pulse / logic-engine / oracle-core + assistant
+ ad-hoc) without round-robin context-switch overhead.

This lint pins R551's three-surface shape so a future "tidy-up" pass
can't silently drop the controller, the boot service, or the CLI verb:

  (a) scripts/hardware/nvidia-mps.py    — the controller
  (b) scripts/sovereign-osctl           — `nvidia-mps` verb dispatch
  (c) systemd/system/sovereign-nvidia-mps.service — boot-time apply
  (d) config/nvidia-mps.yaml.example    — policy template
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MPS_PY = REPO_ROOT / "scripts" / "hardware" / "nvidia-mps.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-nvidia-mps.service"
EX_YAML = REPO_ROOT / "config" / "nvidia-mps.yaml.example"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── Structural ──

def test_controller_script_exists():
    assert MPS_PY.is_file(), f"missing {MPS_PY}"


def test_controller_executable():
    assert os.access(MPS_PY, os.X_OK), f"{MPS_PY} not executable"


def test_controller_python3_shebang():
    assert _read(MPS_PY).startswith("#!/usr/bin/env python3")


def test_controller_documents_round_and_epic():
    body = _read(MPS_PY)
    assert "R551" in body, "missing R551 anchor"
    assert "E11.M14" in body, "missing E11.M14 anchor"
    assert "§1g" in body, "missing §1g operator anchor"


def test_systemd_unit_exists():
    assert UNIT.is_file(), f"missing {UNIT}"


def test_yaml_example_exists():
    assert EX_YAML.is_file(), f"missing {EX_YAML}"


# ── Verb surface ──

REQUIRED_VERBS = ("status", "show", "start", "stop",
                  "set-thread-pct", "policy", "apply")


def test_all_required_verbs_declared_in_argparse():
    body = _read(MPS_PY)
    for v in REQUIRED_VERBS:
        # argparse subparsers declare add_parser("verb") — match either
        # quote style and allow assignment to a local (e.g. s_pct).
        assert (f'add_parser("{v}")' in body) or (f"add_parser('{v}')" in body), (
            f"missing add_parser({v!r}) in {MPS_PY}"
        )


def test_osctl_dispatches_nvidia_mps_verb():
    body = _read(OSCTL)
    # Match the case-statement entry.
    assert re.search(r"^\s*nvidia-mps\)\s*$", body, re.MULTILINE), (
        f"sovereign-osctl missing `nvidia-mps)` dispatch entry"
    )
    assert "scripts/hardware/nvidia-mps.py" in body, (
        f"sovereign-osctl nvidia-mps verb does not call nvidia-mps.py"
    )


# ── Behavioral (no-nvidia-smi gracefulness) ──

def test_status_runs_without_nvidia_smi():
    """The controller must NOT crash when nvidia-smi is absent (CI
    container, dev workstation without NVIDIA). Status should report
    the absence, not raise."""
    r = subprocess.run(
        ["python3", str(MPS_PY), "status"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, (
        f"status returned rc={r.returncode}; stderr={r.stderr!r}"
    )
    assert "NVIDIA MPS status" in r.stdout, r.stdout
    # Either present (rare in CI) or absent (common) — both shapes valid.
    assert "nvidia-smi present" in r.stdout, r.stdout


def test_status_json_is_valid_json():
    import json
    r = subprocess.run(
        ["python3", str(MPS_PY), "status", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    for k in ("nvidia_smi_present", "mps_control_present",
              "pipe_dir", "log_dir", "daemon_running", "visible_gpus"):
        assert k in data, f"status JSON missing key {k!r}: {data}"


def test_start_without_nvidia_returns_2_not_traceback():
    """When nvidia-cuda-mps-control is absent, start must return rc=2
    (usage / unavailable) — never raise an uncaught traceback."""
    r = subprocess.run(
        ["python3", str(MPS_PY), "start"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    # rc=2 (unavailable) is the green path. rc=0 only legal if MPS is
    # actually installed AND was already running (extremely unlikely
    # in CI). Anything else (especially Python traceback) is a bug.
    assert r.returncode in (0, 2), (
        f"start rc={r.returncode}; stderr={r.stderr!r}"
    )
    assert "Traceback" not in r.stderr, (
        f"start emitted a Python traceback: {r.stderr}"
    )


# ── Systemd unit hardening (R171 lineage) ──

REQUIRED_UNIT_KEYS = (
    "ProtectSystem=strict",
    "NoNewPrivileges=true",
    "PrivateTmp=true",
    "ProtectKernelTunables=true",
    "ProtectKernelModules=true",
    "ProtectControlGroups=true",
)


def test_systemd_unit_has_r171_hardening():
    body = _read(UNIT)
    for key in REQUIRED_UNIT_KEYS:
        assert key in body, (
            f"sovereign-nvidia-mps.service missing R171 hardening key: {key}"
        )


def test_systemd_unit_calls_controller_with_apply():
    body = _read(UNIT)
    assert "nvidia-mps.py apply" in body, (
        "boot service must call `nvidia-mps.py apply <policy.yaml>`"
    )
    assert "ExecStop=" in body, (
        "boot service must declare ExecStop= (clean daemon shutdown)"
    )


# ── YAML example carries the keys parse_policy understands ──

REQUIRED_POLICY_KEYS = ("enabled", "pipe_dir", "log_dir")


def test_yaml_example_documents_required_keys():
    body = _read(EX_YAML)
    for k in REQUIRED_POLICY_KEYS:
        assert k in body, (
            f"config/nvidia-mps.yaml.example missing key: {k}"
        )


# ── Defense-in-depth: catalog states RTX PRO 6000 lacks MIG ──

def test_mps_rationale_acknowledges_no_mig_on_rtx_pro_6000():
    """The controller's docstring must explicitly tie its existence to
    the operator's hardware reality: RTX PRO 6000 has no MIG, so MPS
    is the only path. Catches a future agent silently 'tidying' the
    rationale away and adding MIG-mode that the hardware can't run."""
    body = _read(MPS_PY)
    assert "MIG" in body, "controller doesn't mention MIG context"
    assert "RTX PRO 6000" in body or "non-MIG" in body, (
        "controller doesn't tie its existence to non-MIG hardware"
    )
