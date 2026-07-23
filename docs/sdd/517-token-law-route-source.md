# SDD-517 — The route token-law source: bind a routing decision to a constraint profile (M00155 DEEPEN)

> Status: active · Mandate: **E11.M517** (control-bits band 500–599)
>
> Cross-link: the **last** M00117 plane — the *route* source the milestone always named but left unbuilt. The sixteenth SDD in the control-bits band, after the Expose arc (SDD-507/510/511), the Connect fork (SDD-512), and the Deepen slices (SDD-513 entropy, SDD-514 incremental fusion, SDD-515 SIMD, SDD-516 PII).
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-23** — operator-directed (*"you can be unblocked, you have my go"* + a QCFA design decision selecting **config-driven profile binding**). The route source was parked across SDD-513/514/515/516 because there is no honest `SrpRole → allow-bitset` table; the operator's decision resolves the semantics.

## Mission

The M00117 milestone named a *route* plane beside grammar / regex / safety / policy, but it stayed unbuilt for an honest reason. The 7-axis router (`sovereign-router-7axis`) outputs an `SrpRole` — a **compute tier** (`Conductor` = CPU, `Logic` = RTX 5090, `Oracle` = Blackwell, `Cloud`), *not* a vocabulary subset. Which GPU runs a task says nothing about which **tokens** are allowed, so a direct role→token mapping would be invented, not honest. What the routing decision *does* carry that is token-law-relevant is its **axes** — `privacy` (Public ⇒ cloud egress is acceptable) and `safety` — plus whether the chosen role sends data **off the device** (`Cloud`).

So the route is a source not by mapping a role to tokens, but by **binding a routing decision to a token-law profile**: when a task's placement means personal data or secrets could leave the device, the engine **forces the intrinsic egress guards on** — the PII-completion plane (SDD-516) and the entropy plane (SDD-513) — no matter what the request asked for. Routing a task to the cloud is exactly when the strictest data-egress constraints should be non-optional.

## The design decision (operator-selected)

The operator selected **config-driven profile binding** (QCFA, 2026-07-23) over hard-wired axis escalation or leaving it parked. The route resolves the decision to a named profile of **forced-on** planes, with a built-in doctrine and an operator per-role override.

### The doctrine (built-in default)

> **Data leaves the device** when the role is `Cloud` OR the privacy envelope is `Public`. Then: force PII + entropy on. And when safety is `Risky`: keep the safety denylist selected. A **local, private, safe** task gets a no-op profile — routing forces nothing.

An operator `RouteProfileMap` overrides the profile per role (a present override **replaces** the doctrine for that role; the operator takes full control). v1 uses the default doctrine at the serving boundary; wiring an operator-supplied map from config is a roadmap item.

### Complement, never replace

The route only ever forces guards **on**, never off. A stricter per-request `token_law` stays strict; a lax one is tightened when its routing demands it. A request's `mask_layers` can never **deselect** a route-forced guard (the serving selection re-forces it).

## Design

### The source — `sovereign-token-law-route` (NEW crate, dependency-light)

Deliberately minimal: it carries only the decision logic and a `RouteProfile` of **flags** (`force_pii` / `force_entropy` / `force_safety_denylist`), depending on `sovereign-router-7axis` for the axis types and `serde` for the operator config — it never depends on the plane crates. `RouteDirective { role, privacy, safety }` is the wire shape a serving request carries; `RouteProfileMap::{doctrine, resolve, resolve_directive}` resolve it. `forbid(unsafe_code)`; +7 unit tests (cloud forces guards, public forces guards on a local role, local-private-safe is a no-op, risky keeps the denylist, an operator override replaces the doctrine, directive parity).

### Applied at the serving boundary — `sovereign-gatewayd`

`ServingTokenLaw` gains an optional `route: RouteDirective`. The serving path applies the resolved profile using the constraint types it already holds:
- `selection()` folds the profile in — a route-forced guard's mask-layer is set true, so `mask_layers` can't deselect it;
- `compile()` falls back to the plane defaults (`EntropyRequest::default()` / `PiiRequest::default()`) for a forced guard the request omitted, so a routed-to-cloud request is guarded even with no explicit `entropy`/`pii`;
- `is_unconstrained()` is false when the route forces an egress guard on;
- `layers_active()` reports a guard when the request supplied it **or** the route forced it.

+3 gatewayd tests (cloud route forces PII+entropy on an otherwise-empty law; local-private-safe stays unconstrained; a route re-forces a guard `mask_layers` tried to drop).

## What shipped

- **NEW crate `sovereign-token-law-route`** (728→729) — `RouteProfile` / `RouteDirective` / `RouteProfileMap` (doctrine + per-role override), `serde`, `forbid(unsafe_code)`, deps `sovereign-router-7axis` only, +7 unit tests.
- **`sovereign-gatewayd`** — `ServingTokenLaw.route` + the profile applied through `selection` / `compile` / `is_unconstrained` / `layers_active`; +3 tests.
- Registration: SDD-517 + INDEX + mandate E11.M517 + catalog regen + context `sdd files` 227→228 + `workspace crates` 728→729 + crate-inventory + rustdoc-panel catalog regen + `tests/lint/test_token_law_route_source_contract.py`.

With this the M00117 engine's **route** source is built — the token-law engine now has all its named sources (grammar · regex · denylist · regex-denylist · policy · entropy · PII · route).

## Non-goals / roadmap

- **Operator `RouteProfileMap` from config** — v1 uses the built-in doctrine at the serving boundary; plumbing an operator-supplied per-role override map from a config file/env is the natural v2.
- **Auto-supplying the `RouteDirective` from the live router in the `/v1/messages` path** — v1 takes the directive on the request (the caller supplies it from the router's `RouteDecision` + axes); binding it to the in-process router decision is a follow-up.

## References

- The parked-plane history: `docs/sdd/513-token-law-entropy-plane.md`, `docs/sdd/516-token-law-pii-plane.md` (Non-goals — "the route plane … needs a `SrpRole → vocab-bitset` design decision").
- The router: `crates/sovereign-router-7axis/src/lib.rs` (`SrpRole`, `Privacy`, `Safety`, `RouteDecision`).
- The source: `crates/sovereign-token-law-route/src/lib.rs` (`RouteProfile`, `RouteProfileMap`, `RouteDirective`).
- The forced guards: `crates/sovereign-token-law-pii/src/lib.rs` (SDD-516), `crates/sovereign-token-law-entropy/src/lib.rs` (SDD-513).
- The serving boundary: `crates/sovereign-gatewayd/src/lib.rs` (`ServingTokenLaw`).
