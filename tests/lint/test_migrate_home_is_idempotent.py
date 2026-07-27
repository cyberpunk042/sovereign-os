"""The already-migrated guard must fire, or /home is rsynced into itself.

2026-07-27. migrate-home.sh mounts the shared LV at a temp dir and rsyncs /home
into it. Its "already done" guard was:

    findmnt -no SOURCE /home | grep -q "$(readlink -f "${HOME_LV}")"

Both sides name the same device, in different spellings: `findmnt` reports
/dev/mapper/<vg>-<lv>, while `readlink -f /dev/<vg>/<lv>` yields /dev/dm-N. The
substring match between them fails, so on a machine where /home is ALREADY the
shared LV the guard does not fire — and the script mounts that LV a second time
and copies the filesystem into a subdirectory of itself.

Demonstrated with two symlinks to one file: substring match says NO MATCH,
resolved comparison says MATCH.

Everything else in that script was already careful: the source is only read,
rsync has no --delete, the copy is verified before unmounting, and an existing
/home line in fstab is left alone.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "install" / "migrate-home.sh"


def test_the_guard_compares_resolved_devices():
    body = SCRIPT.read_text(encoding="utf-8")
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    assert "_resolve" in code, (
        "the already-migrated guard must resolve BOTH sides; comparing "
        "findmnt's spelling against readlink's never matches for an LV"
    )
    assert 'grep -q "$(readlink -f "${HOME_LV}")"' not in code, (
        "the substring form is the bug this replaced"
    )


def test_resolved_comparison_beats_substring(tmp_path: Path):
    """Two spellings of one device: the old form misses, the new one matches."""
    dev = tmp_path / "dm-1"
    dev.write_text("", encoding="utf-8")
    a, b = tmp_path / "mapper-style", tmp_path / "lv-style"
    a.symlink_to(dev)
    b.symlink_to(dev)
    old = subprocess.run(
        ["bash", "-c", f'printf "%s" "{a}" | grep -q "$(readlink -f "{b}")"'],
        capture_output=True)
    new = subprocess.run(
        ["bash", "-c",
         f'_r() {{ readlink -f "$1"; }}; [ "$(_r "{a}")" = "$(_r "{b}")" ]'],
        capture_output=True)
    assert old.returncode != 0, "the old substring form unexpectedly matched"
    assert new.returncode == 0, "the resolved comparison failed to match"


def test_the_source_is_never_deleted():
    """rsync must not carry --delete, and nothing may rm the live /home."""
    code = "\n".join(l for l in SCRIPT.read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))
    assert "--delete" not in code, (
        "the migration copies; deleting from the source turns a reversible step "
        "into an irreversible one"
    )
    assert "rm -rf /home" not in code


def test_it_will_not_clobber_an_existing_fstab_entry():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "already has a /home entry" in body, (
        "an existing /home line in fstab must be left alone"
    )
