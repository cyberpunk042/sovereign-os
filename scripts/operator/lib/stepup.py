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
