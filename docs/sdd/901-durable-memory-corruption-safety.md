# SDD-901 — Durable memory: never silently lost (corruption recovery + bounded growth)

> Status: draft
> Owner: operator-directed ("continue" — Phase-1 audit, Arc 3); agent-authored
> Last updated: 2026-07-12
> Number band: **900–999 (general / audit session)** per SDD-100 — this session's reserved band (SDD-900 was the first).
> Closes findings: **F-2026-084** (durable memory — corruption = silent total loss; unbounded growth), *partially* — the corruption-recovery + bounded-growth halves. The decay half is explicitly deferred (see Non-goals). From `docs/review/phase-1/99-findings-ledger.md`.
> Derived from / extends: `sovereign-gatewayd`'s durable-memory path (SDD — the gateway daemon's `SOVEREIGN_GATEWAY_MEMORY` snapshot) + `sovereign-memory-os` (`MemoryStore`).

## Mission

Make the daemon's learned memory **durable in the honest sense** — never silently thrown away. The gateway
daemon persists its learning `Cortex`'s `MemoryStore` to `SOVEREIGN_GATEWAY_MEMORY` on a timer so recall survives
a restart. But the load path was `serde_json::from_str(&json).unwrap_or_else(|_| seed_memory())`: **any** parse
failure — a torn/truncated file from a hard kill, a manual edit, a struct-shape change across versions —
**silently discarded all learned memory** and reseeded, with no signal to anyone. And the store grew without
bound: a daemon that learns on every request accumulated memory forever and re-serialized the whole thing every
snapshot. This SDD makes corruption recoverable (preserve + reseed loudly) and caps growth (value-based, so it
needs no clock).

## Problem

- **Silent total loss on corruption** (`gatewayd/src/lib.rs`): `unwrap_or_else(seed_memory)` on the parsed store
  means a single bad byte wipes months of learned recall with zero operator signal.
- **Unbounded growth**: `Cortex::with_memory(seed_memory())` builds an *unbounded* `MemoryStore`; the daemon
  never capped it, so it grows for the process lifetime and every ~10s snapshot re-serializes the lot.

## What this SDD builds

### 1. `sovereign-memory-os`: `MemoryStore::set_capacity`

`pub fn set_capacity(&mut self, capacity: Option<usize>)` sets (or clears) the bound and **immediately enforces
it**, evicting the lowest-value residents down to the cap via the existing value-based `evict_lowest_value`
(ties → oldest freshness → lowest id). `None` removes the bound. Value-based, so it needs **no wall-clock and can
never over-evict** — the key property that makes it safe to add now (unlike time-decay). Plus a `capacity()`
getter. (`with_capacity` already existed for a fresh store; this lets a daemon cap a store it *seeded or loaded*
unbounded.)

### 2. `sovereign-gatewayd`: corruption-safe load + a capacity bound

- **`load_memory_from(path) -> (MemoryStore, MemoryLoadOutcome)`** — a pure (env-free, unit-testable) loader:
  absent/unreadable ⇒ `Fresh` (seed); valid ⇒ `Loaded`; **unparseable ⇒ move the file aside to `<path>.corrupt`
  (atomic rename) and reseed** ⇒ `Recovered(Some(backup))`. The old bytes are **preserved for forensic recovery,
  never discarded**, and the daemon logs it loudly.
- `with_force_local` now uses it, logs the outcome (resumed N items / recovered-and-backed-up / fresh), then caps
  the store via `set_capacity(memory_capacity_from_env())`.
- **`SOVEREIGN_GATEWAY_MEMORY_CAP`** — the resident-memory cap; default `4096`, `0` ⇒ unbounded.

## Goals

- A corrupt/torn memory file is **never** silently discarded — it's preserved at `<path>.corrupt` and the
  operator is told, so learned state can be recovered.
- Learned memory can't grow without bound; the highest-value memories are kept.
- Zero behaviour change when `SOVEREIGN_GATEWAY_MEMORY` is unset (the common test/dev path) — still a fresh seed.
- Backward-compatible on-disk format: still a raw `MemoryStore` JSON (the persisted shape is unchanged; `capacity`
  serializes with `#[serde(default)]` so old files still load).

## Non-goals

- **Memory decay** (the M028 `maintain(now, ttl)` pass that exists but is never scheduled — the third part of
  F-2026-084). Wiring it correctly needs a **single monotonic clock feeding both admission timestamps and the
  decay call**; today request `now` values are ad-hoc (`0` from `SimpleRequest`, `100` from CoAT), so a decay
  thread on an independent clock could age *everything* or *nothing*. Adding a wrong decay is worse than none —
  it's deferred to a follow-up that first unifies the admission clock. Bounded growth (this SDD) already caps the
  unbounded-accumulation symptom in a clock-independent way.
- **Snapshot-format versioning** — the daemon persists a raw `MemoryStore` (no `schema_version`; that field lives
  on the separate `MemoryOsSnapshot` surface). Migrating the daemon to a versioned snapshot with `validate()` is
  a separate format-migration follow-up; this SDD keeps the format and makes the *load* robust.

## Open questions

| Q | Question | Status |
|---|---|---|
| Q-901-001 | Unify the admission clock (a process monotonic epoch) so the M028 decay pass can be scheduled safely. | open — the deferred decay half |
| Q-901-002 | Move the daemon to a versioned `MemoryOsSnapshot` on disk (schema_version + doctrine + `validate()`) with a migration hook? | open |
| Q-901-003 | Rotate multiple `.corrupt` backups (`.corrupt.1`, …) instead of overwriting a single one? | open — single backup for now |

## Verification

- `cargo test -p sovereign-memory-os` — 40 (2 new: `set_capacity` bounds a previously-unbounded store + evicts
  lowest-value down to it and stays bounded on later admits; `None` removes the bound).
- `cargo test -p sovereign-gatewayd` — lib 55 (4 new: absent path ⇒ fresh seed; valid store round-trips;
  **corruption ⇒ reseed + `.corrupt` backup preserved, original moved aside, bytes recoverable**; cap env default
  is finite), main 4, transports 14.
- `cargo clippy -p sovereign-gatewayd -p sovereign-memory-os --all-targets -- -D warnings` — clean.
- Downstream `sovereign-cortex` / `sovereign-serve` build unchanged. `cargo fmt --all --check` clean.

## Way forward

The decay half (Q-901-001) is the natural follow-up once the admission clock is unified — at which point the
existing `GatewayServer::maintain` can be scheduled from a timer thread safely. Together with this SDD's
corruption-recovery + bounded-growth, that closes F-2026-084 fully.

## Cross-references

- `docs/review/phase-1/99-findings-ledger.md` — F-2026-084 (source finding)
- `crates/sovereign-gatewayd/src/lib.rs` — `load_memory_from`, `MemoryLoadOutcome`, `memory_capacity_from_env`, `with_force_local`
- `crates/sovereign-memory-os/src/engine.rs` — `MemoryStore::set_capacity` / `capacity` / `evict_lowest_value`
- SDD-100 — the per-session number-band convention this SDD's 900-band placement follows
- SDD-900 — real RoPE (this session's prior Arc-1 chunk)
- MS003 `unsigned-pending-MS003`
