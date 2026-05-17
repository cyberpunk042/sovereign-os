"""R320 (E9.M4 closure) — SDD Epic/Module cross-link audit.

Operator-named (§1b mandate row, verbatim): "Cross-link Epic/Module
IDs into SDD-029 + future SDDs". E9.M4 was partial (R264 SDD-029
established the pattern); this audit closes the doctrine by L1-
linting that every SDD created from SDD-029 onward carries the
cross-link to its mandate Epic/Module ID.

Doctrine pattern (set by R264 SDD-029 + R283 SDD-030):

  # SDD-NNN — <title> (E<n>.M<n> / R<round>)

  > Status: <state>
  > Owner: <team>
  > Closes findings: <Epic.Module> (mandate decomposition)
  > Derived from: §<n> of operator mandate ...

OR the cross-link may appear in the body:

  ## SDD-NNN ... derived from E<n>.M<n> (R<round>).

This lint walks docs/sdd/*.md AND verifies:
  - SDDs numbered ≥029 carry either (1) "Closes findings:" line OR
    (2) E<n>.M<n> reference in title OR (3) E<n>.M<n> reference in
    first ~30 lines.
  - SDDs numbered <029 are exempt (predate the doctrine).

Failures land as test failures listing the missing-cross-link
files. Operator runs `pytest tests/lint/test_sdd_cross_links.py -v`
to audit.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_DIR = REPO_ROOT / "docs" / "sdd"

# Doctrine starts at SDD-029 per R264.
DOCTRINE_FLOOR = 29

# Regex for E<digit>.M<digit> reference (e.g., E5.M11 / E1.M38).
EPIC_MODULE_RE = re.compile(r"\bE\d+\.M\d+\b")
# Regex for "Closes findings:" line.
CLOSES_RE = re.compile(r"^\s*>\s*Closes findings:\s*\S+", re.MULTILINE)


def _sdd_files() -> list[Path]:
    if not SDD_DIR.is_dir():
        return []
    return sorted(p for p in SDD_DIR.iterdir()
                  if p.is_file() and p.suffix == ".md")


def _sdd_number(path: Path) -> int | None:
    """Extract SDD number from filename like '030-operator-overlay-doctrine.md'."""
    m = re.match(r"^(\d{3})-", path.name)
    if m:
        return int(m.group(1))
    return None


def _has_cross_link(body: str) -> bool:
    """True iff body has either Closes-findings line or E<n>.M<n> ref
    in first ~30 lines."""
    if CLOSES_RE.search(body):
        return True
    first_30 = "\n".join(body.splitlines()[:30])
    if EPIC_MODULE_RE.search(first_30):
        return True
    return False


def test_sdd_dir_exists():
    """SDD dir must be present (this entire lint is a no-op otherwise)."""
    assert SDD_DIR.is_dir(), f"missing {SDD_DIR}"


def test_doctrine_floor_sdd_present():
    """SDD-029 must exist (R264 doctrine establishment round)."""
    by_num = {_sdd_number(p): p for p in _sdd_files() if _sdd_number(p)}
    assert DOCTRINE_FLOOR in by_num, (
        f"SDD-{DOCTRINE_FLOOR:03d} (doctrine floor) missing"
    )


def test_all_post_doctrine_sdds_carry_cross_link():
    """Every SDD numbered ≥DOCTRINE_FLOOR (29) must carry a mandate
    cross-link. Older SDDs are exempt."""
    missing = []
    for path in _sdd_files():
        n = _sdd_number(path)
        if n is None or n < DOCTRINE_FLOOR:
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as e:
            missing.append(f"{path.name}: read failed: {e}")
            continue
        if not _has_cross_link(body):
            missing.append(path.name)
    assert not missing, (
        f"R320 (E9.M4) SDD cross-link audit FAILED — {len(missing)} "
        f"SDDs are missing their Epic/Module cross-link "
        f"(SDDs ≥{DOCTRINE_FLOOR:03d} must carry one):\n  "
        + "\n  ".join(missing)
    )


def test_doctrine_pattern_recognizes_closes_findings():
    """Unit: _has_cross_link recognizes 'Closes findings:' line."""
    body = "# SDD-099 — Test\n\n> Closes findings: E9.M99 (mandate)\n"
    assert _has_cross_link(body)


def test_doctrine_pattern_recognizes_inline_epic_module():
    """Unit: _has_cross_link recognizes inline E<n>.M<n> in first lines."""
    body = "# SDD-099 — Test (E9.M99 / R999)\n"
    assert _has_cross_link(body)


def test_doctrine_pattern_rejects_no_cross_link():
    """Unit: _has_cross_link returns False for SDDs with no link."""
    body = "# SDD-099 — Test\n\n> Status: draft\n\nNo cross-link here.\n"
    assert not _has_cross_link(body)


def test_doctrine_floor_exempts_old_sdds():
    """Unit: SDDs numbered <29 are exempt — they predate R264."""
    # 028 is exempt; 029 + is gated.
    assert DOCTRINE_FLOOR == 29  # locked in this round


def test_at_least_one_post_doctrine_sdd_present():
    """Smoke: post-doctrine SDDs (≥029) should exist, otherwise the
    audit is vacuous. R264 + R283 give us SDD-029 + SDD-030 at minimum."""
    nums = [_sdd_number(p) for p in _sdd_files()]
    post = [n for n in nums if n is not None and n >= DOCTRINE_FLOOR]
    assert len(post) >= 2, (
        f"expected ≥2 post-doctrine SDDs (SDD-029 + SDD-030 minimum); "
        f"found {len(post)}"
    )
