# SDD-518 — Operator-configurable route profiles: the route doctrine becomes tunable per role (M00155 DEEPEN)

> Status: active · Mandate: **E11.M518** (control-bits band 500–599)
>
> Cross-link: the first of SDD-517's two named roadmap items — the operator `RouteProfileMap` from config. The seventeenth SDD in the control-bits band, after the route source (SDD-517) shipped with a built-in doctrine only.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-23** — operator-directed (*"next go"*). SDD-517 landed the route token-law source but hard-coded `RouteProfileMap::default()` (the doctrine) at the serving boundary and named "an operator `RouteProfileMap` from config/env" as the natural v2. This is that v2, built the same impure-boundary way the token-law engine's other env config resolves.

## Mission

SDD-517's route source forces the intrinsic egress guards (PII + entropy) on when a task's routing means data can leave the device (Cloud role or Public privacy). That doctrine is sound as a default, but it was **non-negotiable** — the serving boundary always used `RouteProfileMap::default()`. An operator with a different risk posture (e.g. a Cloud tier that is a trusted private VPC, or a Public-but-air-gapped lab) had no way to tune it. This SDD makes the per-role profile map **operator-configurable** via an environment variable, falling back to the doctrine when unset — exactly the pattern the engine already uses for `SOVEREIGN_TOKEN_LAW_MASK_LAYERS` (`MaskLayerSet::from_env_or_all`).

## Design

### The loader — `RouteProfileMap` (in `sovereign-token-law-route`)

Two small additions, no new type:
- `RouteProfileMap::from_json(&str) -> Result<Self, String>` — parse an operator override map. A role omitted keeps the doctrine; a role present with a `RouteProfile` **replaces** it (the SDD-517 override semantics). `{}` is the all-doctrine map.
- `RouteProfileMap::from_env_or_default()` — read the `SOVEREIGN_TOKEN_LAW_ROUTE_PROFILES` env var (const `ROUTE_PROFILES_ENV`); unset, empty, **or a parse error** all fall back to the doctrine (the impure boundary is forgiving, like `from_env_or_all`). The pure core (`resolve` / `doctrine`) is unchanged.

The `serde_json` dependency is added (the crate already derived `Deserialize`); it stays dependency-light otherwise (router-7axis + serde + serde_json).

### The application — `sovereign-gatewayd`

`ServingTokenLaw::route_profile()` now resolves through `RouteProfileMap::from_env_or_default()` instead of `::default()`, so a `route` directive is scored against the operator's map when set, the doctrine otherwise. Nothing else changes — `selection` / `compile` / `is_unconstrained` / `layers_active` already consume the resolved profile.

## What shipped

- **`sovereign-token-law-route`** — `ROUTE_PROFILES_ENV` const + `RouteProfileMap::from_json` + `RouteProfileMap::from_env_or_default`; `serde_json` dep; +3 unit tests (a per-role override parses and applies while omitted roles keep the doctrine; `{}` is the all-doctrine map; malformed JSON is rejected).
- **`sovereign-gatewayd`** — `route_profile()` resolves the operator env map (existing route tests unchanged: with the env unset they exercise the doctrine).
- Registration: SDD-518 + INDEX + mandate E11.M518 + catalog regen + context `sdd files` 228→229 + `tests/lint/test_token_law_route_profile_config_contract.py`.

## Non-goals / roadmap

- **Auto-supplying the `RouteDirective` from the live in-process router** on `/v1/messages` — SDD-517's other roadmap item, still open: the `/v1/messages` path is Anthropic-shaped and carries no 7-axis `TaskAxes`, while the axes-bearing cortex path (`SimpleRequest`) is a different entry point — bridging them is a design decision, deferred.
- **A config *file* (not just env)** — the env var is the v1 surface, matching `SOVEREIGN_TOKEN_LAW_MASK_LAYERS`; a file/osctl surface can layer on later.

## References

- The source this tunes: `docs/sdd/517-token-law-route-source.md` (Non-goals — "operator `RouteProfileMap` from config/env — the natural v2").
- The env-config precedent: `crates/sovereign-token-law-fuse/src/lib.rs` (`MaskLayerSet::from_env_or_all`).
- The loader: `crates/sovereign-token-law-route/src/lib.rs` (`from_json`, `from_env_or_default`, `ROUTE_PROFILES_ENV`).
- The application: `crates/sovereign-gatewayd/src/lib.rs` (`ServingTokenLaw::route_profile`).
