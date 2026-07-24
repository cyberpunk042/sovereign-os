# SDD-521 — Route-profile config-file surface (the persistent v2 of the env override)

> Status: active · Mandate: **E11.M521** (control-bits band 500–599)
>
> Cross-link: the v2 of SDD-518's operator-configurable route profiles — the persistent config-file companion to the `SOVEREIGN_TOKEN_LAW_ROUTE_PROFILES` env var. The twentieth SDD in the control-bits band, directly extending SDD-517/518.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-24** — operator-directed (*"lets continue"*). SDD-518's own named roadmap item: the per-role route→constraint-profile map can now be declared in a **JSON file**, not only inline in an env var.

## Mission

SDD-517 bound routing decisions to token-law profiles (the doctrine); SDD-518 made that per-role map operator-configurable via `SOVEREIGN_TOKEN_LAW_ROUTE_PROFILES` — an inline JSON env var. That is ergonomic for a one-role tweak but awkward for a real multi-role map: a JSON object covering `conductor` / `logic` / `oracle` / `cloud`, each with three flags, is unwieldy (and un-diffable) as a single environment string. SDD-518 named the fix in its non-goals: *"a config FILE surface (env is the v1, matching the mask-layers env)."* This ships it: the same map, in a file, resolved with a clear precedence and the same forgiving-fallback semantics.

## Design

### The loader — `sovereign-token-law-route`

- `ROUTE_PROFILES_FILE_ENV` const (`SOVEREIGN_TOKEN_LAW_ROUTE_PROFILES_FILE`) — names a JSON file whose contents are the *same* shape `RouteProfileMap::from_json` already parses (no new format; the file is just the JSON somewhere durable).
- `RouteProfileMap::from_file(path) -> Result<Self, String>` — `std::fs::read_to_string` + `from_json`. An unreadable file or invalid JSON is an `Err`; the forgiving fallback lives in `from_env_or_default`.
- `from_env_or_default` gains the file surface with a fixed **precedence**: the **inline** `ROUTE_PROFILES_ENV` JSON wins (the most explicit, per-run override), then the `ROUTE_PROFILES_FILE_ENV` **file** (the persistent config), then the all-doctrine `default`. Unset / empty / unreadable / parse-error at any surface falls through to the next — the same impure boundary SDD-518 established (and the token-law engine's `MaskLayerSet::from_env_or_all`).
- The precedence is factored into a **pure** `resolve_env(inline, file)` helper so the ordering is unit-testable without mutating the process environment; `from_env_or_default` is the thin `std::env::var` wrapper over it. The pure `resolve` / `doctrine` core is unchanged.

### The serving boundary — `sovereign-gatewayd`

**Unchanged.** `ServingTokenLaw::route_profile()` already resolves through `RouteProfileMap::from_env_or_default()` (SDD-518); the file surface is transparent to it — a request routed with a `route` directive is now scored against the operator's file when set, the inline env when set, and the doctrine otherwise, with no gatewayd change.

### Honest scope

- The file is read at the serving boundary on each `from_env_or_default()` resolve (the same call site SDD-518 introduced) — there is no caching or watch; a changed file takes effect on the next resolve. This matches the env var's live-read semantics.
- Precedence is inline-env-over-file by design (an ephemeral per-run override should beat a persistent config, the conventional CLI/env-over-file order). An operator who wants the file to be authoritative simply leaves `ROUTE_PROFILES_ENV` unset.
- No new dependency: `std::fs` only (the crate stays `sovereign-router-7axis` + `serde` + `serde_json`, `forbid(unsafe_code)`).

## What shipped

- **`sovereign-token-law-route`** — `ROUTE_PROFILES_FILE_ENV` const + `from_file` + the pure `resolve_env` precedence helper; `from_env_or_default` rewired to inline-env → file → doctrine. +3 unit tests (a file parses + applies while omitted roles keep the doctrine; a missing/malformed file is an `Err`; the pure precedence — inline wins over file, empty inline falls to the file, neither ⇒ doctrine, an unreadable path ⇒ doctrine). Route-crate tests 10 → 13.
- **`sovereign-gatewayd`** — no change (already resolves through `from_env_or_default`).
- **`tests/lint/test_token_law_route_profile_config_contract.py`** — extended with SDD-521 assertions: the file-env const, `from_file`, the `resolve_env` precedence helper, and the doc.
- Registration: SDD-521 + INDEX row 521 + mandate **E11.M521** + catalog regen + context `sdd files` 231→232.

## Non-goals / roadmap

- **A default config-file path** (reading, say, `config/token-law-route-profiles.json` with no env var set) — v1 requires the operator to name the file via the env var, matching how the inline env is opt-in; a well-known default path is a natural v3.
- **File-watch / hot-reload** — the file is read on each resolve (live enough); a watcher that avoids the per-resolve read is a perf item, not a capability gap.
- Auto-supplying the `RouteDirective` from the live in-process router on `/v1/messages` — SDD-517's still-open roadmap item, operator/design-gated (the Anthropic-shaped `/v1/messages` carries no 7-axis `TaskAxes`).

## References

- The predecessors: `docs/sdd/517-token-law-route-source.md` (the doctrine + serving application), `docs/sdd/518-token-law-route-profile-config.md` (the env override; its non-goals named this file surface).
- The loader: `crates/sovereign-token-law-route/src/lib.rs` (`ROUTE_PROFILES_FILE_ENV`, `from_file`, `resolve_env`, `from_env_or_default`).
- The serving boundary (unchanged): `crates/sovereign-gatewayd/src/lib.rs` (`ServingTokenLaw::route_profile`).
- The guard: `tests/lint/test_token_law_route_profile_config_contract.py`.
