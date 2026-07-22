"""SDD-509 Phase A — step-up MFA primitives: TOTP (RFC 6238) + elevation + tiering.

The specced software MFA for high-privilege cockpit operations: TOTP (Google
Authenticator) as the offline factor, a short-TTL single-use *elevation* so the
operator steps up once per window (not per command), and the auth-tier
resolution from `config/control-systems.yaml`. Phase B adds the notifykit
phone/email one-time-code factors; Phase C adds the config pane. Pure stdlib —
no new dependency (honors the repo invariant).

Honest scope (SDD-509): software MFA on the operator's phone stops a *browser*
attacker and adds friction + a signed audit trail. It is NOT a hardware
guarantee against an attacker who already holds a shell as the operator user —
that is the OS-hardening / selfdef boundary this complements, not replaces. The
elevation + secret stores are meant to live behind a root-owned verifier
(process isolation) — Phase A ships the verification *logic*; wiring it into a
dedicated root process is the tracked hardening step.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import time
from pathlib import Path

# ── auth tiers ──────────────────────────────────────────────────────────────
TIER_NONE = "none"
TIER_PRESENT = "operator-present"
TIER_STEP_UP = "step-up"
TIER_PROXY_ONLY = "proxy-only"
VALID_TIERS = (TIER_NONE, TIER_PRESENT, TIER_STEP_UP, TIER_PROXY_ONLY)

# selfdef/perimeter are producer-owned — signed-proxy only, never a local factor
# ("already covered", per the operator). Mirrors _action_exec.SELFDEF_OWNED.
_PROXY_ONLY_IDS = frozenset({"selfdef", "perimeter"})


def resolve_tier(control: dict) -> str:
    """The auth tier a control requires.

    An explicit ``auth:`` field wins; otherwise it derives from ``privileged``
    (backward-compatible: privileged → step-up, else none). selfdef/perimeter
    are always proxy-only.
    """
    explicit = control.get("auth")
    if explicit in VALID_TIERS:
        return explicit
    if control.get("id") in _PROXY_ONLY_IDS:
        return TIER_PROXY_ONLY
    return TIER_STEP_UP if control.get("privileged") else TIER_NONE


# ── TOTP (RFC 6238) ─────────────────────────────────────────────────────────
def _pad_b32(secret_b32: str) -> str:
    s = secret_b32.strip().replace(" ", "").upper()
    return s + "=" * ((8 - len(s) % 8) % 8)


def totp_code(
    secret_b32: str,
    for_time: float,
    *,
    period: int = 30,
    digits: int = 6,
    algo: str = "sha1",
) -> str:
    """The RFC 6238 TOTP code for ``secret_b32`` at ``for_time`` (epoch seconds)."""
    key = base64.b32decode(_pad_b32(secret_b32), casefold=True)
    counter = int(for_time // period)
    mac = hmac.new(key, struct.pack(">Q", counter), getattr(hashlib, algo)).digest()
    offset = mac[-1] & 0x0F
    bincode = (
        ((mac[offset] & 0x7F) << 24)
        | (mac[offset + 1] << 16)
        | (mac[offset + 2] << 8)
        | mac[offset + 3]
    )
    return str(bincode % (10**digits)).zfill(digits)


def totp_verify(
    secret_b32: str,
    code: str,
    for_time: float | None = None,
    *,
    period: int = 30,
    digits: int = 6,
    algo: str = "sha1",
    skew: int = 1,
) -> bool:
    """Constant-time-compare ``code`` against the TOTP for ``secret_b32``,
    accepting ±``skew`` periods of clock drift."""
    if for_time is None:
        for_time = time.time()
    code = (code or "").strip()
    if not code.isdigit() or len(code) != digits:
        return False
    for w in range(-skew, skew + 1):
        expected = totp_code(
            secret_b32, for_time + w * period, period=period, digits=digits, algo=algo
        )
        if hmac.compare_digest(expected, code):
            return True
    return False


def new_totp_secret(nbytes: int = 20) -> str:
    """A fresh base32 TOTP secret (no padding — Authenticator-app friendly)."""
    return base64.b32encode(secrets.token_bytes(nbytes)).decode("ascii").rstrip("=")


def provisioning_uri(secret_b32: str, account: str, issuer: str = "sovereign-os") -> str:
    """The ``otpauth://`` URI to render as an enrollment QR."""
    from urllib.parse import quote, urlencode

    label = quote(f"{issuer}:{account}", safe="")
    query = urlencode(
        {
            "secret": secret_b32,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": 6,
            "period": 30,
        }
    )
    return f"otpauth://totp/{label}?{query}"


