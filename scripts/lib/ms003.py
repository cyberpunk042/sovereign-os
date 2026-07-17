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


# --- trust-anchor store (verifier half, 2026-07-17) --------------------------
# F-2026-034's open half. The producer (sign) half shipped in SDD-989/990;
# this adds the LOCAL trust-anchor store + record/ledger verification so a
# sovereign-os node can audit its own durable ledgers (and selfdef can reuse
# the same store layout + statuses as the cross-repo verifier contract).
#
# Store layout: one file per anchor at
#   $SOVEREIGN_OS_MS003_TRUST_ANCHORS/<keyid>.pub   (default
#   /etc/sovereign-os/ms003-trust-anchors/), containing the base64url raw
#   32-byte ed25519 public key (the `pubkey` line gen-key/pubkey print).
#
# Verification statuses (the exhaustive enum consumers switch on):
#   verified            — real signature, anchor found, openssl verify OK
#   unsigned-placeholder — the historical `unsigned-pending-MS003`
#   no-signature-field  — record carries no `signature` key at all
#   unknown-keyid       — signed, but no anchor file for its keyid
#   invalid-signature   — signed, anchor found, verification FAILED (tamper!)

VERIFY_STATUSES = ("verified", "unsigned-placeholder", "no-signature-field",
                   "unknown-keyid", "invalid-signature")


def _anchor_dir() -> Path:
    return Path(os.environ.get("SOVEREIGN_OS_MS003_TRUST_ANCHORS",
                               "/etc/sovereign-os/ms003-trust-anchors"))


def anchors() -> dict[str, bytes]:
    """keyid → raw 32-byte public key, from the trust-anchor store.
    Missing/unreadable store degrades to {} (never raises)."""
    out: dict[str, bytes] = {}
    try:
        for f in sorted(_anchor_dir().glob("*.pub")):
            try:
                raw = _b64u_dec(f.read_text(encoding="utf-8").strip())
            except Exception:
                continue
            if len(raw) == 32 and f.stem == keyid(raw):
                out[f.stem] = raw
    except OSError:
        pass
    return out


def anchor_add(pub_b64u: str) -> str | None:
    """Install a base64url raw public key as a trust anchor; returns its
    keyid, or None when the input is not a valid 32-byte key."""
    try:
        raw = _b64u_dec(pub_b64u.strip())
    except Exception:
        return None
    if len(raw) != 32:
        return None
    d = _anchor_dir()
    d.mkdir(parents=True, exist_ok=True)
    kid = keyid(raw)
    (d / f"{kid}.pub").write_text(_b64u(raw) + "\n", encoding="utf-8")
    return kid


def verify_record(record: dict) -> str:
    """Classify one record against the trust-anchor store → one of
    VERIFY_STATUSES. Never raises."""
    try:
        sig = record.get("signature")
        if sig is None:
            return "no-signature-field"
        if sig == UNSIGNED:
            return "unsigned-placeholder"
        if not is_signed(sig):
            return "invalid-signature"
        kid = sig.split(":", 3)[2]
        store = anchors()
        if kid not in store:
            return "unknown-keyid"
        return "verified" if verify(record, sig, store[kid]) else "invalid-signature"
    except Exception:
        return "invalid-signature"


def _iter_records(node) -> list[dict]:
    """Every dict carrying a `signature` key inside a parsed JSON document
    (records may sit at top level or nested in ledger arrays)."""
    found: list[dict] = []
    if isinstance(node, dict):
        if "signature" in node:
            found.append(node)
        for v in node.values():
            found.extend(_iter_records(v))
    elif isinstance(node, list):
        for v in node:
            found.extend(_iter_records(v))
    return found


def sweep(root: Path) -> dict[str, int]:
    """Walk `root` for .json/.jsonl documents, verify every signed record
    against the trust-anchor store. Returns counts per VERIFY_STATUSES
    (+ 'files' scanned, 'unreadable' documents). Never raises."""
    counts = {s: 0 for s in VERIFY_STATUSES}
    counts["files"] = 0
    counts["unreadable"] = 0
    try:
        paths = sorted(list(root.rglob("*.json")) + list(root.rglob("*.jsonl")))
    except OSError:
        return counts
    for p in paths:
        counts["files"] += 1
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            counts["unreadable"] += 1
            continue
        docs = []
        if p.suffix == ".jsonl":
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    docs.append(json.loads(line))
                except Exception:
                    counts["unreadable"] += 1
        else:
            try:
                docs.append(json.loads(text))
            except Exception:
                counts["unreadable"] += 1
        for doc in docs:
            for rec in _iter_records(doc):
                counts[verify_record(rec)] += 1
    return counts


def _cmd_anchor_add(argv: list[str]) -> int:
    if argv and argv[0] == "--from-key":
        if not _have_key():
            print(f"no usable operator key at {_key_path()}")
            return 1
        pub_b64u = _b64u(_pub_raw_from_key(_key_path()))
    elif argv:
        pub_b64u = argv[0]
    else:
        print("usage: ms003.py anchor-add (<pubkey-b64url> | --from-key)")
        return 1
    kid = anchor_add(pub_b64u)
    if kid is None:
        print("error: not a valid base64url 32-byte ed25519 public key")
        return 1
    print(f"anchor installed: {_anchor_dir() / (kid + '.pub')}")
    return 0


def _cmd_anchor_list() -> int:
    store = anchors()
    print(f"trust-anchor store: {_anchor_dir()} ({len(store)} anchor(s))")
    for kid in store:
        print(f"  {kid}")
    return 0


def _cmd_verify_sweep(argv: list[str]) -> int:
    strict = "--strict" in argv
    args = [a for a in argv if a != "--strict"]
    root = Path(args[0]) if args else Path(
        os.environ.get("SOVEREIGN_OS_MS003_SWEEP_ROOT", "/var/lib/sovereign-os"))
    counts = sweep(root)
    print(f"sweep root: {root}")
    for k in ("files", "unreadable", *VERIFY_STATUSES):
        print(f"  {k}: {counts[k]}")
    if counts["invalid-signature"] or counts["unknown-keyid"]:
        return 2  # tamper / untrusted signer — always an error
    if strict and counts["unsigned-placeholder"]:
        return 3  # unsigned records present and the operator demands none
    return 0


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
    if cmd == "anchor-add":
        return _cmd_anchor_add(argv[1:])
    if cmd == "anchor-list":
        return _cmd_anchor_list()
    if cmd == "verify-sweep":
        return _cmd_verify_sweep(argv[1:])
    print(f"openssl: {'available' if _openssl(['version']) else 'absent'}")
    print(f"key path: {_key_path()}")
    print(f"signing: {'ACTIVE (real ed25519)' if _have_key() else 'placeholder (unsigned-pending-MS003)'}")
    store = anchors()
    print(f"trust anchors: {len(store)} at {_anchor_dir()}"
          + (f" [{', '.join(store)}]" if store else ""))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
