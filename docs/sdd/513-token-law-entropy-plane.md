# SDD-513 — The entropy token-law plane: a text→token safety projection (M00155 DEEPEN)

> Status: active · Mandate: **E11.M513** (control-bits band 500–599)
>
> Cross-link: the **first slice of the M00155 Deepen fork** (`backlog/milestones/M010-deterministic-data-plane.md`) over the M00117 engine. The twelfth SDD in the control-bits band, after the Expose arc (SDD-507/510/511) and the Connect fork (SDD-512).
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-23** — operator-directed (*"lets go"* → Fork 3 DEEPEN). Deepen names three pieces (route-plane-as-source, a text→token safety projection, SIMD); this ships the **most self-contained** of them, riding the already-proven `safe_token_ids` seam.

## Mission

The M00117 planes to date turn a *structural* text constraint into a per-token allow-list: grammar keeps a parse reachable, regex keeps a match live, the deny plane bans the token that *completes* a forbidden substring. Those are **exact per-step guarantees** because "the token that completes pattern P" is well-defined.

Secret leakage is **not** structural. A leaked API key or password is recognized by its *statistics* — a run of characters with high Shannon entropy — not a fixed substring. The deny plane's own scope note (`crates/sovereign-token-law-deny/src/lib.rs`) is honest that *"the token that completes a high-entropy secret is not well-defined"*, so entropy stayed a **post-hoc scanner** (`sovereign-secret-scan`, run on the finished output by the gateway's `StreamGuard`). This SDD projects that same detector to the token level as a new plane — closing a gap the codebase itself documented.

## The honesty framing (load-bearing)

This is an **explicitly heuristic** plane, NOT the exact per-step guarantee the substring planes give. The rule is **monotone and windowed**: score the trailing `window` characters of `generated + candidate_token` with the SAME `sovereign_secret_scan::shannon_entropy` definition and thresholds the post-hoc scanner uses, and **ban** any token that would leave that window at or above the entropy threshold (once the window is long enough to judge). It bans tokens that *extend or form* a secret-shaped run before it is emitted — a **preventive complement to, never a replacement for, the exact post-hoc scan**, which remains the backstop.

Because the threshold is a heuristic cutoff, the plane can (a) miss a low-entropy-but-sensitive value and (b) over-ban legitimate high-entropy text (a base64 blob the operator *wants*). So it is **opt-in per request**, tuned by `(threshold_bits, window, min_len)`, off by default, and it reuses the scanner's exact definition so the plane and the post-hoc scan can never disagree on what "high entropy" means. A checksum/Luhn-shaped PII projection (well-defined *completion*, unlike entropy) is the natural v2.

## Design

### 1. The plane — `sovereign-token-law-entropy`

A new crate mirroring `sovereign-token-law-deny` verbatim: `EntropyConstraint::safe_token_ids(&self, generated, vocab) -> Vec<usize>` returns the allow-list — all tokens minus the entropy-raising ones — the exact `Vec<usize>` shape `sovereign-token-law-mask`'s `TokenLawPlanes` composes. `forbid(unsafe_code)`; deps `sovereign-secret-scan` only (for the shared `shannon_entropy` — now `pub` — and the `ENTROPY_THRESHOLD_BITS` / `MIN_ENTROPY_TOKEN_LEN` defaults). A disabled constraint (`threshold ≤ 0` or `window = 0`) is an all-safe identity, so composition is a clean no-op.

### 2. The engine seam — a sixth plane

`sovereign-token-law-fuse` gains `FuseLayers.entropy: Option<EntropyConstraint>` (cleared by `select` when deselected), a `CompiledFuse` field, a `fused_mask` block (push `safe_token_ids` into the dynamics, `LayerCoverage { layer: "entropy" }`, stop-on-empty), and a `FuseRequest.entropy: Option<EntropyRequest>` wire field. `MaskLayerSet` gains a **sixth** bool + the `entropy` layer name — a **distinct** name, deliberately NOT folded into the `safety` alias (which stays exactly `denylist`+`regex_denylist`, so an existing `safety`-only selection is unchanged). `sovereign-llm`'s `TokenLawSpec` + `complete_with_token_law` and gatewayd's `ServingTokenLaw` + `/v1/messages` carry the field, so the plane is a first-class citizen everywhere the other five are — inspectable via the fuse route, drivable in generation, enforceable on live serving.

## What shipped

- **`sovereign-token-law-entropy`** (NEW crate) — `EntropyConstraint` (`safe_token_ids` / `is_high_entropy` / defaults tracking the scanner) + 6 unit tests.
- **`sovereign-secret-scan`** — `shannon_entropy` made `pub` (one honest definition shared with the post-hoc scanner).
- **`sovereign-token-law-fuse`** — the sixth plane wired through `FuseLayers` / `select` / `CompiledFuse` / `fused_mask` / `FuseRequest` / `MaskLayerSet` / `EntropyRequest`; +2 composition tests (the plane bans a secret-extender through the real `FuseRequest` path; the layer deselects cleanly).
- **`sovereign-llm`** — `TokenLawSpec.entropy` + `complete_with_token_law` passthrough.
- **`sovereign-gatewayd`** — `ServingTokenLaw.entropy` (the `/v1/messages` `token_law` object) + `layers_active` reporting.
- **Registration** — SDD-513 + INDEX row 513 + mandate E11.M513 + catalog regen + `context.md` sdd count 223→224 + workspace-crates 726→727 + crate-inventory + rustdoc-panel regen + `tests/lint/test_token_law_entropy_plane_contract.py`.

## Non-goals / roadmap

- **Checksum/Luhn PII projection** — a well-defined *completion* (unlike entropy), the natural v2 of this plane.
- **The other two Deepen pieces** remain: the **route plane as a real source** (blocked on a design question — the router outputs a *model choice*, not a vocab subset; there is no defined `SrpRole → allow-bitset` mapping yet) and **SIMD `fused_mask`** (the AND-kernel is scalar today, but the real serving hot path is the O(n²) whole-prefix re-decode flagged in SDD-512, so SIMD-of-the-AND optimizes the smaller loop — sequenced accordingly).

## References

- Milestone: `backlog/milestones/M010-deterministic-data-plane.md` (M00155 Deepen).
- The mirrored plane: `crates/sovereign-token-law-deny/src/lib.rs` (`safe_token_ids` + the entropy/checksum non-goal note this SDD addresses).
- The detector: `crates/sovereign-secret-scan/src/lib.rs` (`shannon_entropy`, `ENTROPY_THRESHOLD_BITS`, `MIN_ENTROPY_TOKEN_LEN`).
- Engine seam: `crates/sovereign-token-law-fuse/src/lib.rs` (`FuseLayers` / `CompiledFuse::fused_mask` / `FuseRequest` / `MaskLayerSet`).
- Arc: `docs/sdd/507-token-law-fusion-data-plane.md`, `docs/sdd/512-token-law-serving-boundary.md`.