# ── elevation store (short-TTL, single-use) ─────────────────────────────────
# Phase A default location; meant to be a root-owned path behind the verifier.
DEFAULT_ELEVATION_STORE = Path("/run/sovereign-os/stepup/elevations.json")


class ElevationStore:
    """A short-TTL, single-use elevation ledger.

    A successful factor mints an elevation bound to ``(session, tier)`` with a
    TTL; a matching privileged op consumes it (burned on use — no replay). The
    JSON file is the phase-A backing; the intended home is a root-owned store
    the operator user cannot write directly (the mint-vs-enforce boundary).
    """

    def __init__(self, path: Path | str = DEFAULT_ELEVATION_STORE):
        self.path = Path(path)

    def _load(self, now: float) -> list[dict]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return []
        # drop expired on every load (self-pruning)
        return [e for e in raw if isinstance(e, dict) and e.get("expires", 0) > now]

    def _save(self, entries: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(entries), encoding="utf-8")
        tmp.replace(self.path)

    def mint(self, session: str, tier: str, ttl: float = 300.0, now: float | None = None) -> str:
        """Mint an elevation for ``(session, tier)``; returns an opaque handle."""
        if now is None:
            now = time.time()
        entries = self._load(now)
        handle = secrets.token_urlsafe(24)
        entries.append(
            {"handle": handle, "session": session, "tier": tier, "expires": now + ttl}
        )
        self._save(entries)
        return handle

    def check(self, session: str, tier: str, now: float | None = None) -> bool:
        """True if a live elevation covers ``(session, tier)`` — WITHOUT burning
        it (for a read-only 'is the operator elevated?' probe)."""
        if now is None:
            now = time.time()
        return any(
            e["session"] == session and e["tier"] == tier for e in self._load(now)
        )

    def consume(self, session: str, tier: str, now: float | None = None) -> bool:
        """Burn one live elevation covering ``(session, tier)``. Returns True if
        one was found and consumed (single-use — the op proceeds); False means
        step-up is required."""
        if now is None:
            now = time.time()
        entries = self._load(now)
        for i, e in enumerate(entries):
            if e["session"] == session and e["tier"] == tier:
                del entries[i]
                self._save(entries)
                return True
        return False


# ── enrollment + verify convenience (a step-up dir holds the enrolled secret
#    + the elevation ledger) ───────────────────────────────────────────────
def secret_path(stepup_dir: Path | str) -> Path:
    return Path(stepup_dir) / "totp.secret"


def enrolled_secret(stepup_dir: Path | str) -> str | None:
    """The enrolled base32 TOTP secret, or None if step-up isn't enrolled."""
    try:
        return secret_path(stepup_dir).read_text(encoding="utf-8").strip() or None
    except (FileNotFoundError, OSError):
        return None


def is_enrolled(stepup_dir: Path | str) -> bool:
    return enrolled_secret(stepup_dir) is not None


