"""SDD-509 Phase C — break-glass recovery codes (lost-phone path) contract.

A batch of one-time recovery codes generated at enrollment, shown once, stored
as salted hashes. Each is a single-use fallback factor. Exercised deterministically.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STEPUP = REPO / "scripts" / "operator" / "lib" / "stepup.py"


def _load():
    spec = importlib.util.spec_from_file_location("stepup_bg", STEPUP)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_generate_returns_plaintext_batch_once(tmp_path):
    m = _load()
    codes = m.generate_break_glass(tmp_path, count=8)
    assert len(codes) == 8
    assert len(set(codes)) == 8, "codes must be unique"
    # readable format: three dash-separated groups, no ambiguous chars
    for c in codes:
        assert c.count("-") == 2
        assert all(ch in m._BREAK_GLASS_ALPHABET for ch in c.replace("-", ""))
    # plaintext is NOT persisted — only salted hashes
    stored = m.break_glass_path(tmp_path).read_text(encoding="utf-8")
    for c in codes:
        assert c not in stored


def test_remaining_counts_unused(tmp_path):
    m = _load()
    assert m.break_glass_remaining(tmp_path) == 0  # none generated
    codes = m.generate_break_glass(tmp_path, count=5)
    assert m.break_glass_remaining(tmp_path) == 5
    m.verify_break_glass_and_elevate(tmp_path, "operator", codes[0], now=1000.0)
    assert m.break_glass_remaining(tmp_path) == 4


def test_verify_single_use_and_elevates(tmp_path):
    m = _load()
    codes = m.generate_break_glass(tmp_path, count=3)
    now = 1000.0
    assert m.verify_break_glass_and_elevate(tmp_path, "operator", codes[1], now=now) is True
    # elevation minted
    assert m.ElevationStore(tmp_path / "elevations.json").check(
        "operator", "step-up", now=now + 1
    )
    # single-use — same code no longer works
    assert m.verify_break_glass_and_elevate(tmp_path, "operator", codes[1], now=now + 2) is False


def test_verify_is_format_insensitive(tmp_path):
    m = _load()
    codes = m.generate_break_glass(tmp_path, count=2)
    # typed lower-case, spaces instead of dashes, still verifies
    mangled = codes[0].lower().replace("-", " ")
    assert m.verify_break_glass_and_elevate(tmp_path, "operator", mangled, now=1000.0) is True


def test_verify_rejects_bad_and_unbatched(tmp_path):
    m = _load()
    # no batch generated → None (nothing to verify against)
    assert m.verify_break_glass_and_elevate(tmp_path, "operator", "AAAA-BBBB-CCCC") is None
    m.generate_break_glass(tmp_path, count=2)
    # wrong code → False, no elevation
    assert m.verify_break_glass_and_elevate(tmp_path, "operator", "ZZZZ-ZZZZ-ZZZZ", now=1000.0) is False
    assert not m.ElevationStore(tmp_path / "elevations.json").check("operator", "step-up", now=1000.0)


def test_regenerate_invalidates_prior_batch(tmp_path):
    m = _load()
    old = m.generate_break_glass(tmp_path, count=3)
    new = m.generate_break_glass(tmp_path, count=3)
    assert set(old).isdisjoint(set(new))
    # an old code no longer verifies after regeneration
    assert m.verify_break_glass_and_elevate(tmp_path, "operator", old[0], now=1000.0) is False
    assert m.verify_break_glass_and_elevate(tmp_path, "operator", new[0], now=1000.0) is True
