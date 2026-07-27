"""Pinning the custom kernel must target the menuentry ID, not its title.

2026-07-26. A sovereign-os desktop install ends up with BOTH the custom znver5
kernel (linux-image-6.12.0) and the stock Debian kernel (6.12.96+deb13, dragged
in by task-kde-desktop). GRUB sorts by version, and 6.12.96 sorts ABOVE 6.12.0,
so without pinning the box boots the stock kernel and the whole custom-kernel
build is wasted.

set-grub-default-kernel.sh existed to fix that, and read the wrong awk field:

    -F"'"   $1 "menuentry "  $2 <title>  $3 " ... $menuentry_id_option "  $4 <id>

It printed $2 -- "Debian GNU/Linux, with Linux 6.12.0", commas and all -- and
passed that to grub-set-default, while its own comment said to target the id.

The version is also interpolated into an awk REGEX, where '.' matches any
character: an unescaped "6.12.0" can match versions it was never meant to.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "install" / "set-grub-default-kernel.sh"

MOCK = textwrap.dedent("""\
    menuentry 'Debian GNU/Linux, with Linux 6.12.96+deb13-amd64' --class debian $menuentry_id_option 'gnulinux-6.12.96+deb13-amd64-advanced-ede2be49' {
    menuentry 'Debian GNU/Linux, with Linux 6.12.0' --class debian $menuentry_id_option 'gnulinux-6.12.0-advanced-ede2be49' {
    menuentry 'Debian GNU/Linux, with Linux 6.12.0 (recovery mode)' --class debian $menuentry_id_option 'gnulinux-6.12.0-recovery-ede2be49' {
    """)


def test_it_extracts_an_id_not_a_title(tmp_path: Path):
    """Run the script's own extraction against a realistic grub.cfg."""
    cfg = tmp_path / "grub.cfg"
    cfg.write_text(MOCK, encoding="utf-8")
    body = SCRIPT.read_text(encoding="utf-8")
    awk_line = next(l for l in body.splitlines() if l.startswith("id=$(awk"))
    esc_line = next(l for l in body.splitlines() if l.startswith("KVER_RE="))
    script = f'KVER=6.12.0\nGRUBCFG="{cfg}"\n{esc_line}\n{awk_line}\nprintf %s "$id"\n'
    out = subprocess.run(["sh", "-c", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    got = out.stdout.strip()
    assert got == "gnulinux-6.12.0-advanced-ede2be49", (
        f"expected the menuentry id, got {got!r} — a title cannot be relied on "
        "as a grub-set-default target"
    )
    assert "menuentry" not in got and "," not in got


def test_the_version_is_escaped_before_going_into_a_regex():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "KVER_RE" in body, (
        "the kernel version is interpolated into an awk regex where '.' is a "
        "wildcard; escape it before matching"
    )


def test_the_installer_actually_calls_it():
    """A pin that is never invoked pins nothing."""
    for name in ("default.preseed", "sovereign.preseed"):
        text = (REPO_ROOT / "scripts" / "build" / "installer-cdd"
                / "profiles" / name).read_text(encoding="utf-8")
        assert "set-grub-default-kernel.sh" in text, (
            f"{name} must pin the custom kernel, or the install boots the stock "
            "Debian kernel that task-kde-desktop drags in"
        )
