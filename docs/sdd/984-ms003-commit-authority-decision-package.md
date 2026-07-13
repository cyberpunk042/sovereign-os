# SDD-984 — MS003 commit-authority / signed-mutation gating: decision-package (F-2026-034)

> Status: draft — **DECISION-PACKAGE (awaiting operator decision; do not implement until the core decision below is made)**
> Owner: operator-directed 2026-07-13 ("yes lets go, lets do it" — scope the CRIT cross-cutting blocker); agent-authored.
> Addresses: **F-2026-034** (CRIT) — the acknowledged cross-cutting hole; every SDD-142..204 ships `unsigned-pending-MS003`.
> Mandate module: **E11.M984**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Why this is a decision-package, not an implementation

The audit's biggest still-open finding is a **policy gap, not a coding task**.
Research (this session, read-only across `_action_exec.py`, `control-systems.yaml`,
the decision-writers, `M065`, SDD-015/048, the selfdef mirror) surfaced one
headline fact that reframes everything:

> **MS003 is a *selfdef*-owned milestone. sovereign-os has no local MS003 spec —
> only a *consumer contract*.** There is no `MS003` file in `backlog/milestones/`
> (it holds `M002`–`M086`); every reference is "cross-ref **selfdef** MS003".

So "close F-2026-034" cannot mean "implement signing" until the operator decides
**what signing means for sovereign-os's own locally-executed mutations** — a
question the doctrine (R10212) leaves genuinely open. This package lays out the
facts, the options, a recommendation, and the questions only you (+ selfdef
coordination) can answer.

## Current state (what exists today — verified)

| Layer | Reality | Evidence |
|---|---|---|
| The marker | `signature: "unsigned-pending-MS003"` — a literal placeholder constant written into every mutation/decision record | `scripts/intelligence/memory-store.py:61`, `memory-decide.py:74`, `scripts/inference/adapter-decide.py:69`, `scripts/lifecycle/*-decide.py` |
| The gate (real) | **presence-gate + confirm + sudo + audit** — privileged controls require the operator key to be *present* (material never read) + explicit `confirm=true`; executed via `sudo -n`; audited OCSF-5001 into the M049 span store | `scripts/operator/_action_exec.py:93-105,278-291,199-235` |
| The boundary | **R10212** — the web never arbitrarily mutates. **R10274** — the sanctioned "signed-mutation-proxy" write path (currently realized as presence-gate, not real signature). Selfdef-owned controls (`selfdef`, `perimeter`) are **never executed locally** → `409 boundary`, proxied to selfdef | `_action_exec.py:53,259-270`; `docs/handoff/007-*.md:18-22` |
| Real crypto on the host | **only SecureBoot image signing** (`sbsign` of kernel/EFI with the operator MOK/PK) — a *different domain* (boot images, not mutation records). **No ed25519/HMAC/minisign signing of mutations exists anywhere** (0 signing deps across `crates/*/Cargo.toml`) | `docs/sdd/015-secure-boot-posture.md:41-51`; `scripts/build/08-image-sign.sh` |
| Doctrine | Signing is **selfdef's responsibility** — the authoritative audit chain + MS003 verify-only signatures live on the IPS; sovereign-os mirror APIs return **405 on every mutation** | `scripts/operator/audit-mirror-api.py:5-11`; `adapter-decide.py:25,194` "Never builds signing crypto" |

**Plain-language summary:** today a privileged mutation is *honestly unsigned* —
it is gated (key present + you confirm), executed, and fully audited, but the
`signature` field is a placeholder. Nothing forges a signature; nothing verifies
one.

## The mutation surfaces to sweep (re-baselined — the finding's counts are stale)

| Surface | Count | Notes |
|---|---|---|
| **osctl mutating verbs** via the control registry (`config/control-systems.yaml`) | **36 controls; 28 privileged; 2 selfdef-owned** → **~34 sovereign-os-owned local mutations** | handoff 007 assumed "9 controls" — the registry has since grown to 36. **Any sweep must re-baseline.** |
| **Decision-writer scripts** stamping the placeholder | **6** | `intelligence/memory-store.py`, `intelligence/memory-decide.py`, `inference/adapter-decide.py`, `inference/adapter-gate.py`, `lifecycle/approval-decide.py`, `lifecycle/session-decide.py` |
| **Operator APIs** | **54 files, architecturally read-only** (mutation → 405); the one write path is `control-exec-api.py` → `_action_exec.py` | so the sweep is the write daemon + the 6 decision-writers, not 54 APIs |
| **selfdefctl parity verbs** (`scripts/mirror/selfdef-cli-mirror.py`) | 140+ subcommands; the `requires_signature==true` subset (effect ∈ execute/commit/persist/destructive/prepare) | **proxy-only** on the sovereign-os side (R10212) — these stay signed-proxy, not local |
| **Stage-gate sign-off** (`M065` F05492–F05496) | operator-key fingerprint, hardware-token derivation, delegation tokens ≤24h — all "cross-ref selfdef MS003" | the gate-authorization surface that also needs the signature |

## The core decision (operator)

For **sovereign-os-owned, locally-executed** mutations (the ~34 controls +
the 6 decision-writers), what does "signed" mean? Three coherent options:

