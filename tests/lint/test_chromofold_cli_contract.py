"""Contract for `sovereign-osctl chromofold` (SDD-500).

The read-only ChromoFold CLI (`scripts/inference/chromofold.py`) must:
  * exist, be executable, stdlib-only (no network, no third-party deps);
  * honest-degrade to an exit-0 offline *report* when no engine checkout is
    resident (never a fabricated capability — SB-077);
  * validate the reference-fixture header seam (4-byte magic + u32-LE version)
    against the resident engine's own capability descriptor, no GPU;
  * fail (exit 1) only when a resident fixture's header actually mismatches.
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "inference" / "chromofold.py"


def _run(args, root: str | None):
    env = {k: v for k, v in os.environ.items() if k not in ("CHROMOFOLD_ROOT", "WARP_SHADERS_ROOT")}
    if root is not None:
        env["CHROMOFOLD_ROOT"] = root
    return subprocess.run(
        ["python3", str(CLI), *args],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=20, check=False,
    )


def test_cli_exists_and_is_executable():
    assert CLI.is_file(), f"missing {CLI}"
    assert os.access(CLI, os.X_OK), f"{CLI} is not executable"


def test_cli_is_stdlib_only():
    src = CLI.read_text(encoding="utf-8")
    # no third-party import lines (a smoke check — the CLI must run air-gapped)
    for banned in ("import requests", "import yaml", "from requests", "import numpy"):
        assert banned not in src, f"{banned!r} — the chromofold CLI must be stdlib-only"


def test_info_offline_reports_and_exits_zero():
    r = _run(["info"], root=None)
    assert r.returncode == 0, f"offline info should exit 0, got {r.returncode}: {r.stderr}"
    assert "offline" in (r.stdout + r.stderr).lower()


def test_info_json_offline_is_machine_readable():
    r = _run(["info", "--json"], root=None)
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert payload["availability"] == "offline"
    assert payload["engine_root"] is None


def _make_engine(tmp: Path, version: int = 3, corrupt: bool = False) -> str:
    """A minimal resident engine root: capability.json + one reference fixture."""
    fixtures = tmp / "packaging" / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "tiny.cfwv").write_bytes(
        (b"XXXX" if corrupt else b"CFWV") + struct.pack("<I", version) + b"\x00" * 16
    )
    cap = {
        "abi_version": 0,
        "library": "libchromofold.so",
        "header_primary": "chromofold/chromofold.h",
        "header_search": "chromofold/chromofold_search.h",
        "capabilities": [
            {"id": "fm_count", "header": "chromofold_search.h", "fn": "cf_fm_count_async",
             "sovereign_os_first": True},
        ],
        "reference_fixtures": [
            {"ext": ".cfwv", "magic": "CFWV", "version": 3, "fixture": "packaging/fixtures/tiny.cfwv"},
        ],
    }
    (tmp / "packaging" / "chromofold_capability.json").write_text(json.dumps(cap))
    return str(tmp)


def test_selftest_resident_passes_on_matching_header(tmp_path):
    root = _make_engine(tmp_path)
    r = _run(["selftest"], root=root)
    assert r.returncode == 0, f"matching header should PASS: {r.stdout}{r.stderr}"
    assert "PASS" in r.stdout


def test_selftest_resident_fails_on_bad_magic(tmp_path):
    root = _make_engine(tmp_path, corrupt=True)
    r = _run(["selftest"], root=root)
    assert r.returncode == 1, "a mismatched fixture magic must FAIL (exit 1), not fabricate PASS"
    assert "FAIL" in (r.stdout + r.stderr)


def test_selftest_offline_is_not_a_failure(tmp_path):
    r = _run(["selftest"], root=None)
    assert r.returncode == 0, "offline selftest is honest-degrade, not a failure"
    assert "OFFLINE" in r.stdout or "offline" in r.stdout.lower()
