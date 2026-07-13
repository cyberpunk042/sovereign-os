# SDD-989 — MS003 signing primitive: sovereign-os mints ed25519 (Option B, producer half) (F-2026-034)

> Status: draft
> Owner: operator-directed 2026-07-13 (AskUserQuestion → **"B — sovereign-os mints (recommended)"**); agent-authored.
> Advances: **F-2026-034** (MS003 — the `unsigned-pending-MS003` placeholder arc). Producer half; PR 2 sweeps the writers.
> Mandate module: **E11.M989**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## The operator decision this implements

Every mutation/decision record sovereign-os writes carries a `signature` field
pinned to the literal placeholder `unsigned-pending-MS003` — MS003 (mutation-record
signing) was scoped but never had a producer. The audit surfaced the open design
question as **F-2026-034** and put it to the operator as a package with three shapes;
the operator chose **Option B**:

> **sovereign-os mints an ed25519 signature over each record with the operator's
> own key identity; selfdef verifies against the exported public trust anchor.**

Option B keeps the two guarantees that made the placeholder safe in the first place:

- **Offline survivability (MS043).** Signing is local — no call to selfdef, no
  network. A sovereign node that never reaches selfdef still produces real,
  verifiable signatures. selfdef verification is asynchronous and after-the-fact.
- **The selfdef boundary (R10212) is untouched.** This signs records
  sovereign-os *already writes on its own authority*; it does not move any
  selfdef-owned control into sovereign-os. selfdef-owned privileged actions stay
  a signed proxy exactly as before.

This SDD ships the **producer half only** — the signing primitive + provisioning +
the wire-format contract selfdef must implement. Wiring the primitive into the
record writers is **PR 2** (deliberately separate — see *Scoping* below).

## What this SDD builds

**`scripts/lib/ms003.py`** — the signing primitive. Public surface:

| Function | Contract |
|---|---|
| `canonical_bytes(record)` | The exact bytes signed/verified: the record **minus its `signature` field**, `json.dumps(sort_keys=True, separators=(",",":"))`, UTF-8. Producer and verifier MUST agree on this byte-for-byte. |
| `sign(record) -> str` | Real `ms003:ed25519:…` signature when a key is present; else the `unsigned-pending-MS003` placeholder. **Never raises** — a signing failure degrades to the placeholder, never breaks a mutation write. |
| `verify(record, signature, public_key_raw) -> bool` | selfdef-side reference verification against a raw 32-byte ed25519 public key. The placeholder never verifies. |
| `is_signed(signature) -> bool` | `True` only for a real `ms003:ed25519:` signature. |
| `keyid(pub_raw) -> str` | The 16-char key selector (see wire format). |
| CLI: `gen-key` / `pubkey` / `status` | Provision the operator key (0600, refuses to clobber), export the public trust anchor, report signing state. |

**`tests/unit/test_ms003_sign.py`** — 6 tests: no-key→placeholder, never-raises-on-a
-garbage-key, `canonical_bytes` excludes the signature field + is key-order stable,
the placeholder never verifies, and (skip-if-no-ed25519) a full sign→verify
round-trip with tamper-rejection + wrong-key-rejection + gen-key-refuses-overwrite.

## No new dependency + graceful fallback (the two hard constraints)

The runtime/intelligence scripts are **strictly stdlib** — that invariant is itself
enforced by a lint. Two engineering constraints followed:

1. **No new Python package.** The `cryptography` wheel is not importable in this
   environment (its `_cffi_backend` is missing → a pyo3 `PanicException` that, being
   a `BaseException`, escapes `except Exception`). So signing shells to the **system
   `openssl`** (already a hard dependency — SecureBoot provisioning uses it):
   `openssl pkeyutl -sign/-verify -rawin` for ed25519, `openssl pkey -pubout -outform
   DER` for the raw public key (last 32 bytes of the DER SPKI). Pure stdlib +
   subprocess; nothing to install; locally verifiable on any box with openssl.
2. **Opportunistic, never mandatory.** A record gets a real signature only when BOTH
   an ed25519-capable `openssl` AND an operator key at `$SOVEREIGN_OS_MS003_KEY`
   (default `~/.sovereign-os/ms003.key`) are present. Otherwise `sign()` returns the
   historical placeholder — a node **without** the key behaves exactly as it does
   today. This is what makes PR 2 (wiring the writers) a no-op for every existing
   node and test until an operator provisions a key.

