# SDD-524 — `/v1/messages` serving-boundary deepening: streaming-constrained decode + config-default route directive

> Status: active · Mandate: **E11.M524** (control-bits band 500–599)
>
> Cross-link: closes two named roadmap tails at the `/v1/messages` serving boundary — SDD-512's *"streaming SSE of the constrained output … deferred"* and SDD-517's *"auto-supplying the `RouteDirective`"*. The twenty-third SDD in the control-bits band.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-24** — operator-directed (*"all of these, a big PR"*).

## Mission

Two serving-boundary tails remained on the Anthropic `/v1/messages` surface:

1. **Streaming-constrained decode (SDD-512 deferral).** The non-streaming path applied the token-law (constrained decode); the streaming path did not — it generated unconstrained. SDD-512 deferred streaming out of a redaction concern.
2. **Auto-supplying the route directive (SDD-517 deferral).** A routing decision that forces the intrinsic egress guards had to be supplied per-request as `token_law.route`; there was no way to make a whole daemon force them by posture.

## Design

### Streaming-constrained `/v1/messages` (piece 4)

The streaming handler (`stream_anthropic_messages`) now parses the request's `token_law` and passes the resolved `law_active` to `generate_chat_with_sampler_law` (it previously passed `None`), so the streamed decode is masked per step by the same M00117 planes the non-streaming path uses. A law-carrying request bound for a **proxy** backend is refused (422) — no logit access out-of-process, matching the non-streaming path.

**The redaction concern that deferred this is resolved by verification, not new code:** the output-safety `StreamGuard` lives **inside** `generate_chat_with_sampler_law` and wraps the constrained + static decode paths **identically** (per that function's own comment), so streamed output has always been secret/PII-safe cross-chunk — the streaming path was already redacted; only the *law* was missing. Confirming this before touching the safety-adjacent path is why no spine change was needed.

### Config-default route directive (piece 3)

`ServingTokenLaw::effective_route()` returns the request's explicit `route` (SDD-517), or a daemon-level default parsed from `SOVEREIGN_GATEWAY_ROUTE_DIRECTIVE` (a JSON `{role,privacy,safety}`) when the request omits one. `route_profile()` resolves through it. So an operator running the daemon in a known egress posture (a box that serves Cloud/Public traffic) forces the egress guards on for token-law-carrying local generation without every request carrying a `route`. The per-request route always wins; unset/empty/invalid env ⇒ no default (the forgiving impure boundary, split into a pure `parse_route_directive` for testability).

### Honest scope

- The config-default route applies to requests that carry a `token_law` (the `ServingTokenLaw` the directive lives on); forcing guards on **bare** requests that carry no `token_law` at all is a further serving-boundary step.
- The **live in-process 7-axis router** derivation SDD-517 also named stays deferred — `/v1/messages` is Anthropic-shaped and carries no 7-axis `TaskAxes`; the config-default posture is the honest auto-supply this surface admits.

## What shipped

- **`sovereign-gatewayd`** — `stream_anthropic_messages` applies `law_active` (+ the proxy-law refusal); `ROUTE_DIRECTIVE_ENV` + `parse_route_directive` + `ServingTokenLaw::effective_route()`; `route_profile()` resolves the effective route. +1 lib test (`parse_route_directive_reads_json_and_rejects_junk`); the streaming law + proxy refusal are guarded by `tests/lint/test_gateway_generation_contract.py`.
- Registration: SDD-524 + INDEX row 524 + mandate **E11.M524** + catalog regen + context `sdd files` (part of the 232→235 batch).

## Non-goals / roadmap

- Forcing egress guards on **bare** (no-`token_law`) requests via the daemon posture.
- Live in-process 7-axis router derivation of the directive (no per-request axes on `/v1/messages`).

## References

- The predecessors: `docs/sdd/512-token-law-serving-boundary.md` (the CONNECT boundary; deferred streaming), `docs/sdd/517-token-law-route-source.md` + `docs/sdd/518` + `docs/sdd/521` (the route source + config surfaces).
- The redaction verification: `crates/sovereign-gatewayd/src/lib.rs` (`generate_chat_with_sampler_law`, the `StreamGuard` output-side spine).
- The wiring: `crates/sovereign-gatewayd/src/main.rs` (`stream_anthropic_messages`), `crates/sovereign-gatewayd/src/lib.rs` (`effective_route`, `parse_route_directive`, `ROUTE_DIRECTIVE_ENV`).
