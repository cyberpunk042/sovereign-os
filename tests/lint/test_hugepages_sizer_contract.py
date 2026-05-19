"""R552 (E11.M15) — HugePages sizer contract lint.

Operator §1g (verbatim, sacrosanct):
  "AVX-512 + 256GB RAM"  /  "Wasm-to-AVX-512 AOT"
  "1-bit / ternary models in ZMM"

Inference engines (llama.cpp / vllm / bitnet) cut TLB pressure 512×
when their weight tensors land in 2MiB hugepages — measured 5-15%
throughput gain on CPU-side decode. 1GiB gigantic pages eliminate
TLB walks entirely for static weight regions but must be reserved
at boot via kernel cmdline (post-boot 1GiB allocation fails — no
contiguous physical region remains).

This lint pins R552's four-surface shape:

  (a) scripts/hardware/hugepages-sizer.py
  (b) scripts/sovereign-osctl   — `hugepages` verb dispatch
  (c) systemd/system/sovereign-hugepages-sizer.service
  (d) /etc/sovereign-os/hugepages.target-gb  (operator-set int)
      — checked indirectly via the systemd unit's ConditionPathExists.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIZER_PY = REPO_ROOT / "scripts" / "hardware" / "hugepages-sizer.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-hugepages-sizer.service"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── Structural ──

def test_sizer_script_exists():
    assert SIZER_PY.is_file(), f"missing {SIZER_PY}"


def test_sizer_executable():
    assert os.access(SIZER_PY, os.X_OK), f"{SIZER_PY} not executable"


def test_sizer_python3_shebang():
    assert _read(SIZER_PY).startswith("#!/usr/bin/env python3")


def test_sizer_documents_round_and_epic():
    body = _read(SIZER_PY)
    assert "R552" in body, "missing R552 anchor"
    assert "E11.M15" in body, "missing E11.M15 anchor"
    assert "§1g" in body, "missing §1g operator anchor"


def test_systemd_unit_exists():
    assert UNIT.is_file(), f"missing {UNIT}"


# ── Verb surface ──

REQUIRED_VERBS = ("show", "status", "recommend", "apply")


def test_all_required_verbs_declared_in_argparse():
    body = _read(SIZER_PY)
    for v in REQUIRED_VERBS:
        assert (f'add_parser("{v}")' in body) or (f"add_parser('{v}')" in body), (
            f"missing add_parser({v!r}) in {SIZER_PY}"
        )


def test_osctl_dispatches_hugepages_verb():
    body = _read(OSCTL)
    assert re.search(r"^\s*hugepages\)\s*$", body, re.MULTILINE), (
        "sovereign-osctl missing `hugepages)` dispatch entry"
    )
    assert "scripts/hardware/hugepages-sizer.py" in body, (
        "sovereign-osctl hugepages verb does not call hugepages-sizer.py"
    )


# ── Behavioral ──

def test_show_runs_on_any_host():
    """show must succeed on any host — including ones without
    HugePages in the kernel — never raise."""
    r = subprocess.run(
        ["python3", str(SIZER_PY), "show"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, (
        f"show rc={r.returncode}; stderr={r.stderr!r}"
    )
    assert "HugePages state" in r.stdout, r.stdout
    assert "Traceback" not in r.stderr, r.stderr


def test_show_json_is_valid_json():
    r = subprocess.run(
        ["python3", str(SIZER_PY), "show", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    for k in ("mem_total_kb", "per_size", "persist_path",
              "gigantic_cmdline_path"):
        assert k in data, f"show JSON missing key {k!r}: {data}"


def test_recommend_target_64gb_returns_a_count():
    r = subprocess.run(
        ["python3", str(SIZER_PY), "recommend",
         "--target-gb", "64", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["page_size_kb"] == 2048, data
    assert data["nr_pages"] > 0, data
    assert data["target_gb"] == 64, data


def test_recommend_gigantic_target_8gb():
    r = subprocess.run(
        ["python3", str(SIZER_PY), "recommend",
         "--target-gb", "8", "--gigantic", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["page_size_kb"] == 1048576, data
    # 8 GiB / 1 GiB = 8 pages (modulo OS-RAM cap)
    assert data["nr_pages"] >= 1, data


def test_recommend_oversize_caps_with_warning():
    """target larger than total RAM must trigger a cap warning and
    return a smaller-than-asked nr_pages — never OOM-bomb the host."""
    r = subprocess.run(
        ["python3", str(SIZER_PY), "recommend",
         "--target-gb", "999999", "--json"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["warnings"], "expected cap-warning for 999999 GiB target"
    assert any("75%" in w for w in data["warnings"]), data["warnings"]


def test_recommend_requires_target_gb():
    """recommend without --target-gb must usage-error, not Python-crash."""
    r = subprocess.run(
        ["python3", str(SIZER_PY), "recommend"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode != 0
    assert "Traceback" not in r.stderr, r.stderr


# ── Systemd hardening ──

REQUIRED_UNIT_KEYS = (
    "NoNewPrivileges=true",
    "PrivateTmp=true",
    "ProtectKernelModules=true",
    "ProtectControlGroups=true",
)


def test_systemd_unit_has_r171_hardening():
    body = _read(UNIT)
    for key in REQUIRED_UNIT_KEYS:
        assert key in body, (
            f"sovereign-hugepages-sizer.service missing R171 key: {key}"
        )


def test_systemd_unit_runs_before_inference_services():
    """Hugepages must be reserved BEFORE pulse/logic-engine/oracle-core
    start — otherwise inference engines mmap normal-pages and the
    reservation is wasted."""
    body = _read(UNIT)
    assert "Before=" in body, "missing Before= ordering"
    assert "sovereign-pulse" in body, (
        "Before= must list sovereign-pulse.service"
    )
    assert "sovereign-logic-engine" in body, (
        "Before= must list sovereign-logic-engine.service"
    )
    assert "sovereign-oracle-core" in body, (
        "Before= must list sovereign-oracle-core.service"
    )


def test_systemd_unit_reads_target_from_etc_file():
    """Unit must read /etc/sovereign-os/hugepages.target-gb (the
    operator-set integer). Catches a future refactor that hardcodes
    a target in the unit itself."""
    body = _read(UNIT)
    assert "/etc/sovereign-os/hugepages.target-gb" in body, (
        "unit doesn't reference operator-set target file"
    )
    assert "ConditionPathExists=" in body, (
        "unit missing ConditionPathExists guard"
    )


# ── Defense-in-depth rationale ──

def test_sizer_docstring_explains_gigantic_boot_constraint():
    """Gigantic 1GiB pages MUST be reserved at boot via kernel cmdline
    — post-boot allocation fails. The docstring must surface this so
    operators don't try `apply --gigantic` and wonder why it doesn't
    take effect."""
    body = _read(SIZER_PY)
    assert "gigantic" in body.lower() and "boot" in body.lower(), (
        "docstring must explain gigantic pages need boot-time reservation"
    )
