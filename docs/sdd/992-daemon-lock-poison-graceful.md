# SDD-992 — the gateway daemon survives a poisoned lock instead of cascading (F-2026-065)

> Status: draft
> Owner: operator-directed 2026-07-13 (phase-1 audit continuation); agent-authored.
> Closes: **F-2026-065** (LOW) — the daemon-path half.
> Mandate module: **E11.M992**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## The bug

Every mutex access on the gateway's request path used `.lock().expect("… poisoned")`.
A `Mutex` becomes **poisoned** when a thread panics while holding its guard — and a
poisoned lock **stays** poisoned, so *every* `.lock().expect()` after it panics too.
On a `type=root`-adjacent daemon that is a cascade: one panicking request thread
takes the whole daemon down, one request at a time. F-2026-065 named exactly this:
"a future refactor panics the request thread, and lock poisoning would cascade to
every request."

15 sites across the daemon path (`crates/sovereign-gatewayd/src/lib.rs`): the
`cortex` mutex (`infer` / `explain` / `decide` / `deliberate` / `coat` / `maintain`
/ `persist_memory`) and the `ledger` mutex (dry-run + request counters, health,
Prometheus metrics, the `Ledger` response).

## The fix — two guards, matched to what each lock protects

The finding's action: "convert to error returns on the daemon path; keep expects in
pure-lib contexts." Two helpers encode the right response per lock:

```rust
/// The Cortex is the decision engine; a poisoned lock means a prior panic
/// mid-mutation, so it may hold torn state — DECLINE the request.
fn cortex_guard(&self) -> Result<MutexGuard<'_, Cortex>, GatewayResponse> {
    self.cortex.lock().map_err(|_| GatewayResponse::Error {
        message: "cortex lock poisoned — request declined".to_string(),
    })
}

/// The Ledger is pure counters; a poisoned lock holds nothing worth declining a
/// request over — RECOVER the guard and keep serving.
fn ledger_guard(&self) -> MutexGuard<'_, Ledger> {
    self.ledger.lock().unwrap_or_else(|e| e.into_inner())
}
```

- **Cortex** → *decline*: every request handler returns `GatewayResponse::Error`
  on poison instead of panicking (`match self.cortex_guard() { Ok(g) => g, Err(e) =>
  return e }`). `persist_memory` (returns `io::Result`) maps poison to an I/O error;
  `maintain` (periodic hygiene, returns `usize`) skips the cycle (`return 0`) — it
  runs again next tick. The daemon never serves possibly-torn engine state.
- **Ledger** → *recover*: `into_inner()` takes the guard through the poison. The
  guarded ops are counter increments (`total_requests += 1`, `dry_runs += 1`) that
  can't tear meaningfully, and dropping an already-computed successful response over
  a stat lock would be the wrong trade.

**Kept as-is (correct per the finding)**: the two `sovereign-coat` `.expect()`s
(`chosen.expect("seeds non-empty")`, `thought.expect("non-root on best path")`) are
**pure-lib invariant guards** inside the search algorithm — they document conditions
the algorithm establishes, not runtime lock state. The finding explicitly says to
keep pure-lib expects; converting them would plumb `CoatError` through the search
harness for invariants that hold by construction. Left untouched.

## Verification (real, observed)

Three new tests poison a mutex the real way — a thread panics while holding the
guard (stderr silenced) — then assert the daemon's graceful behaviour:

- **`cortex_guard_declines_a_poisoned_lock_instead_of_panicking`** — a poisoned
  cortex yields `Err(GatewayResponse::Error { message: "…poisoned…" })`, not a panic.
- **`infer_on_a_poisoned_cortex_returns_error_not_panic`** — end-to-end: the
  `/v1/infer` handler returns a graceful `Error` over a poisoned cortex.
- **`ledger_guard_recovers_a_poisoned_lock_and_keeps_serving`** — a poisoned ledger
  is recovered; `health()` still returns its counters instead of panicking.

`cargo test -p sovereign-gatewayd` — **71 lib + 4 + 18 integration passed** (was 68
lib; +3). `cargo fmt --all --check` (CI-exact) exit 0; `cargo clippy -p
sovereign-gatewayd --all-targets` clean.

## Scope / safety

`crates/sovereign-gatewayd/src/lib.rs` only (2 new private helpers + 15 call-site
conversions + 3 tests). No `sovereign-coat` change (pure-lib expects kept), no
cockpit/webapp/`scripts/operator`/crate-API change; collision-safe; no new
dependency. R10212/MS043 untouched. MS003 `unsigned-pending-MS003`.

## Non-goals

- Converting the `sovereign-coat` pure-lib invariant expects (the finding says keep
  them; they are not daemon lock state).
- Making the guarded operations themselves panic-free (a separate concern — this
  bounds the *blast radius* of any such panic to one declined request, no cascade).
- Broader `.unwrap()`/`.expect()` audits elsewhere in the tree.

## Cross-references

- `crates/sovereign-gatewayd/src/lib.rs` — `cortex_guard` / `ledger_guard` + the converted handlers
- `crates/sovereign-coat/src/lib.rs` — the two pure-lib invariant expects (kept)
- `docs/sdd/991-coat-cortex-lock-narrowing.md` — SDD-991 already softened the CoAT recall poison path (empty recall); this generalizes the graceful-poison treatment to every daemon lock
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-065 (closed here)
