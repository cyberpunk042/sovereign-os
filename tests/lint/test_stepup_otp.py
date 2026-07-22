"""SDD-509 Phase B — out-of-band one-time codes (phone/email) contract.

The net-new OTP layer notifykit lacked: mint / verify / rate-limit / replay-burn,
plus a TARGETED single-channel delivery adapter (never the broadcast dispatch,
which would copy the code into the file/log channel). Store logic is exercised
deterministically; delivery is proven inert-until-configured (non-breaking) and
proven to select a single secure channel rather than broadcasting.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STEPUP = REPO / "scripts" / "operator" / "lib" / "stepup.py"


def _load():
    spec = importlib.util.spec_from_file_location("stepup_otp", STEPUP)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_otp_mint_verify_single_use(tmp_path):
    m = _load()
    store = m.OtpStore(tmp_path / "otp.json")
    now = 1000.0
    code = store.request("operator", "sms", now=now)
    assert code and code.isdigit() and len(code) == 6
    assert store.verify("operator", code, now=now + 5) is True
    # single-use — the code is burned
    assert store.verify("operator", code, now=now + 6) is False


def test_otp_expiry(tmp_path):
    m = _load()
    store = m.OtpStore(tmp_path / "otp.json")
    code = store.request("operator", "email", now=1000.0)
    assert store.verify("operator", code, now=1000.0 + m.OTP_TTL + 1) is False


def test_otp_attempt_budget_then_burn(tmp_path):
    m = _load()
    store = m.OtpStore(tmp_path / "otp.json")
    now = 1000.0
    code = store.request("operator", "sms", now=now)
    # exhaust the attempt budget with wrong guesses
    for _ in range(m.OTP_MAX_ATTEMPTS):
        assert store.verify("operator", "000000", now=now + 1) is False
    # even the correct code no longer works — the entry was burned on exhaustion
    assert store.verify("operator", code, now=now + 2) is False


def test_otp_request_cooldown_anti_flood(tmp_path):
    m = _load()
    store = m.OtpStore(tmp_path / "otp.json")
    now = 1000.0
    first = store.request("operator", "sms", now=now)
    assert first is not None
    # a second request within the cooldown is refused (no phone/email flood)...
    assert store.request("operator", "sms", now=now + 1) is None
    # ...and the FIRST code is still valid
    assert store.verify("operator", first, now=now + 2) is True


def test_otp_replaces_prior_after_cooldown(tmp_path):
    m = _load()
    store = m.OtpStore(tmp_path / "otp.json")
    now = 1000.0
    first = store.request("operator", "sms", now=now)
    second = store.request("operator", "sms", now=now + m.OTP_REQUEST_COOLDOWN + 1)
    assert second is not None and second != first
    # the prior code is replaced (only the latest is valid)
    assert store.verify("operator", first, now=now + 100) is False
    assert store.verify("operator", second, now=now + 100) is True


def test_wrong_guess_does_not_burn_a_sibling_channel_code(tmp_path):
    m = _load()
    store = m.OtpStore(tmp_path / "otp.json")
    now = 1000.0
    sms = store.request("operator", "sms", now=now)
    email = store.request("operator", "email", now=now)  # different channel, no cooldown clash
    # one wrong guess decrements both budgets by 1 but burns neither yet;
    # the correct sms code still verifies (and only it is burned)
    assert store.verify("operator", "999999", now=now + 1) is False
    assert store.verify("operator", sms, now=now + 2) is True
    assert store.verify("operator", email, now=now + 3) is True


def test_verify_otp_and_elevate_mints_elevation(tmp_path):
    m = _load()
    store = m.OtpStore(tmp_path / "otp.json")
    now = 1000.0
    code = store.request("operator", "sms", now=now)
    assert m.verify_otp_and_elevate(tmp_path, "operator", code, now=now + 1) is True
    assert m.ElevationStore(tmp_path / "elevations.json").check(
        "operator", "step-up", now=now + 2
    )
    # a wrong code neither elevates nor mints
    assert m.verify_otp_and_elevate(tmp_path, "operator", "000000", now=now + 3) is False


def test_delivery_is_inert_until_notifykit_configured(tmp_path):
    m = _load()
    # no notifykit config → delivery is a no-op failure, never a crash; the
    # phone/email factors simply aren't offered (non-breaking).
    assert m.available_otp_channels(tmp_path / "nope.toml") == []
    ok, detail = m.deliver_otp("123456", "sms", tmp_path / "nope.toml")
    assert ok is False
    ok2, _ = m.request_otp_and_deliver(tmp_path, tmp_path / "nope.toml", "operator", "email")
    assert ok2 is False
    # an unknown factor is rejected cleanly
    assert m.deliver_otp("123456", "carrier-pigeon", tmp_path / "x.toml")[0] is False


def test_delivery_targets_one_channel_never_broadcasts():
    # the adapter must NOT use the broadcast registry (which would copy the code
    # into the file/log channel) — it builds and sends to ONE secure channel.
    src = STEPUP.read_text(encoding="utf-8")
    assert "build_channel" in src and "channel.send(" in src
    assert "ChannelRegistry" not in src and ".dispatch(" not in src, (
        "OTP delivery must not broadcast — that leaks the code to the file channel"
    )
