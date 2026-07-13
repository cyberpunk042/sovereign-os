#!/usr/bin/env python3
"""
tests/unit/test_ms003_sign.py — the MS003 ed25519 signing primitive (SDD-989).

Exercises the producer half of the operator-chosen Option B (sovereign-os mints,
selfdef verifies): sign/verify round-trip, tamper + wrong-key rejection, canonical
determinism, and the graceful no-key fallback that keeps a stdlib-only node's
behaviour unchanged. Signing shells to the system `openssl`; the real-signing
cases skip cleanly if `openssl` can't do ed25519.

Stdlib + pytest only.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[2] / "scripts" / "lib" / "ms003.py"


def _load():
    spec = importlib.util.spec_from_file_location("ms003_uut", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _openssl_has_ed25519() -> bool:
    try:
        r = subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519"],
                           capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


ms003 = _load()
REC = {"op": "remember", "mem_id": "m1", "actor": "op", "signature": ms003.UNSIGNED}


def test_no_key_falls_back_to_placeholder(monkeypatch, tmp_path):
    monkeypatch.setenv("SOVEREIGN_OS_MS003_KEY", str(tmp_path / "absent.key"))
    assert ms003.sign(REC) == ms003.UNSIGNED


def test_sign_never_raises_on_garbage(monkeypatch, tmp_path):
    # a non-key file at the path must degrade to the placeholder, not raise
    bad = tmp_path / "bad.key"
    bad.write_text("not a key")
    monkeypatch.setenv("SOVEREIGN_OS_MS003_KEY", str(bad))
    assert ms003.sign(REC) == ms003.UNSIGNED


def test_canonical_bytes_excludes_signature_field():
    a = ms003.canonical_bytes(REC)
    b = ms003.canonical_bytes({**REC, "signature": "anything-else"})
    assert a == b
    # and it is deterministic regardless of key order
    assert ms003.canonical_bytes({"b": 1, "a": 2}) == ms003.canonical_bytes({"a": 2, "b": 1})


def test_placeholder_never_verifies():
    assert ms003.verify(REC, ms003.UNSIGNED, b"\x00" * 32) is False
    assert ms003.is_signed(ms003.UNSIGNED) is False


@pytest.mark.skipif(not _openssl_has_ed25519(), reason="openssl lacks ed25519")
def test_sign_verify_roundtrip_and_rejections(monkeypatch, tmp_path):
    kp = tmp_path / "ms003.key"
    monkeypatch.setenv("SOVEREIGN_OS_MS003_KEY", str(kp))
    assert ms003._gen_key() == 0
    pub = ms003._pub_raw_from_key(kp)
    assert pub is not None and len(pub) == 32

    sig = ms003.sign(REC)
    assert ms003.is_signed(sig)
    assert sig.startswith("ms003:ed25519:")
    # a real signature verifies
    assert ms003.verify(REC, sig, pub) is True
    # tampering the record fails
    assert ms003.verify({**REC, "mem_id": "TAMPERED"}, sig, pub) is False
    # a different key fails
    kp2 = tmp_path / "other.key"
    monkeypatch.setenv("SOVEREIGN_OS_MS003_KEY", str(kp2))
    assert ms003._gen_key() == 0
    pub2 = ms003._pub_raw_from_key(kp2)
    assert ms003.verify(REC, sig, pub2) is False


@pytest.mark.skipif(not _openssl_has_ed25519(), reason="openssl lacks ed25519")
def test_gen_key_refuses_overwrite(monkeypatch, tmp_path):
    kp = tmp_path / "ms003.key"
    monkeypatch.setenv("SOVEREIGN_OS_MS003_KEY", str(kp))
    assert ms003._gen_key() == 0
    assert ms003._gen_key() == 1  # refuses to clobber
    assert (kp.stat().st_mode & 0o777) == 0o600
