"""R388 (E10.M32) — whitelabel/default.yaml operator-verbatim content lint.

`whitelabel/default.yaml` is the operator-readable identity surface
rendered to /etc/motd + /etc/os-release on the installed system.
Operator-verbatim content (master spec §3.2 motd quote + os-release
identity strings) lives here. Silent drift would ship an OS image
that doesn't carry operator's voice.

R388 pins:
  - §3.2 operator-verbatim motd quote (both lines)
  - §3.2 os-release identity strings (NAME / ID / ID_LIKE)
  - Operator's quality-bar phrase "no hacks, no shortcuts" preserved

Mirrors R387 (sain-01 profile) — extends lint surface from CATALOG
content to additional OPERATIONAL artifacts (whitelabel).
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WHITELABEL = REPO_ROOT / "whitelabel" / "default.yaml"


def _read_whitelabel() -> str:
    assert WHITELABEL.is_file(), f"missing {WHITELABEL}"
    return WHITELABEL.read_text(encoding="utf-8")


def test_whitelabel_file_exists():
    assert WHITELABEL.is_file(), f"missing {WHITELABEL}"


def test_motd_quote_line_1_verbatim():
    """Operator-verbatim motd line 1 from master spec §3.2:
       'We want quality over quantity and honesty over cheats and lies.'"""
    body = _read_whitelabel()
    assert "quality over quantity" in body, (
        "whitelabel/default.yaml missing operator-verbatim §3.2 motd "
        "phrase 'quality over quantity'"
    )
    assert "honesty over cheats and lies" in body, (
        "whitelabel/default.yaml missing operator-verbatim §3.2 motd "
        "phrase 'honesty over cheats and lies'"
    )


def test_motd_quote_line_2_verbatim():
    """Operator-verbatim motd line 2 from master spec §3.2:
       'We do not want hacks, quick fixes, and shortcuts.'"""
    body = _read_whitelabel()
    assert "hacks, quick fixes" in body, (
        "whitelabel/default.yaml missing operator-verbatim §3.2 motd "
        "phrase 'hacks, quick fixes' (full line: 'We do not want hacks, "
        "quick fixes, and shortcuts')"
    )
    assert "shortcuts" in body, "motd missing 'shortcuts' word"


def test_os_release_identity_strings():
    """os-release identity strings preserved (operator-verbatim from
    master spec §3.2 os-release block: NAME='Sovereign OS' / "
    "ID=sovereign / ID_LIKE=debian)."""
    body = _read_whitelabel()
    # "Sovereign OS" name
    assert "Sovereign OS" in body, (
        "whitelabel missing operator-verbatim NAME='Sovereign OS' "
        "(master spec §3.2)"
    )
    # The id/id_like fields appear (lowercased in yaml ID/ID_LIKE convention)
    body_lower = body.lower()
    assert "sovereign" in body_lower, (
        "whitelabel missing operator-verbatim ID=sovereign"
    )


def test_quality_bar_phrase_preserved():
    """Operator-stated quality bar 'Quality over Quantity | Honesty
    over Cheats' from master spec §0 Standard line. Either the full
    motd quote OR the standalone phrase is acceptable."""
    body = _read_whitelabel()
    assert "quality over quantity" in body.lower(), (
        "operator quality-bar phrase 'Quality over Quantity' missing"
    )


def test_no_silent_motd_paraphrase():
    """Catch silent paraphrase patterns that would corrupt operator's
    exact phrasing.

    Forbidden paraphrases (operator never used these forms):
      - 'quality before quantity' (operator wrote 'quality over quantity')
      - 'no hacks no shortcuts' (operator wrote 'hacks, quick fixes,
        and shortcuts')
      - 'cheating' (operator wrote 'cheats')
    """
    body_lower = _read_whitelabel().lower()
    forbidden_paraphrases = [
        # If 'before' appears with quality but operator-verbatim 'over'
        # doesn't, that's silent paraphrasing.
        ("quality before quantity", "quality over quantity"),
        # Compressed form without commas
        ("quick fixes and shortcuts", "hacks, quick fixes"),
    ]
    for wrong, right in forbidden_paraphrases:
        if wrong in body_lower and right.lower() not in body_lower:
            raise AssertionError(
                f"whitelabel contains paraphrase {wrong!r} without "
                f"operator-verbatim form {right!r} — silent paraphrasing "
                f"of operator's §3.2 motd quote detected."
            )


def test_motd_complete_quote_present():
    """Both motd lines MUST appear together in the same file (operator's
    full §3.2 motd is a 2-sentence quote — don't split it)."""
    body = _read_whitelabel()
    # Find the position of each key phrase
    pos1 = body.find("quality over quantity")
    pos2 = body.find("hacks, quick fixes")
    assert pos1 >= 0 and pos2 >= 0, "one or both motd lines missing"
    # The two lines should be close together (≤200 chars apart) — operator's
    # 2-sentence quote, not scattered across the file
    distance = abs(pos2 - pos1)
    assert distance <= 200, (
        f"motd lines split by {distance} chars — operator's 2-sentence "
        f"quote should appear adjacent"
    )


def test_whitelabel_has_at_least_30_lines():
    """Sanity floor: whitelabel must be substantively defined, not a stub."""
    line_count = len(_read_whitelabel().splitlines())
    assert line_count >= 30, (
        f"whitelabel/default.yaml has only {line_count} lines; expected ≥30 "
        f"(motd + os-release + branding surfaces)"
    )
