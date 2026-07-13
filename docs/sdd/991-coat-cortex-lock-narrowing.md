# SDD-991 — CoAT no longer serializes generation: narrow the cortex lock to per-recall (F-2026-063/090)

> Status: draft
> Owner: operator-directed 2026-07-13 ("MS003 implementation arc, CoAT-through-jobs runtime fix"); agent-authored.
> Advances: **F-2026-063** (MED) + **F-2026-090** (OPP). Touches a bonus corner of **F-2026-065**.
> Mandate module: **E11.M991**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## The bug (root cause, precisely located)

`GatewayServer::coat()` (`crates/sovereign-gatewayd/src/lib.rs`) ran the whole CoAT
deliberation **while holding the shared cortex mutex**:

```rust
let cortex = self.cortex.lock().expect("cortex poisoned");   // held for the WHOLE loop
let memory = CortexRecall { cortex: &cortex, now, half_life };
… CoatEngine::new(ModelThoughts { server: self, model }, memory, cfg).deliberate(&prob)
```

`CortexRecall` borrowed `&Cortex`, so the `MutexGuard` lived for the entire
`deliberate()` — up to **12 model-backed expansions**. `self.cortex: Mutex<Cortex>`
is the **same** mutex every other decision surface locks (`infer()`, `explain`,
`simple`, `deliberate`, and every other `/v1/coat`). So a single model-backed CoAT
request **serialized all other generation behind one lock** for the full multi-second
deliberation — exactly F-2026-090's "calls the model once per expansion holding the
generation mutex — serially blocks all other generation," and the mechanism behind
F-2026-063's "blocks the HTTP handler."

By contrast `infer()` holds the same mutex only **briefly** — one scoped
`act_and_learn`, then releases. CoAT was the outlier.

## The fix

Make `CortexRecall` borrow the **mutex**, not a guard, and lock **per recall** — the
same short-hold pattern `infer()` uses:

```rust
struct CortexRecall<'a> { cortex: &'a Mutex<Cortex>, now: u64, half_life: u64 }

fn recall(&self, ctx: &ThoughtContext, k: usize) -> Vec<Recall> {
    …
    let hits = match self.cortex.lock() {
        Ok(cortex) => cortex.recall(topic, entity, self.now, self.half_life, k),
        Err(_) => return Vec::new(),   // poison → no recall, never a panic
    };
    …
}
```

and `coat()` no longer pre-locks — it hands `CortexRecall { cortex: &self.cortex, … }`
to the engine and lets each recall take the lock for its own duration. Between the
≤12 expansions the cortex mutex is **free**, so `/v1/infer` (and every other decision
surface, and other `/v1/coat` requests) interleave instead of blocking for the whole
deliberation.

**Why this is the right fix, not "route through jobs" alone.** The finding suggested
steering the caller to the background-jobs runtime. But `_run_deliberation` just issues
the *same* synchronous `POST /v1/coat` — so moving the caller to a background thread
would **not** have removed the gatewayd-side lock-hold; a jobs-driven CoAT would still
have serialized `/v1/infer` behind `self.cortex`. The serialization had to be fixed
**in `coat()`**, and it now is. (The generator mutex is still taken per model call
inside `generate_chat` — that is the correct, inherent serialization of actual token
generation, and it is released between expansions.)

**Safety.** A CoAT deliberation is read-only on the cortex (it recalls, never learns —
"a deliberation never pollutes memory"). Per-recall locking means a concurrent
`infer()` may `act_and_learn` *between* a deliberation's recalls; each recall is still
internally consistent (locked), the freshness clock (`now`/`half_life`) is frozen at
call time, and associative recall is advisory — so a slightly-evolving memory across
iterations is benign, even desirable (it's the concurrency the finding wants). The
poison path now **degrades to empty recall** instead of panicking the request thread
mid-deliberation — softer than the whole-loop `.expect()` it replaced (a small nod to
F-2026-065's daemon-path-panic concern, scoped to this method).

## Verification (real, observed)

- **NEW `coat_recall_releases_the_cortex_lock_between_recalls`** — after a recall,
  `s.cortex.try_lock().is_ok()` (the guard was dropped; a concurrent `/v1/infer`
  would not block on it).
- **NEW `coat_does_not_hold_the_cortex_lock_across_deliberation`** — a full heuristic
  `/v1/coat` deliberation returns a trace AND leaves `s.cortex.try_lock().is_ok()` —
  the whole-loop hold is gone end-to-end.
- Existing CoAT tests unchanged-green: `coat_recall_normalization_keeps_weak_hits_weak`,
  `post_coat_deliberates_with_associative_recall_read_only`, `coat_rungs_and_errors`,
  `coat_accepts_a_model_hint`.
- `cargo test -p sovereign-gatewayd` — **68 lib + 18 integration passed**;
  `cargo fmt --all --check` (CI-exact) exit 0; `cargo clippy -p sovereign-gatewayd
  --all-targets` clean.

## Scope / safety

`crates/sovereign-gatewayd/src/lib.rs` only (the `CortexRecall` struct + `recall` +
`coat`) + two new unit tests. **No cockpit, no webapp, no `scripts/operator`, no crate
API change** (`CortexRecall` is a private struct) — collision-safe. No new dependency.
R10212/MS043 untouched. MS003 `unsigned-pending-MS003` (this path writes no signed
record).

## What remains (named follow-ups — deliberately out of scope)

- **Async caller (webapp → jobs)** — F-2026-063's "runs synchronously on the request
  thread" is *mitigated* (it no longer blocks *other* requests) but the calling
  request still awaits its own deliberation. Making the brain webapp submit a
  `"deliberation"` job + poll (the jobs runtime + `sovereign-osctl jobs submit
  deliberation` CLI already exist) is a **webapp-surface** change — currently contended
  by the active cockpit-crates work — so it is deferred to a clear-lane follow-up.
- **Model-backed integration test** — every `/v1/coat` test today runs with no
  generator loaded (`thought_source: "heuristic"`). A test asserting
  `thought_source == "model"` end-to-end needs a synthetic loadable model-dir fixture
  (`config.json` + `*.safetensors` + `tokenizer.json` for `SOVEREIGN_GATEWAY_MODEL`);
  that fixture is a separate infrastructure task that also unblocks F-2026-066
  (cross-daemon integration). Deferred there.

## Non-goals

- Converting `self.cortex` to an `RwLock` (would let concurrent CoAT *reads* run fully
  parallel, but is an architecturally-significant refactor across every decision
  surface — an operator-level decision, not folded in here).
- The generator-mutex behaviour (correct as-is: serialize actual generation, release
  between expansions).

## Cross-references

- `crates/sovereign-gatewayd/src/lib.rs` — `CortexRecall` / `coat()` (the fix)
- `crates/sovereign-coat/src/lib.rs` — the generic `CoatEngine::deliberate` loop (unchanged)
- `scripts/operator/jobs-api.py` — `_run_deliberation` (the existing jobs path; the async-caller follow-up wires the webapp to it)
- `docs/src/gateway-api-reference.md` — the `/v1/coat` route (SDD-983)
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-063 / F-2026-090 (advanced here), F-2026-065 / F-2026-066 (the follow-up anchors)
