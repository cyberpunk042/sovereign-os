# SDD-974 — workspace-hygiene baseline contract

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-004** (workspace hygiene exemplary — protect the baseline).
> Surfaces finding: **F-2026-096** (202 cockpit crates don't inherit the workspace lints; this SDD's lint is the compensating control, manifest-unification deferred).
> Mandate module: **E11.M974** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

The Phase-1 audit found the crate workspace's hygiene **exemplary** (F-2026-004) and asked for one thing: a lint-contract asserting the invariants *"so the bar never silently drops"*. Exemplary state with no guard rots the moment a hurried change or a new crate family slips past review. This SDD installs the guard.

## Investigation (each invariant re-checked against the tree, 717 crates)

- **Descriptions**: 717/717 member manifests declare a `description` (literal or `.workspace = true`) — **0 missing**.
- **Root lints**: `[workspace.lints.rust]` declares `unsafe_code = "forbid"` + `missing_docs = "warn"`.
- **Per-crate tests**: 716/717 crates carry `#[test]` / `#[cfg(test)]`; the sole exception is `sovereign-feature-selftest` (a marker crate, by design).
- **Markers**: **0** `todo!()` / `unimplemented!()` / `FIXME` / `TODO` in crate `.rs` sources.
- **Absolute paths**: **0** hardcoded `/home` `/Users` `/root` paths in crate `.rs` sources.
- **`unsafe`**: exactly **one** crate uses real `unsafe` — `sovereign-simd`, the sanctioned AVX-512 carve-out that *deliberately* opts out of the workspace lints (`unsafe_code = "allow"`, its manifest documents "the ONE crate permitted `unsafe`, per operator decision").

**One thing the finding overstated** (surfaced honestly as F-2026-096): its claim *"all inherit workspace lints"* does not fully hold. Only **514/717** crates declare `[lints] workspace = true`; **202** (the cockpit family) declare no `[lints]` table at all, so they do **not** inherit the compile-time `unsafe_code = "forbid"` ban. The gap is latent — none of those 202 currently uses `unsafe` — but a future cockpit crate *could* add `unsafe` and the compiler would not stop it.

## What this SDD builds

### `tests/lint/test_workspace_hygiene_baseline.py` — the baseline contract

Six invariant tests, each recomputed from the tree so drift fails CI in **either** direction (the bar can't drop, and a stale allowlist can't hide a fixed exception):

1. root `[workspace.lints.rust]` still declares `unsafe_code = "forbid"` + `missing_docs = "warn"`;
2. every member manifest declares a `description`;
3. every crate carries tests except an explicit `NO_TEST_ALLOWLIST = {sovereign-feature-selftest}` (and the allowlist may not name a crate that now has tests);
4. crate `.rs` sources are marker-free (comment tails + string bodies stripped first, so it matches real `todo!()`/`unimplemented!()` macros + `FIXME`/`TODO`, not the word inside a doc-comment or literal);
5. crate `.rs` sources hardcode no `/home` `/Users` `/root` absolute path;
6. `unsafe` (real `unsafe {`/`fn`/`impl`/`trait`) appears only in `UNSAFE_ALLOWLIST = {sovereign-simd}` — and the allowlist may not name a crate that no longer uses it (keeps the carve-out minimal).

Invariant 6 doubles as the **compensating control** for F-2026-096: even though 202 cockpit crates don't inherit the compile-time ban, this grep-level CI assertion guarantees repo-wide that none of them actually uses `unsafe`, so the ban's *practical* guarantee holds until the manifests are unified.

## Verification

- `python3 -m pytest tests/lint/test_workspace_hygiene_baseline.py` — **6 passed**.
- `ruff check` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Unifying the 202 cockpit manifests** (adding `[lints] workspace = true` so they inherit the ban at compile time) — that's a 202-file mechanical change to a crate family a parallel session is actively growing (714→717 this audit); editing those hot manifests here would collide. It is filed as **F-2026-096** for the cockpit-crate session / operator to own; invariant 6 holds the line in the meantime.
- **Widening the carve-out or the no-test allowlist** — both allowlists are intentionally minimal; growth requires an explicit operator decision, not a silent edit.
- **Banning `unreachable!()`** — it is legitimate, common, and not a work-tombstone; only `todo!()`/`unimplemented!()` are markers.

## Safety invariants

New read-only pytest lint only — no crate code, no manifests touched, no runtime, no gateway. It reads what the repo already ships and asserts the audit-verified baseline. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `tests/lint/test_workspace_hygiene_baseline.py` — the contract
- `Cargo.toml` `[workspace.lints.rust]` — the two load-bearing bans
- `crates/sovereign-simd/Cargo.toml` — the sanctioned `unsafe` carve-out (operator decision)
- `crates/sovereign-feature-selftest/` — the sanctioned no-test marker crate
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-004 (source) + F-2026-096 (surfaced)
- SDD-960 — the sibling workspace-metadata contract (same self-maintaining discipline)
- SDD-962 — the runtime-binaries completeness-lint pattern
- SDD-100 — the per-session number-band convention
