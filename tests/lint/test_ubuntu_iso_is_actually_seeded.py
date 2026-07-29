"""The remastered Ubuntu ISO must really be seeded, not just claim to be.

2026-07-28. `ubuntu-autoinstall/build.sh` patches the ISO's grub.cfg to add
`autoinstall ds=nocloud;s=/cdrom/autoinstall/`. Its first version appended to the
END of the kernel line — i.e. AFTER casper's `---` separator, which divides
kernel parameters from what is handed on to init. That is not where Subiquity
looks. The ISO would have booted straight into a fully interactive install while
the build log said "entries seeded", and nobody would have known until the
operator sat in front of it.

Caught by running the patcher against a realistic casper grub.cfg BEFORE any ISO
was ever built. These tests EXECUTE the shipped code rather than grepping it, so
the behaviour is what is asserted.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "scripts" / "build" / "ubuntu-autoinstall" / "build.sh"

# A realistic Ubuntu live ISO grub.cfg: two casper entries (one "safe graphics"
# with its own kernel arg) and one non-casper entry that must stay untouched.
CASPER_CFG = """\
set timeout=30
menuentry "Try or Install Ubuntu" {
\tset gfxpayload=keep
\tlinux\t/casper/vmlinuz  ---
\tinitrd\t/casper/initrd
}
menuentry "Ubuntu (safe graphics)" {
\tlinux\t/casper/vmlinuz  nomodeset ---
\tinitrd\t/casper/initrd
}
menuentry "Test memory" {
\tlinux16 /boot/memtest86+.bin
}
"""


def patcher() -> str:
    """The inline python heredoc that build.sh runs on grub.cfg."""
    text = BUILD.read_text(encoding="utf-8")
    m = re.search(r"^python3 - \"\$\{GRUBCFG\}\" <<'PY'\n(.*?)\n^PY$",
                  text, re.S | re.M)
    assert m, "could not find the grub.cfg patcher in ubuntu-autoinstall/build.sh"
    return m.group(1)


def run_patcher(tmp_path: Path, cfg: str):
    script = tmp_path / "patch.py"
    script.write_text(patcher(), encoding="utf-8")
    target = tmp_path / "grub.cfg"
    target.write_text(cfg, encoding="utf-8")
    r = subprocess.run([sys.executable, str(script), str(target)],
                       capture_output=True, text=True)
    return r, target.read_text(encoding="utf-8")


def test_the_autoinstall_arg_lands_before_caspers_separator(tmp_path: Path):
    r, out = run_patcher(tmp_path, CASPER_CFG)
    assert r.returncode == 0, r.stderr
    for line in out.splitlines():
        if "/casper/vmlinuz" not in line:
            continue
        assert "autoinstall" in line, f"casper entry not seeded: {line!r}"
        assert line.index("autoinstall") < line.index("---"), (
            f"autoinstall landed AFTER casper's `---` separator: {line!r}. "
            "Subiquity does not read it there; the ISO would boot fully "
            "interactive while the build claimed it was seeded."
        )


def test_every_casper_entry_is_seeded_and_nothing_else_is_touched(tmp_path: Path):
    r, out = run_patcher(tmp_path, CASPER_CFG)
    assert r.returncode == 0, r.stderr
    assert out.count("autoinstall ds=nocloud") == 2, (
        "both casper entries must be seeded — an operator who picks 'safe "
        "graphics' from the menu must get the same seeded install"
    )
    assert "linux16 /boot/memtest86+.bin" in out, (
        "non-casper entries (memtest, firmware settings) must be left exactly "
        "as Ubuntu shipped them"
    )


def test_patching_twice_does_not_double_the_argument(tmp_path: Path):
    """Builders get re-run; a doubled cmdline arg is a broken boot."""
    r1, _ = run_patcher(tmp_path, CASPER_CFG)
    assert r1.returncode == 0
    once = (tmp_path / "grub.cfg").read_text(encoding="utf-8")
    r2, twice = run_patcher(tmp_path, once)
    assert r2.returncode == 0, r2.stderr
    assert twice.count("autoinstall ds=nocloud") == 2, (
        "re-patching an already-patched grub.cfg must be a no-op"
    )


def test_it_refuses_an_iso_whose_layout_it_does_not_recognise(tmp_path: Path):
    """Silence is the enemy: no casper entries means we cannot seed it.

    Writing the file back unchanged and reporting success would ship an
    installer that ignores the answer file entirely — the 2026-07-26 shape
    (a build that 'succeeded' and produced the wrong artifact).
    """
    r, _ = run_patcher(tmp_path, 'menuentry "x" {\n\tlinux /boot/vmlinuz\n}\n')
    assert r.returncode != 0, (
        "a grub.cfg with no /casper/vmlinuz entries must FAIL the build, not "
        "silently produce an unseeded ISO"
    )
    assert "refusing" in (r.stderr + r.stdout).lower()


def test_the_seed_directory_carries_a_meta_data_file():
    """cloud-init's NoCloud datasource needs meta-data to exist, even empty.

    Without it the seed is ignored and Subiquity falls through to a fully
    interactive install with no explanation.
    """
    body = BUILD.read_text(encoding="utf-8")
    assert re.search(r":\s*>\s*\"\$\{AI\}/meta-data\"", body), (
        "build.sh must create an (empty) meta-data beside user-data"
    )


def test_the_answer_file_is_validated_before_the_expensive_repack():
    body = BUILD.read_text(encoding="utf-8")
    assert "yaml.safe_load" in body, (
        "build.sh must parse user-data before remastering — failing after a "
        "multi-GB xorriso run wastes the operator's time on a typo"
    )