### Option A — pure consumer (selfdef mints every signature)
Every local mutation round-trips to selfdef to obtain an MS003 signature before
(or when) it commits. Purest R10212 doctrine.
- **+** No crypto in sovereign-os; one chain-of-trust; matches "selfdef signs".
- **−** Couples every local mutation to **selfdef availability** — conflicts with
  MS043 offline-survivability (the box "boots degraded but functional without
  selfdef"). A signing round-trip on the hot path is latency + a hard dependency.

### Option B — local signing with the operator identity (selfdef verifies) — *recommended*
sovereign-os mints a real signature over each local mutation record using an
**operator signing key** (reuse the MOK/PK identity the presence-gate already
keys off, or a dedicated `~/.sovereign-os/operator.key`), with **ed25519/minisign**.
Selfdef (and `sovereign-zfs-commit-gate`, which already models a `signature`
envelope field) **verifies**. Selfdef-owned controls stay proxy (unchanged).
- **+** Real signatures now; **no selfdef-uptime coupling** (offline-survivable);
  reuses an identity already present; respects R10212 (selfdef-owned still proxied).
  Verification remains selfdef's job (consumer produces, producer verifies).
- **−** sovereign-os gains a (small, additive) signing primitive — a new
  dependency + key-management surface; needs a documented key-provisioning flow.

### Option C — formalize "honestly unsigned" (presence-gate + audit only)
Accept that local mutations are presence-gated + audited but never cryptographically
signed; rename the marker from "pending" to a permanent "presence-gated" status
and close the finding as *won't-sign-locally*.
- **+** Zero new crypto; matches today's reality; cheapest.
- **−** Leaves the CRIT finding permanently open in spirit; no tamper-evidence on
  the mutation record itself (only the audit chain, which selfdef owns).

**Recommendation: Option B**, scoped so selfdef-owned surfaces stay pure proxy
(A) and only sovereign-os-owned local mutations gain a local operator signature —
because it delivers real commit-authority **without** breaking offline-survivability
(MS043), and it slots into the `signature` field + `sovereign-zfs-commit-gate`
envelope that already exist. It does, however, depend on the selfdef MS003 spec
for the signature *format* so selfdef can verify — hence the cross-repo step below.

## Open questions (must resolve before implementation)

1. **Which option (A / B / C)** for locally-executed sovereign-os-owned mutations?
2. **Signing identity**: reuse the SecureBoot operator MOK/PK identity (already
   the presence-gate signal) or a dedicated `~/.sovereign-os/operator.key`?
3. **Signature format / algorithm**: must match what selfdef MS003 verifies
   (ed25519? minisign? — the selfdef signing-audit already speaks *minisign*).
   **This requires the selfdef MS003 spec, which is not in this repo.**
4. **Finding mislabel**: F-2026-034 cites "SDD-055 / MS003", but SDD-055 is
   `lm-orchestration-wiring` (unrelated). The real anchors are **SDD-015**
   (MS003 / MOK signing) + **SDD-048** (approval-authority consumer decision).
   Confirm so the sweep references the right SDDs. *(Corrected in the ledger.)*
5. **Registry re-baseline**: the sweep covers **34** owned controls (not 9);
   confirm the control set + the 6 decision-writers as the full surface.
6. **`sovereign-zfs-commit-gate`**: is its `signature` envelope field the intended
   verification point for commit-authority, or incidental?

## Cross-repo dependency (the blocking step)

MS003's authoritative spec lives in **`cyberpunk042/selfdef`**, not here. Before
any sweep, the selfdef MS003 signature format + verification contract must be
pinned. **Recommended first action: a coordination message** (this is exactly
what the SDD-981 board is for) to the operator + the selfdef/core-runtime lane,
requesting the MS003 spec, then a paired selfdef decision. This package is the
sovereign-os *consumer* half; it cannot close without the selfdef half.

## Non-goals (of this package)

- Implementing any signing (blocked on the core decision + the selfdef spec).
- Touching the mutation surfaces (`_action_exec.py`, `control-systems.yaml`, the
  decision-writers) — read-only research only; collision-safe.
- Closing F-2026-034 — it stays **open**; this package *scopes* it and unblocks
  the decision. It closes when the operator picks an option, the selfdef spec is
  pinned, and the sweep ships.

## Safety invariants

Docs only (this SDD + registries + the F-2026-034 ledger back-annotation). No
gatewayd/cockpit/`unsafe`/crate edits; every cited surface was read, never
written. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003` (fittingly).

## Cross-references

- `docs/review/phase-1/99-findings-ledger.md` — F-2026-034 (this package addresses it)
- `docs/sdd/015-secure-boot-posture.md` — MS003 / MOK signing anchor · `docs/sdd/048-approval-authority.md` — the consumer decision (presence-gate, "no MS003 signing")
- `scripts/operator/_action_exec.py` — the R10274 execution primitive (presence-gate + confirm + sudo + audit)
- `config/control-systems.yaml` — the 36-control registry (the local mutation surface)
- `backlog/milestones/M065-*.md` — stage-gate sign-off (F05492–F05496, cross-ref selfdef MS003)
- `scripts/mirror/selfdef-cli-mirror.py` + `scripts/interop/mcp-aggregate.py` — the selfdefctl parity ladder (proxy-only)
- `crates/sovereign-zfs-commit-gate/src/lib.rs` — the `signature` commit-envelope (candidate verification point)
- `docs/sdd/957-*` — precedent (serve-vs-gatewayd decision-package)
