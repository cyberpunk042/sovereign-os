"""SDD-509 Phase A — step-up MFA primitives contract + RFC 6238 known-answer.

Pins the pure step-up core (scripts/operator/lib/stepup.py): the TOTP verifier
against the RFC 6238 Appendix B test vectors, the auth-tier resolution, and the
short-TTL single-use elevation store. No exec-rail wiring here (that lands with
its own contract); this proves the crypto + logic in isolation.
"""
from __future__ import annotations

import base64
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "scripts" / "operator" / "lib" / "stepup.py"


def _load():
    spec = importlib.util.spec_from_file_location("stepup", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# RFC 6238 Appendix B: secret = ASCII "12345678901234567890", SHA1, T0=0, X=30.
_RFC_SECRET_B32 = base64.b32encode(b"12345678901234567890").decode("ascii").rstrip("=")
# (epoch seconds, 8-digit TOTP) from the RFC table; we assert the 6-digit tail.
_RFC_VECTORS = [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
]


def test_totp_matches_rfc6238_vectors():
    m = _load()
    for t, eight in _RFC_VECTORS:
        want6 = eight[-6:]
        got = m.totp_code(_RFC_SECRET_B32, t, digits=6, algo="sha1")
        assert got == want6, f"t={t}: got {got}, want {want6}"


def test_totp_verify_accepts_current_and_rejects_wrong():
    m = _load()
    t = 1111111109
    assert m.totp_verify(_RFC_SECRET_B32, "081804", t, skew=0)
    assert not m.totp_verify(_RFC_SECRET_B32, "000000", t, skew=0)
    # non-numeric / wrong-length are rejected, never crash
    assert not m.totp_verify(_RFC_SECRET_B32, "abc", t)
    assert not m.totp_verify(_RFC_SECRET_B32, "1234567", t)
    assert not m.totp_verify(_RFC_SECRET_B32, "", t)


def test_totp_skew_window():
    m = _load()
    t = 1111111109
    prev = m.totp_code(_RFC_SECRET_B32, t - 30)
    nxt = m.totp_code(_RFC_SECRET_B32, t + 30)
    assert m.totp_verify(_RFC_SECRET_B32, prev, t, skew=1)
    assert m.totp_verify(_RFC_SECRET_B32, nxt, t, skew=1)
    # outside the window with skew=1
    assert not m.totp_verify(_RFC_SECRET_B32, m.totp_code(_RFC_SECRET_B32, t - 90), t, skew=1)


def test_new_secret_and_provisioning_uri_round_trip():
    m = _load()
    secret = m.new_totp_secret()
    # a freshly minted secret produces a code its own verifier accepts
    code = m.totp_code(secret, 1000.0)
    assert m.totp_verify(secret, code, 1000.0, skew=0)
    uri = m.provisioning_uri(secret, account="operator@sain-01")
    assert uri.startswith("otpauth://totp/")
    assert f"secret={secret}" in uri and "issuer=sovereign-os" in uri


def test_resolve_tier():
    m = _load()
    assert m.resolve_tier({"id": "os-profile", "auth": "step-up"}) == "step-up"
    # explicit wins over privileged
    assert m.resolve_tier({"id": "x", "auth": "operator-present", "privileged": True}) == "operator-present"
    # derived from privileged when no explicit auth
    assert m.resolve_tier({"id": "x", "privileged": True}) == "step-up"
    assert m.resolve_tier({"id": "x", "privileged": False}) == "none"
    # selfdef/perimeter are always proxy-only
    assert m.resolve_tier({"id": "selfdef", "privileged": True}) == "proxy-only"
    assert m.resolve_tier({"id": "perimeter"}) == "proxy-only"
    # an invalid explicit tier falls back to the derived value
    assert m.resolve_tier({"id": "x", "auth": "bogus", "privileged": True}) == "step-up"


def test_elevation_mint_check_consume_single_use(tmp_path):
    m = _load()
    store = m.ElevationStore(tmp_path / "elev.json")
    now = 1000.0
    assert not store.check("sess1", "step-up", now=now)
    store.mint("sess1", "step-up", ttl=300, now=now)
    # check does not burn; consume burns exactly once
    assert store.check("sess1", "step-up", now=now + 10)
    assert store.consume("sess1", "step-up", now=now + 10)
    assert not store.consume("sess1", "step-up", now=now + 10), "single-use"
    assert not store.check("sess1", "step-up", now=now + 10)


def test_elevation_expires_and_is_session_tier_bound(tmp_path):
    m = _load()
    store = m.ElevationStore(tmp_path / "elev.json")
    now = 1000.0
    store.mint("sess1", "step-up", ttl=300, now=now)
    # expired
    assert not store.check("sess1", "step-up", now=now + 301)
    # wrong session / wrong tier never matches
    store.mint("sess2", "step-up", ttl=300, now=now)
    assert not store.consume("other", "step-up", now=now + 10)
    assert not store.consume("sess2", "step-up-strong", now=now + 10)
    assert store.consume("sess2", "step-up", now=now + 10)