def enroll(stepup_dir: Path | str, account: str = "operator@sain-01") -> tuple[str, str]:
    """Mint + persist a fresh TOTP secret; return ``(secret, provisioning_uri)``.
    The file is 0600 (best-effort) — its intended home is a root-owned dir."""
    secret = new_totp_secret()
    p = secret_path(stepup_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(secret + "\n", encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return secret, provisioning_uri(secret, account)


def verify_and_elevate(
    stepup_dir: Path | str,
    actor: str,
    code: str,
    *,
    tier: str = TIER_STEP_UP,
    ttl: float = 300.0,
    now: float | None = None,
) -> bool | None:
    """Verify a TOTP ``code`` and, on success, mint an elevation for
    ``(actor, tier)``. Returns True (verified + elevated), False (bad code), or
    None (step-up not enrolled — nothing to verify against)."""
    secret = enrolled_secret(stepup_dir)
    if secret is None:
        return None
    if not totp_verify(secret, code, now):
        return False
    ElevationStore(Path(stepup_dir) / "elevations.json").mint(actor, tier, ttl, now)
    return True


# ── Phase B: one-time codes delivered out-of-band (phone/email) ─────────────
# The net-new layer the design flagged: notifykit *delivers*, but has no OTP
# concept (mint / verify / rate-limit / replay-burn). This is it. A minted code
# is stored as a SALTED HASH (never plaintext at rest); the real defense against
# online guessing is the per-code attempt limit + short TTL. A delivered code is
# sent to exactly ONE secure channel (never the broadcast dispatch — that would
# copy the code into the file/log channel).
OTP_DIGITS = 6
OTP_TTL = 300.0
OTP_MAX_ATTEMPTS = 5
OTP_REQUEST_COOLDOWN = 20.0  # min seconds between requests per (actor, channel)


def _hash_otp(code: str, salt: str) -> str:
    return hashlib.sha256((salt + ":" + code).encode("utf-8")).hexdigest()


class OtpStore:
    """Short-TTL, single-use, rate-limited one-time codes (phone/email factor).

    A code is minted for ``(actor, channel)``, stored as a salted hash with a
    TTL + an attempt budget; ``verify`` constant-time-compares, decrements the
    budget, and burns the code on success OR on budget exhaustion. A fresh
    ``request`` for the same ``(actor, channel)`` replaces the prior code and is
    rate-limited by ``OTP_REQUEST_COOLDOWN``.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def _load(self, now: float) -> list[dict]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return []
        return [e for e in raw if isinstance(e, dict) and e.get("expires", 0) > now]

    def _save(self, entries: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(entries), encoding="utf-8")
        tmp.replace(self.path)

    def request(
        self,
        actor: str,
        channel: str,
        *,
        now: float | None = None,
        ttl: float = OTP_TTL,
        digits: int = OTP_DIGITS,
        max_attempts: int = OTP_MAX_ATTEMPTS,
    ) -> str | None:
        """Mint + persist a code for ``(actor, channel)``; return the PLAINTEXT
        code to deliver, or None if a request was made too recently (cooldown)."""
        if now is None:
            now = time.time()
        entries = self._load(now)
        kept: list[dict] = []
        for e in entries:
            if e["actor"] == actor and e["channel"] == channel:
                if now - e.get("issued", 0) < OTP_REQUEST_COOLDOWN:
                    self._save(entries)  # re-persist the pruned set
                    return None  # too soon — anti-flood
                continue  # replace this actor+channel's prior code
            kept.append(e)
        code = "".join(str(secrets.randbelow(10)) for _ in range(digits))
        salt = secrets.token_hex(8)
        kept.append(
            {
                "actor": actor,
                "channel": channel,
                "salt": salt,
                "hash": _hash_otp(code, salt),
                "issued": now,
                "expires": now + ttl,
                "attempts": max_attempts,
            }
        )
        self._save(kept)
        return code

    def verify(self, actor: str, code: str, now: float | None = None) -> bool:
        """Check ``code`` for ``actor`` (any channel). On the matching code:
        burn it, leave the actor's other codes untouched. On a wrong guess:
        decrement every one of the actor's codes and drop any exhausted."""
        if now is None:
            now = time.time()
        code = (code or "").strip()
        entries = self._load(now)
        mine = [e for e in entries if e["actor"] == actor]
        others = [e for e in entries if e["actor"] != actor]
        matched = None
        if code.isdigit():
            for e in mine:
                if hmac.compare_digest(e["hash"], _hash_otp(code, e["salt"])):
                    matched = e
                    break
        if matched is not None:
            self._save(others + [e for e in mine if e is not matched])  # burn matched
            return True
        kept = []
        for e in mine:
            e["attempts"] = int(e.get("attempts", 0)) - 1
            if e["attempts"] > 0:
                kept.append(e)  # budget remains; else burned
        self._save(others + kept)
        return False


def available_otp_channels(notify_config_path: Path | str) -> list[str]:
    """The OTP-capable notifykit channels that are configured AND enabled
    (``twilio`` = phone/SMS, ``resend`` = email). Empty if notifykit isn't set
    up — so the phone/email factors simply aren't offered until go-live."""
    try:
        import sys

        repo = Path(__file__).resolve().parents[3]
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        from tools.notifykit.config import NotifyConfig

        cfg = NotifyConfig.load(notify_config_path)
    except Exception:
        return []
    kinds = []
    for ch in cfg.channels.values():
        if ch.enabled and ch.kind in ("twilio", "resend"):
            kinds.append("sms" if ch.kind == "twilio" else "email")
    return sorted(set(kinds))


def deliver_otp(
    code: str,
    factor: str,
    notify_config_path: Path | str,
    *,
    ttl_min: int = 5,
) -> tuple[bool, str]:
    """Deliver ``code`` over exactly ONE secure channel (``sms``→twilio,
    ``email``→resend) — never the broadcast dispatch (which would copy the code
    into the file/log channel). Returns ``(ok, detail)``. Inert (``ok=False``)
    until the operator has configured + enabled that notifykit channel."""
    kind = {"sms": "twilio", "email": "resend"}.get(factor)
    if kind is None:
        return False, f"unknown OTP factor {factor!r}"
    try:
        import sys

        repo = Path(__file__).resolve().parents[3]
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        from tools.notifykit.channels import build_channel
        from tools.notifykit.config import NotifyConfig
        from tools.notifykit.event import Event

        cfg = NotifyConfig.load(notify_config_path)
    except Exception as e:  # notifykit unavailable / misconfigured
        return False, f"notifykit unavailable: {e}"
    target = next(
        (c for c in cfg.channels.values() if c.kind == kind and c.enabled), None
    )
    if target is None:
        return False, f"no enabled {kind} channel"
    channel = build_channel(target)
    valid, why = channel.validate()
    if not valid:
        return False, f"invalid {kind} config: {why}"
    event = Event(
        title="sovereign-os step-up code",
        message=f"Your sovereign-os step-up code is {code}. It expires in {ttl_min} min.",
        priority="high",
        urgency="high",
        source="stepup",
    )
    receipt = channel.send(event)
    return receipt.ok, receipt.detail


def request_otp_and_deliver(
    stepup_dir: Path | str,
    notify_config_path: Path | str,
    actor: str,
    factor: str,
    *,
    now: float | None = None,
) -> tuple[bool, str]:
    """Mint an OTP for ``(actor, factor)`` and deliver it over the one secure
    channel. Returns ``(ok, detail)``; the plaintext code never leaves here."""
    store = OtpStore(Path(stepup_dir) / "otp.json")
    code = store.request(actor, factor, now=now)
    if code is None:
        return False, "a code was just sent — wait before requesting another"
    return deliver_otp(code, factor, notify_config_path)


def verify_otp_and_elevate(
    stepup_dir: Path | str,
    actor: str,
    code: str,
    *,
    tier: str = TIER_STEP_UP,
    ttl: float = 300.0,
    now: float | None = None,
) -> bool:
    """Verify an out-of-band OTP and, on success, mint an elevation."""
    store = OtpStore(Path(stepup_dir) / "otp.json")
    if not store.verify(actor, code, now):
        return False
    ElevationStore(Path(stepup_dir) / "elevations.json").mint(actor, tier, ttl, now)
    return True
