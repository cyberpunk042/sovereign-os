# SDD-206 — The gateway safety spine (input screening + output redaction, made real on the daemon)

> Status: draft
> Owner: operator-directed ("lets get started, pick a big chunk and lets do it in a big PR"); agent-authored
> Last updated: 2026-07-12
> Closes findings: F-2026-081 (security crates absent from `gatewayd`), F-2026-082 (no auth / no TLS / no socket timeouts), and the transport half of the gateway-hardening arc. From `docs/review/phase-1/99-findings-ledger.md` (Arc 2 — "wire the safety spine into the daemon").
> Derived from / extends: the M048 `sovereign-gateway` responsibility contract (the gateway's declared **Privacy** + **Redaction** duties), `sovereign-gatewayd`, and the four already-built-and-tested security crates that were wired only into the parallel, non-daemon `sovereign-serve` orchestrator.

## Mission

Make the daemon actually enforce the safety it *claims*. `sovereign-gateway` declares Privacy + Redaction as
first-class gateway responsibilities, but the running daemon `sovereign-gatewayd` did **none** of it: prompts
and generated text passed through `generate_chat` unfiltered, `sovereign-{pii-redact,secret-scan,injection-detect,toxicity}`
were consumed only by `sovereign-serve` (which the daemon never invokes), and the HTTP surface had no auth, no
per-connection timeout, and dropped over-capacity connections with a bare reset. This SDD wires the safety
spine into the one generation chokepoint and hardens the transport — turning built-but-unwired libraries into
live enforcement. This is the audit's #1 theme (wiring existing tested crates) applied to its highest-value target.

## Problem

- **The security crates are dead relative to the daemon.** `generate_chat` (the single path behind all four
  generation surfaces — OpenAI stream/non-stream + Anthropic Messages stream/non-stream) applied no redaction
  or screening. A model that echoed a secret from its prompt, or generated a plausible-looking key, leaked it
  verbatim.
- **The transport is exposed.** No `Authorization` check, so `--addr 0.0.0.0:…` (a documented first-class mode)
  put memory-mutating routes and `/admin/ledger` in reach of any client. No read/write deadline, so a slow-loris
  peer pinned a handler thread; with the 256-thread cap, enough of them wedged the daemon. Over-cap connections
  were `drop`ped silently (a reset, not a retryable status).

## What this SDD builds

### 1. The safety spine (`sovereign-gatewayd` lib)

A `GuardConfig` resolved once from the environment (secure-by-default) drives, inside `GatewayServer::generate_chat`:

| Stage | Action | Default |
|---|---|---|
| **Input — injection** | `sovereign_injection_detect::scan(prompt)`; at/above `injection_threshold`, tally + log, and (if `block_injection`) refuse with a clear error | screen **on**, block **off** (fail-open) |
| **Output — secrets** | cross-chunk-safe streaming redaction via `sovereign_secret_scan` | on |
| **Output — PII** | cross-chunk-safe streaming redaction via `sovereign_pii_redact` | on |
| **Output — toxicity** | `sovereign_toxicity` score, **flag-only** (logged, never censored) | on |

The load-bearing piece is `StreamGuard`, a redactor that is correct **across decode-chunk boundaries**: it holds
back a trailing window (`STREAM_GUARD_WINDOW = 256` bytes ≥ the longest secret/PII token) and only releases up to
the last ASCII-whitespace boundary before that window. Because every secret/PII pattern here is a single
whitespace-free token, no match can straddle a release cut — so a secret split across two generated chunks is
still caught before *any* byte leaves the box. Memory is bounded (≈ window + one chunk); generation is capped at
`max_new` regardless. Redaction defaults **on**; injection *blocking* defaults **off** so a false positive logs a
tripwire without silently swallowing a legitimate prompt (the operator opts into hard blocking). Toxicity is
flag-only, consistent with the project's honest, non-editorializing doctrine.

Process-lifetime tallies (`guard_injections`, `guard_secrets`, `guard_pii`) are exposed on `/metrics`
(`sovereign_gateway_guard_{injections,redactions,enabled}`) so an operator can see the spine is live.

### 2. Transport hardening (`sovereign-gatewayd` bin)

- **Bearer auth.** `SOVEREIGN_GATEWAY_TOKEN`, when set, requires `Authorization: Bearer <token>` on every HTTP
  request (case-insensitive scheme, constant-time token compare) — else `401`. Unset ⇒ open (loopback default).
  This is the minimum gate that lets the daemon bind beyond loopback safely, and matches what OpenAI/Anthropic
  clients already send.
- **Per-connection deadline.** `SOVEREIGN_GATEWAY_TIMEOUT_SECS` (default 30; `0` disables) sets read + write
  timeouts on every accepted socket in the shared `serve` accept loop, bounding slow-loris.
- **Honest back-pressure.** Over-capacity connections now receive a protocol-appropriate rejection — HTTP `503`
  + `Retry-After: 1`, or an NDJSON error line — instead of a silent `drop`.

## Configuration surface (all new env knobs)

```
SOVEREIGN_GATEWAY_TOKEN                       # HTTP bearer gate (unset = open)
SOVEREIGN_GATEWAY_TIMEOUT_SECS               # per-conn read/write deadline (default 30; 0 = off)
SOVEREIGN_GATEWAY_GUARD                       # master switch (default on)
SOVEREIGN_GATEWAY_GUARD_REDACT_SECRETS        # default on
SOVEREIGN_GATEWAY_GUARD_REDACT_PII            # default on
SOVEREIGN_GATEWAY_GUARD_SCREEN_INJECTION      # default on
SOVEREIGN_GATEWAY_GUARD_BLOCK_INJECTION       # default off (log-only)
SOVEREIGN_GATEWAY_GUARD_INJECTION_THRESHOLD   # [0,1], default 0.5
SOVEREIGN_GATEWAY_GUARD_TOXICITY              # flag-only, default on
```

## Goals

- Every generation surface (OpenAI + Anthropic, stream + non-stream) inherits the spine from the single
  `generate_chat` chokepoint — no per-surface duplication.
- Correct-by-construction streaming redaction (no cross-chunk leak), proven by tests.
- Zero behaviour change when the guard is disabled (`SOVEREIGN_GATEWAY_GUARD=0` ⇒ the exact legacy passthrough).
- Secure-by-default posture; operator can loosen (disable spine) or tighten (block injection, set a token).

## Non-goals

- **TLS termination.** The gateway holds provider keys and should terminate client TLS (F-2026-082 also names
  this), but a rustls layer is a larger, separable change; this SDD does auth + timeouts + back-pressure and
  leaves TLS as a tracked follow-up (a reverse proxy / systemd socket can terminate TLS in the interim).
- **Wiring `sovereign-serve`'s cache/complexity/budget filters** into the daemon (F-2026-089) — a separate arc.
- **Replacing the regex injection detector / auto-mode classifier** with something ML-grade (F-2026-092) — the
  spine treats screening as best-effort defense-in-depth, not the sole security boundary.

## Open questions

| Q | Question | Status |
|---|---|---|
| Q-206-001 | Should injection *blocking* ever default on for non-loopback binds (auto-strict when `--addr` is non-loopback)? | open — defaults fail-open for now |
| Q-206-002 | Should redaction findings also be recorded on the request `Ledger` (not just process-lifetime counters) for per-request audit? | open — counters + logs for now |
| Q-206-003 | TLS: in-process rustls vs delegate to systemd socket / reverse proxy? | open — deferred (non-goal) |

## Verification

- `cargo test -p sovereign-gatewayd` — lib 51 (incl. 11 new spine tests: cross-chunk secret redaction after a
  long-prefix release, split-secret, PII email, clean passthrough, injection block/fail-open, config defaults,
  metrics), main 4 (bearer auth accept/reject/malformed, constant-time-eq, timeout default), transports 14.
- `cargo clippy -p sovereign-gatewayd --all-targets -- -D warnings` — clean.
- `cargo fmt --all --check` — clean.

## Way forward

Arc 2 continues with TLS (Q-206-003) and the `serve`-vs-`gatewayd` filter-chain decision (F-2026-089). Arc 1
(`rope_theta` + sampling params, F-2026-080/086) remains the prerequisite for the model to generate coherently
in the first place — the spine guards whatever the model produces regardless.

## Cross-references

- `docs/review/phase-1/99-findings-ledger.md` — F-2026-081, F-2026-082 (source findings)
- `crates/sovereign-gatewayd/src/lib.rs` — `GuardConfig`, `StreamGuard`, `generate_chat`, `metrics_prometheus`
- `crates/sovereign-gatewayd/src/main.rs` — `auth_token`/`authorized`/`constant_time_eq`, `conn_timeout`, `serve`, reject fns
- `crates/sovereign-{injection-detect,secret-scan,pii-redact,toxicity}` — the wired-in libraries
- SDD-205 — the Anthropic Messages API surface the spine now also guards
- MS003 `unsigned-pending-MS003` — commit-authority signing remains the cross-cutting open work (F-2026-034)
