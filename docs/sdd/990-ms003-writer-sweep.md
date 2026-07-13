# SDD-990 — MS003 writer sweep: wire the signing primitive into the decision-writers (F-2026-034)

> Status: draft
> Owner: operator-directed 2026-07-13 ("MS003 implementation arc"; *"we do not minimize, we do this right"*); agent-authored.
> Advances: **F-2026-034** (MS003). PR 2 of the arc — consumes the SDD-989 primitive.
> Mandate module: **E11.M990**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

SDD-989 shipped the producer primitive (`scripts/lib/ms003.py`) in isolation.
This is **PR 2**: it wires `ms003.sign()` into the eight runtime decision/mutation
writers that until now hard-coded the `unsigned-pending-MS003` placeholder in every
record's `signature` field — so that, on a node with an operator key provisioned,
every persisted mutation/decision record carries a **real ed25519 signature** that
selfdef can verify, while a keyless node's output stays **byte-identical** to before.

## The eight writers swept

| Family | File | Records signed |
|---|---|---|
| intelligence | `scripts/intelligence/memory-store.py` | forget-change ledger entry (+ re-signed on undo), memory audit spans, forget/undo/purge results |
| intelligence | `scripts/intelligence/memory-decide.py` | approve/reject decision + history entry + result |
| inference | `scripts/inference/adapter-decide.py` | registry entry, history entry, promote/demote decision + result |
| inference | `scripts/inference/adapter-gate.py` | gate-pass ledger record + result |
| lifecycle | `scripts/lifecycle/approval-decide.py` | approval record, decision + result |
| lifecycle | `scripts/lifecycle/save-state.py` | save-state manifest record, save/restore ledger entries, audit spans |
| lifecycle | `scripts/lifecycle/session-decide.py` | hibernate/resume/kill decision + result, hibernate-all result |
| lifecycle | `scripts/lifecycle/session-runtime.py` | reaper reap ledger record + audit span |

## The uniform seam

Each writer gained a small best-effort import block + two helpers:

```python
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    import ms003 as _ms003
except Exception:
    _ms003 = None

def _sign(record):   # keyless / import-failure → the historical placeholder
    return _ms003.sign(record) if _ms003 is not None else _UNSIGNED

def _signed(record):  # set record['signature'] in place + return the record
    record["signature"] = _sign(record)
    return record
```

Then every record-construction site is wrapped: `return {...}` → `return _signed({...})`,
`.append({...})` → `.append(_signed({...}))`, span dicts likewise. Because
`ms003.canonical_bytes()` **excludes the `signature` field** before signing, leaving
the pre-existing `"signature": _UNSIGNED` literal inside the wrapped dict is harmless
(it is overwritten and never enters the signed bytes) — which keeps the diff minimal
and the record shape obvious.

**Two site shapes needed care:**
1. **Assignment-then-append-fields** (`adapter-decide` registry entry,
   `approval-decide` approval record): fields are added *after* the `signature`
   line, so signing happens after the record is fully assembled (`_signed(entry)` /
   `_signed(target)` right before it is stored), not at the placeholder line.
2. **Mutate-in-place-then-rewrite** (`memory-store` undo flips `reversed: True`):
   MS003 signatures are point-in-time, so the change record is **re-signed** after
   the mutation, before the rewrite.

**Provenance spans that borrow a decision's signature** (`memory-decide`,
`adapter-decide`, `approval-decide` `_emit_span`) are left as-is — the span carries
the *decision's* signature as a linkage, and the decision is signed before the span
is emitted. Spans that self-build a `signature` field (`memory-store`, `save-state`,
`session-runtime`) are signed directly.

## Graceful fallback = zero behaviour change without a key

`ms003.sign()` returns the `unsigned-pending-MS003` placeholder when no operator key
is present and never raises; `_sign` also falls back if the import fails. So on every
node that has not provisioned an operator key — which is every node today, and every
CI runner — the writers emit exactly the same placeholder they did before. Real
signatures switch on the moment an operator runs `python3 scripts/lib/ms003.py gen-key`.

## Verification (real, observed)

- **NEW `tests/unit/test_ms003_writer_signing.py`** — 4 tests proving the wiring
  end-to-end across two families + both import styles: with a provisioned key,
  `memory-decide` (in-process) and `approval-decide` (subprocess) write a **durable
  ledger record whose signature `ms003.verify()` accepts**, and tampering the record
  breaks verification; without a key both fall back to the placeholder. **4 passed**
  (the 2 real-crypto cases ran).
- Every swept writer's existing unit suite is green (keyless → placeholder, so the
  `signature == "unsigned-pending-MS003"` assertions still hold): memory-store 31,
  memory-decide 18, adapter-decide 20, adapter-gate 21, approval-decide 10,
  save-state 18, session-decide 18, session-runtime 17.
- **Full `tests/unit` — 505 passed.** `ruff check` clean on all eight writers + the
  new test.

## Scope / safety

Eight `scripts/` writers gain the import block + `_signed(...)` wrappers; one new
`tests/unit/` file; this SDD + registries. No new dependency (the primitive shells
to `openssl`), no gatewayd/cockpit/`unsafe`/crate edits. Signing is best-effort and
never raises, so it cannot break a mutation write. R10212 (selfdef boundary) + MS043
(offline survivability) preserved — signing is local and signs only records
sovereign-os already authors. Collision-safe.

## F-2026-034 status after this PR

**Producer half COMPLETE** (primitive + all writers wired). **Still open**: the
**selfdef-side verifier + trust-anchor store** — a selfdef-owned milestone — must
consume the wire-format contract (`ms003:ed25519:<keyid>:<sig>`) and the exported
operator public key. F-2026-034 fully closes when selfdef verifies sovereign-os
signatures against the anchor.

## Non-goals

- The selfdef verifier (selfdef-owned; has the contract from SDD-989).
- Key rotation / multi-anchor policy (the `keyid` selector enables it; policy later).
- Signing records outside these eight writers (no other `unsigned-pending-MS003`
  producers exist in `scripts/` — the sweep is complete for the runtime writers).

## Cross-references

- `scripts/lib/ms003.py` — the primitive (SDD-989)
- `docs/sdd/989-ms003-signing-primitive.md` — PR 1 (the primitive + wire format)
- `tests/unit/test_ms003_writer_signing.py` — the end-to-end wiring proof
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-034 (advanced here)
- R10212 (web-never-arbitrarily-mutates) / MS043 (offline survivability) — invariants preserved
