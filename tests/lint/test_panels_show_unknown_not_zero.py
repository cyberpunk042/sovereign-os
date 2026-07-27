"""A panel must not render "could not tell" as a confident number.

2026-07-27. Both APIs were fixed to distinguish a FAILED PROBE from a genuinely
empty result — and then neither panel rendered the distinction, so the fix was
invisible where it mattered:

  * flash panel: an lsblk failure and "nothing attached" both printed
    "no block devices found". Those call for opposite responses (investigate vs
    plug one in).
  * build panel: `Object.keys(units).length + " sovereign unit(s) installed"`
    printed "0 sovereign unit(s) installed" when systemctl had not answered at
    all — a confident zero standing in for no information.

Fixing an API without surfacing it is half a fix; the operator still reads the
same false statement.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FLASH = REPO_ROOT / "webapp" / "flash" / "index.html"
BUILD = REPO_ROOT / "webapp" / "build-configurator" / "index.html"


def inline_js(path: Path) -> str:
    html = path.read_text(encoding="utf-8")
    return "\n;\n".join(
        re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.DOTALL))


def test_the_flash_panel_distinguishes_probe_failure():
    js = inline_js(FLASH)
    assert "devices_probe_failed" in js, (
        "the flash panel must read the flag; without it an lsblk failure still "
        "renders as 'no block devices found'"
    )


def test_the_build_panel_does_not_report_zero_for_unknown():
    js = inline_js(BUILD)
    assert "units_probe_failed" in js, (
        "the build panel must read the flag; without it a failed systemctl "
        "renders as '0 sovereign unit(s) installed'"
    )
    # the count must be guarded by the flag, not printed unconditionally
    line = next((l for l in js.splitlines() if "sovereign unit(s) installed" in l), "")
    window = js[max(0, js.index("sovereign unit(s) installed") - 240):]
    assert "units_probe_failed" in window[:400], (
        f"the unit count is printed without consulting the flag: {line.strip()[:90]!r}"
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("panel", (FLASH, BUILD))
def test_the_panels_still_parse(panel: Path):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(inline_js(panel))
        path = f.name
    try:
        out = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        assert out.returncode == 0, f"{panel.name} JS does not parse:\n{out.stderr}"
    finally:
        Path(path).unlink()
