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
\tlinux  /casper/vmlinuz  --- quiet splash
\tinitrd\t/casper/initrd
}
menuentry "Ubuntu (safe graphics)" {
\tlinux  /casper/vmlinuz nomodeset  --- quiet splash
\tinitrd\t/casper/initrd
}
menuentry 'Boot from next volume' {
\texit 1
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
    assert "menuentry 'Boot from next volume'" in out and "autoinstall" not in out.split(
        "menuentry 'Boot from next volume'")[1], (
        "non-casper entries ('Boot from next volume', UEFI firmware settings) "
        "must be left exactly as Ubuntu shipped them"
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


def test_the_extracted_grub_cfg_is_made_writable_before_patching():
    """xorriso -osirrox preserves the ISO's permissions: the file lands 0444.

    Verified against the real Ubuntu 26.04 ISO (2026-07-29): the extracted
    grub.cfg is mode 444, so the patcher died with

        PermissionError: [Errno 13] Permission denied: '.../grub.cfg'

    AFTER the multi-GB remaster. A test fixture written by the test itself has
    normal permissions and can never reproduce this — only the real ISO does,
    which is exactly why the ISO was fetched before trusting any of this.
    """
    body = BUILD.read_text(encoding="utf-8")
    extract_at = body.index("-osirrox on -extract /boot/grub/grub.cfg")
    patch_at = body.index('python3 - "${GRUBCFG}"')
    chmod_at = body.find('chmod u+w "${GRUBCFG}"')
    assert chmod_at != -1, (
        "build.sh must chmod u+w the grub.cfg it extracts — xorriso gives it "
        "the ISO's read-only mode and the patcher cannot write it"
    )
    assert extract_at < chmod_at < patch_at, (
        "the chmod must sit between the extract and the patch"
    )


def test_the_patcher_fails_loudly_on_a_read_only_target(tmp_path: Path):
    """And if the chmod is ever lost, the failure must be visible, not silent."""
    script = tmp_path / "patch.py"
    script.write_text(patcher(), encoding="utf-8")
    target = tmp_path / "grub.cfg"
    target.write_text(CASPER_CFG, encoding="utf-8")
    target.chmod(0o444)                      # exactly what xorriso hands back
    try:
        r = subprocess.run([sys.executable, str(script), str(target)],
                           capture_output=True, text=True)
        assert r.returncode != 0, (
            "patching a read-only grub.cfg must fail the build, not appear to "
            "succeed while writing nothing"
        )
    finally:
        target.chmod(0o644)


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


def test_every_late_command_parses_as_a_command_string():
    """A bare `WORD: word` in unquoted YAML becomes a MAPPING, not a command.

    2026-07-29, caught by parsing the user-data off the BUILT ISO: the line

        - curtin in-target -- sh -c '... echo "SOVEREIGN WARNING: nomodeset ..."'

    parsed as a dict, so Subiquity would have received a mapping where it
    expects a command string. YAML-valid, silently wrong — the file loaded
    cleanly and the build reported success.
    """
    import yaml
    ud = (REPO_ROOT / "scripts" / "build" / "ubuntu-autoinstall"
          / "autoinstall" / "user-data")
    ai = yaml.safe_load(ud.read_text(encoding="utf-8"))["autoinstall"]
    for key in ("late-commands", "early-commands"):
        for i, cmd in enumerate(ai.get(key) or []):
            assert isinstance(cmd, str), (
                f"{key}[{i}] parsed as {type(cmd).__name__}, not a command string: "
                f"{cmd!r}\nAn unquoted YAML scalar containing ': ' becomes a "
                "mapping. Remove the colon or quote the whole entry."
            )


def test_the_packages_list_is_all_plain_strings():
    """Same trap, same file, different key."""
    import yaml
    ud = (REPO_ROOT / "scripts" / "build" / "ubuntu-autoinstall"
          / "autoinstall" / "user-data")
    ai = yaml.safe_load(ud.read_text(encoding="utf-8"))["autoinstall"]
    for i, p in enumerate(ai.get("packages") or []):
        assert isinstance(p, str) and p.strip(), (
            f"packages[{i}] is not a plain package name: {p!r}"
        )
