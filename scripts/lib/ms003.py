"""
scripts/lib/ms003.py — MS003 mutation-record signing (Option B, SDD-989).

Operator-chosen model (2026-07-13): **sovereign-os mints** an ed25519 signature
over each mutation record; **selfdef verifies**. This is the sovereign-os
(producer) half — real signatures now, with no coupling to selfdef uptime
(preserves MS043 offline-survivability); selfdef-owned controls stay a signed
proxy (R10212 untouched).

NO NEW DEPENDENCY + GRACEFUL FALLBACK
-------------------------------------
The runtime scripts are strictly stdlib; this keeps that invariant. Signing shells
to the **system `openssl`** (already present — SecureBoot uses it), so there is no
new Python package. Signing is opportunistic: a record gets a REAL signature only
when BOTH are present —

  1. an `openssl` that supports ed25519, and
  2. an operator ed25519 private key at `$SOVEREIGN_OS_MS003_KEY`
     (default `~/.sovereign-os/ms003.key`, a PEM ed25519 key).

Otherwise `sign()` returns the historical `unsigned-pending-MS003` placeholder, so
a node without the key behaves exactly as before. `sign()` NEVER raises — a signing
failure must never break a mutation write; it degrades to the placeholder.

WIRE FORMAT (the contract selfdef verifies)
-------------------------------------------
    ms003:ed25519:<keyid>:<sig>

  * `keyid` — first 16 chars of base64url(raw 32-byte public key), no padding;
    lets the verifier select the operator's trust anchor.
  * `sig`   — base64url(64-byte ed25519 signature), no padding.
  * signed bytes — `canonical_bytes(record)`: JSON of the record with the
    `signature` key removed, `sort_keys=True`, `separators=(",",":")`, UTF-8.

selfdef verifies by: recompute `canonical_bytes`, select the operator public key
by `keyid`, ed25519-verify `sig`. Provision + export the public trust anchor with
`python3 scripts/lib/ms003.py gen-key` / `pubkey`.

Stdlib only (subprocess to `openssl`).
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path

UNSIGNED = "unsigned-pending-MS003"
_PREFIX = "ms003:ed25519:"
# Fixed DER SubjectPublicKeyInfo prefix for an ed25519 public key (RFC 8410):
# 30 2a 30 05 06 03 2b 65 70 03 21 00, then the 32 raw key bytes = 44-byte DER.
_ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")


def _key_path() -> Path:
    return Path(os.environ.get(
        "SOVEREIGN_OS_MS003_KEY", str(Path.home() / ".sovereign-os" / "ms003.key")))


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _openssl(args: list[str], stdin: bytes | None = None) -> bytes | None:
    try:
        r = subprocess.run(["openssl", *args], input=stdin,
                           capture_output=True, timeout=10)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def canonical_bytes(record: dict) -> bytes:
    """The exact bytes signed/verified: the record minus its `signature` field,
    deterministically serialized. Producer and verifier MUST agree on this."""
    body = {k: v for k, v in record.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _pub_raw_from_key(key_path: Path) -> bytes | None:
    """The 32 raw ed25519 public-key bytes (last 32 of the DER SPKI)."""
    der = _openssl(["pkey", "-in", str(key_path), "-pubout", "-outform", "DER"])
    if der is None or len(der) < 32:
        return None
    return der[-32:]


def keyid(pub_raw: bytes) -> str:
    return _b64u(pub_raw)[:16]


def _have_key() -> bool:
    p = _key_path()
    return p.is_file() and _pub_raw_from_key(p) is not None


def sign(record: dict) -> str:
    """Sign `record` → an `ms003:ed25519:…` string, or the `unsigned-pending-MS003`
    placeholder when signing isn't available. Never raises."""
    try:
        kp = _key_path()
        if not kp.is_file():
            return UNSIGNED
        pub_raw = _pub_raw_from_key(kp)
        if pub_raw is None:
            return UNSIGNED
        with tempfile.NamedTemporaryFile() as msg:
            msg.write(canonical_bytes(record))
            msg.flush()
            sig = _openssl(["pkeyutl", "-sign", "-inkey", str(kp),
                            "-rawin", "-in", msg.name])
        if not sig:
            return UNSIGNED
        return f"{_PREFIX}{keyid(pub_raw)}:{_b64u(sig)}"
    except Exception:
        return UNSIGNED


def is_signed(signature: str) -> bool:
    return isinstance(signature, str) and signature.startswith(_PREFIX)


def _pub_pem(pub_raw: bytes) -> bytes:
    der = _ED25519_SPKI_PREFIX + pub_raw
    b64 = base64.encodebytes(der).decode("ascii").strip()
    return (f"-----BEGIN PUBLIC KEY-----\n{b64}\n-----END PUBLIC KEY-----\n").encode()


def verify(record: dict, signature: str, public_key_raw: bytes) -> bool:
    """Verify a real `ms003:ed25519:…` signature against a raw 32-byte ed25519
    public key (the selfdef-side reference). The placeholder never verifies."""
    if not is_signed(signature) or len(public_key_raw) != 32:
        return False
    try:
        _, _, kid, sig_b64 = signature.split(":", 3)
        if kid != keyid(public_key_raw):
            return False
        with tempfile.NamedTemporaryFile() as pub, \
                tempfile.NamedTemporaryFile() as msg, \
                tempfile.NamedTemporaryFile() as sig:
            pub.write(_pub_pem(public_key_raw))
            pub.flush()
            msg.write(canonical_bytes(record))
            msg.flush()
            sig.write(_b64u_dec(sig_b64))
            sig.flush()
            r = subprocess.run(
                ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", pub.name,
                 "-rawin", "-in", msg.name, "-sigfile", sig.name],
                capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


# --- provisioning CLI --------------------------------------------------------
def _gen_key() -> int:
    p = _key_path()
    if p.exists():
        print(f"refusing to overwrite existing key: {p}")
        return 1
    p.parent.mkdir(parents=True, exist_ok=True)
    out = _openssl(["genpkey", "-algorithm", "ed25519", "-out", str(p)])
    if out is None or not p.is_file():
        print("error: openssl could not generate an ed25519 key")
        return 2
    p.chmod(0o600)
    pub = _pub_raw_from_key(p)
    if pub is None:
        print("error: generated key is unreadable")
        return 2
    print(f"wrote {p} (0600)")
    print(f"keyid: {keyid(pub)}")
    print(f"pubkey (share with selfdef as the MS003 trust anchor): {_b64u(pub)}")
    return 0


def _print_pubkey() -> int:
    if not _have_key():
        print(f"no usable operator key at {_key_path()}")
        return 1
    pub = _pub_raw_from_key(_key_path())
    print(f"keyid: {keyid(pub)}")
    print(f"pubkey: {_b64u(pub)}")
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    if cmd == "gen-key":
        return _gen_key()
    if cmd == "pubkey":
        return _print_pubkey()
    print(f"openssl: {'available' if _openssl(['version']) else 'absent'}")
    print(f"key path: {_key_path()}")
    print(f"signing: {'ACTIVE (real ed25519)' if _have_key() else 'placeholder (unsigned-pending-MS003)'}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
