"""`grep -c ... | head -1` fails the whole step under `set -o pipefail`.

2026-07-28. Step 09 aborted a build that had SUCCEEDED — the ISO was produced,
all 59 packages verified, bootable BIOS+UEFI — on this line:

    _a="$(grep -c "^d-i ${_k}" "${_pd}/p" 2>/dev/null | head -1)"

`grep -c` PRINTS 0 and EXITS 1 when nothing matches. With pipefail the pipeline
adopts grep's status, the assignment fails, and `set -e` kills the step.

The two obvious spellings are both wrong:
    ... || echo 0        -> grep already printed 0, so the value becomes "0\\n0"
    ... | head -1        -> pipefail adopts grep's non-zero status

The correct form neutralises grep INSIDE the group, so head sees the 0 it
already printed and the pipeline succeeds:

    _a="$( { grep -c PATTERN FILE 2>/dev/null || true; } | head -1 )"; _a="${_a:-0}"

Both sites that counted preseed keys this way — step 09 and the flash guard —
had the same bug; only step 09 ran first.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SITES = ("scripts/build/09-image-verify.sh", "scripts/sovereign-osctl")


@pytest.mark.parametrize("rel", SITES)
def test_no_unguarded_grep_c_pipeline(rel: str):
    code = "\n".join(l for l in (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))
    bad = re.findall(r'\$\(\s*grep -c [^|]*\| *head', code)
    assert not bad, (
        f"{rel}: `$(grep -c ... | head)` adopts grep's non-zero status under "
        f"pipefail and aborts the step: {bad[:2]}"
    )


@pytest.mark.parametrize("rel", SITES)
def test_no_double_zero_form(rel: str):
    code = "\n".join(l for l in (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))
    # PER LINE. A file-wide check flagged `python3 -c ... || echo 0`, which is
    # correct — python prints nothing on failure, so a single 0 results. Only
    # grep -c pre-prints its own 0 (2026-07-28, my own lint).
    bad = [l.strip() for l in code.splitlines()
           if "grep -c" in l and "|| echo 0" in l]
    assert not bad, (
        f"{rel}: grep -c already prints 0; `|| echo 0` yields \"0\\n0\" and any "
        f"numeric use fails: {bad[:2]}"
    )


def test_the_correct_form_behaves_under_set_e():
    """Both branches, in a shell configured exactly like the real scripts."""
    script = '''set -euo pipefail
        a="$( { grep -c "no-such-pattern" /etc/hostname 2>/dev/null || true; } | head -1 )"; a="${a:-0}"
        b="$( { grep -c "." /etc/hostname 2>/dev/null || true; } | head -1 )"; b="${b:-0}"
        printf "%s %s" "$a" "$b"'''
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert out.returncode == 0, f"the guarded form still aborts: {out.stderr}"
    no_match, match = out.stdout.split()
    assert no_match == "0", f"no-match should count 0, got {no_match!r}"
    assert int(match) >= 1, f"match should count >=1, got {match!r}"


def test_the_naive_form_really_does_abort():
    """Demonstrate the failure, so this lint's premise is not folklore."""
    out = subprocess.run(
        ["bash", "-c", 'set -euo pipefail\n'
                       'a="$(grep -c "no-such" /etc/hostname 2>/dev/null | head -1)"\n'
                       'echo REACHED'],
        capture_output=True, text=True)
    assert "REACHED" not in out.stdout, (
        "expected the naive form to abort under set -e + pipefail"
    )