## Wire format — the contract selfdef verifies

```
ms003:ed25519:<keyid>:<sig>
```

- **`keyid`** — first 16 chars of `base64url(raw 32-byte public key)`, no padding.
  Lets the verifier select which operator trust anchor to check against
  (multi-key / rotation-ready).
- **`sig`** — `base64url(64-byte ed25519 signature)`, no padding.
- **signed bytes** — `canonical_bytes(record)` as defined above.

**selfdef verification algorithm** (the reference is `verify()` in this module):
recompute `canonical_bytes(record)`; select the operator public key by `keyid`;
ed25519-verify `sig` over those bytes. A record whose `signature` is
`unsigned-pending-MS003` is *unsigned*, not *invalid* — selfdef treats it as the
pre-MS003 state, never as a verification failure.

**Trust-anchor provisioning.** `python3 scripts/lib/ms003.py gen-key` writes the
0600 private key and prints the public key (base64url) + keyid; the operator exports
that public value to selfdef as the MS003 trust anchor. `pubkey` re-prints it.

## Scoping — why the primitive ships before the writers

This is PR 1 of a two-PR arc, split on purpose so the cryptographic surface is
reviewed in isolation:

- **PR 1 (this SDD):** the primitive + its tests + provisioning CLI + this
  wire-format contract. Zero record writers touched → zero behavior change on any
  node (no key ⇒ placeholder ⇒ identical output). A reviewer can audit the crypto
  and the selfdef contract without a diff across the intelligence/lifecycle scripts.
- **PR 2 (next):** wire `ms003.sign()` into the ~8 decision/mutation writers that
  currently hard-code the placeholder (`scripts/intelligence/memory-store.py` and
  `memory-decide.py`, `scripts/inference/adapter-decide.py` + `adapter-gate.py`,
  `scripts/lifecycle/approval-decide.py` + `save-state.py` + `session-decide.py` +
  `session-runtime.py`) via `sys.path`-import, each keeping its graceful fallback so
  the no-key path is unchanged, verifying each writer's existing tests still pass.

Because PR 1 changes no writer, **F-2026-034 stays OPEN** — annotated
"producer primitive shipped; writers swept in PR 2; selfdef verifier is its own
milestone" — and only fully closes when PR 2 lands and selfdef consumes the anchor.

## Verification (real, observed)

- `python3 -m pytest tests/unit/test_ms003_sign.py` — **6 passed** (the 2 real-crypto
  cases ran; this box's openssl does ed25519).
- CLI smoke: `gen-key` writes an 0600 key + prints keyid/pubkey; `sign` → a
  `ms003:ed25519:…` string that `verify` accepts; tampering the record or using a
  different key → `verify` returns `False`; the placeholder never verifies; a second
  `gen-key` refuses to clobber.
- `status` on a keyless box: `signing: placeholder (unsigned-pending-MS003)` — the
  unchanged-behavior path.
- `ruff check scripts/lib/ms003.py tests/unit/test_ms003_sign.py` clean.

## Safety invariants

One new `scripts/lib/` module + one new `tests/unit/` file + this SDD + registries.
**No record writer is modified** (that is PR 2); no gatewayd/cockpit/`unsafe`/crate
edits. `sign()` never raises and defaults to the placeholder, so a signing fault can
never break a mutation write. R10212 (selfdef-boundary) and MS043 (offline
survivability) are preserved by construction — signing is local and signs only
records sovereign-os already authors. Collision-safe.

## Non-goals

- The selfdef-side verifier + trust-anchor store — selfdef-owned; this SDD gives it
  the exact contract (wire format + `verify()` reference) to implement against.
- Wiring the record writers — PR 2.
- Key rotation / multi-anchor policy — the `keyid` selector makes it possible; the
  policy is a later increment.
- Adding a Python crypto dependency — deliberately avoided (openssl subprocess).

## Cross-references

- `scripts/lib/ms003.py` — the primitive
- `tests/unit/test_ms003_sign.py` — the tests
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-034 (advanced here), F-2026-063/090 (the CoAT-runtime fix, the other operator-chosen next target)
- `docs/sdd/984-ms003-decision-package.md` — the decision package that surfaced Option B
- R10212 (web-never-arbitrarily-mutates) / MS043 (offline survivability) — the invariants preserved
