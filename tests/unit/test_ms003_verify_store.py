#!/usr/bin/env python3
"""tests/unit/test_ms003_verify_store.py — MS003 verifier half (F-2026-034).

The SDD-989/990 producer half signs records; this proves the LOCAL verifier
half added 2026-07-17: a trust-anchor store + record/ledger classification so
a sovereign-os node can audit its own durable ledgers (and selfdef can reuse
the same store layout + statuses as the cross-repo verifier contract).

Covers: anchor add/list, per-record status classification across the full
VERIFY_STATUSES enum (verified / unsigned-placeholder / no-signature-field /
unknown-keyid / invalid-signature), and a filesystem sweep over .json + .jsonl
ledgers. Real-crypto cases skip cleanly when the system openssl can't do
ed25519. Stdlib + pytest only.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MS003 = REPO / "scripts" / "lib" / "ms003.py"


def _load():
    spec = importlib.util.spec_from_file_location("ms003", MS003)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ms003 = _load()


def _openssl_ed25519_ok() -> bool:
    return ms003._openssl(["version"]) is not None


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_MS003_KEY", str(tmp_path / "ms003.key"))
    monkeypatch.setenv("SOVEREIGN_OS_MS003_TRUST_ANCHORS", str(tmp_path / "anchors"))
    return tmp_path


def test_verify_statuses_enum_is_stable():
    # selfdef's cross-repo verifier consumes these strings — pin them.
    assert ms003.VERIFY_STATUSES == (
        "verified", "unsigned-placeholder", "no-signature-field",
        "unknown-keyid", "invalid-signature",
    )


def test_no_signature_field(env):
    assert ms003.verify_record({"id": "x", "op": "noop"}) == "no-signature-field"


def test_unsigned_placeholder(env):
    rec = {"id": "x", "signature": ms003.UNSIGNED}
    assert ms003.verify_record(rec) == "unsigned-placeholder"


def test_garbage_signature_is_invalid(env):
    rec = {"id": "x", "signature": "not-an-ms003-sig"}
    assert ms003.verify_record(rec) == "invalid-signature"


def test_anchor_add_rejects_bad_key(env):
    assert ms003.anchor_add("!!!not-base64!!!") is None
    assert ms003.anchor_add(ms003._b64u(b"\x00" * 10)) is None  # wrong length


@pytest.mark.skipif(not _openssl_ed25519_ok(), reason="openssl unavailable")
def test_end_to_end_verified_and_tamper_and_unknown(env, monkeypatch):
    # Mint a key, sign a record.
    assert ms003._gen_key() == 0
    rec = {"id": "abc", "op": "decide", "value": 42}
    sig = ms003.sign(rec)
    if not ms003.is_signed(sig):
        pytest.skip("openssl present but ed25519 signing unavailable")
    rec["signature"] = sig

    # Before the anchor is installed: signed but untrusted signer.
    assert ms003.verify_record(rec) == "unknown-keyid"

    # Install THIS node's key as a trust anchor → verified.
    kid = ms003.anchor_add(ms003._b64u(ms003._pub_raw_from_key(ms003._key_path())))
    assert kid is not None
    assert kid in ms003.anchors()
    assert ms003.verify_record(rec) == "verified"

    # Tamper the payload → invalid.
    tampered = dict(rec, value=43)
    assert ms003.verify_record(tampered) == "invalid-signature"


@pytest.mark.skipif(not _openssl_ed25519_ok(), reason="openssl unavailable")
def test_sweep_counts_across_json_and_jsonl(env, monkeypatch):
    assert ms003._gen_key() == 0
    ms003.anchor_add(ms003._b64u(ms003._pub_raw_from_key(ms003._key_path())))

    root = env / "ledgers"
    root.mkdir()
    # A verified record in a nested .json ledger.
    good = {"id": "g", "op": "store"}
    good["signature"] = ms003.sign(good)
    if not ms003.is_signed(good["signature"]):
        pytest.skip("ed25519 signing unavailable")
    (root / "changes.json").write_text(
        json.dumps({"changes": [good]}), encoding="utf-8")
    # An unsigned + a tampered record in a .jsonl ledger.
    unsigned = {"id": "u", "signature": ms003.UNSIGNED}
    tampered = dict(good, value="x")  # signature no longer matches
    (root / "audit.jsonl").write_text(
        json.dumps(unsigned) + "\n" + json.dumps(tampered) + "\n", encoding="utf-8")

    c = ms003.sweep(root)
    assert c["files"] == 2
    assert c["verified"] == 1
    assert c["unsigned-placeholder"] == 1
    assert c["invalid-signature"] == 1
    assert c["unknown-keyid"] == 0


def test_sweep_missing_root_is_empty(env):
    c = ms003.sweep(env / "does-not-exist")
    assert c["files"] == 0 and c["verified"] == 0
