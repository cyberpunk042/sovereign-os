# SDD-965 — ARCHITECTURE.md Stage-2 refresh + currency contract

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-053** (ARCHITECTURE.md scaffold-era stale).
> Mandate module: **E11.M965** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

`ARCHITECTURE.md` was frozen at the arc-opening (`Last updated: 2026-05-16`): it framed the profiles as future **"PR 5/6 stubs / reserved slots deferred per Q-012"** while all five now exist as full bodies, marked Infrastructure/Features as **"Stage 2+"** future, and had **no mention of the Stage-2 Rust intelligence layer** — the box's own local-AI backend (`gatewayd` daemon + the generation/reasoning stack). A reader got a foundation-scaffold picture of a box that has since grown its AI backend.

Scope discipline: `ARCHITECTURE.md` is a **reference document** that names the **info-hub-owned** architectural baseline (the SAIN-01 milestone + 11 epics). This refresh touches only the **sovereign-os-surface** sections; the info-hub-owned baseline (four-repo ecosystem, the 11 epics, cross-repo references) is left byte-unchanged.

## What this SDD builds

### 1. Refreshed sovereign-os-surface sections (additive)

- **Header**: `Last updated: 2026-07-13` with a Stage-2-refresh note (the original 2026-05-16 draft date preserved).
- **Profiles**: the five profiles are now described as realised, schema-conformant `profiles/*.yaml` bodies validated in CI — dropping the "reserved stub / PR 5/6 / Q-012 deferred" framing.
- **NEW "The intelligence layer (Stage-2)" section**: the `crates/` Rust workspace — `sovereign-gatewayd` (the one persistent daemon, Anthropic Messages API `/v1/messages` SDD-205 + the SDD-206 safety spine + durable memory), the in-daemon generation stack (`safetensors-loader → quant-model`, real RoPE/precision/sampler SDD-950/953) and the `sovereign-cortex` routing/reasoning brain — cross-linked to [`binaries.md`](../src/binaries.md) (the binary/daemon topology) and [`ai-backend.md`](../src/ai-backend.md).
- **SFIF mapping**: a **Current state (2026-07, post-Gate-5)** note supersedes the "Stage 2+" future-tense — foundation landed (5 profiles · whitelabel · observability/build/orchestration families · nspawn TDD tier), Gate 5 passed, Stage-2 (build scripts, operator control-plane + systemd fleet, intelligence layer) underway; QEMU/chroot tiers still scaffolds (F-2026-052).

### 2. `tests/lint/test_architecture_doc_current.py` — the currency contract

Fails CI if: any profile under `profiles/*.yaml` is not named in `ARCHITECTURE.md` (a realised profile can't read as a stub, a new profile can't be omitted); or `ARCHITECTURE.md` stops mentioning `gatewayd` / linking `binaries.md` (regression to a foundation-only view that omits the AI backend). It anchors on the two facts that made the doc stale — deliberately not on prose wording or a date (fragile). Same self-maintaining discipline as the context.md counts-contract (SDD-952) and binaries-doc completeness (SDD-962).

## Verification

- `python3 -m pytest tests/lint/test_architecture_doc_current.py` — 2 passed (all 5 profiles named; gatewayd + binaries.md referenced).
- All `profiles/*.yaml` basenames present in `ARCHITECTURE.md`; intelligence-layer section links resolve.
- `ruff` clean; full `tests/lint` + `tests/schema` green. `ARCHITECTURE.md` is root-level (not in the mdbook `docs/src/` tree) so no book impact.

## Non-goals

- **Rewriting the info-hub-owned baseline** — the four-repo ecosystem, 11 SAIN-01 epics, and cross-repo reference sections are authoritative elsewhere and left unchanged.
- **The charter "What this architecture does NOT decide" non-goals list** — those are charter-scoped Q-references; the Current-state note carries the reality without re-litigating the charter.
- **context.md refresh (F-2026-030)** — already closed by SDD-952; this SDD cross-links it rather than duplicating.
- **Building QEMU/chroot TDD tiers (F-2026-052)** — a sibling finding; named as still-scaffold, not built here.

## Safety invariants

Docs + read-only lint only — no crate code, no runtime behavior, no gateway touch. Every refreshed claim is grounded in the tree (5 `profiles/*.yaml`, the `gatewayd` daemon + `binaries.md` from SDD-962, the SDD-205/206 surfaces) — invents nothing; the info-hub-owned sections are untouched. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `ARCHITECTURE.md` — the refreshed reference document
- `tests/lint/test_architecture_doc_current.py` — the currency contract
- `docs/src/binaries.md` (SDD-962) — the binary/daemon topology the intelligence-layer section links
- `context.md` (SDD-952) — the current-arc detail + counts-contract sibling
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-053 (source); F-2026-030 (context.md, closed by SDD-952); F-2026-052 (QEMU/chroot tiers)
- SDD-952 / SDD-962 — the same self-maintaining-contract pattern
- SDD-100 — the per-session number-band convention (phase-1-audit 950–999 sub-band)
