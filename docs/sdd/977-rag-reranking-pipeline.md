# SDD-977 — deepen chat RAG with the rerank → dedup → diversify pipeline

> Status: draft
> Owner: operator-directed 2026-07-13 ("Deepen chat RAG (reranking pipeline)"); agent-authored
> Advances: **F-2026-093** ("wire the island") — exercises the retrieval hub's decorator surface, not just its base store.
> Builds on: **SDD-976** (the `--rag` retrieval-augmented chat path).
> Mandate module: **E11.M977** (operator-mandate cross-link).
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

SDD-976 gave `sovereign-chat` a `--rag` mode grounding queries in a top-k BM25 store — a first real consumer of the `sovereign-retrieval` hub. That used only the hub's base store. This deepens it: a `--rerank` mode runs the hub's **decorator pipeline** — coverage-rerank → dedup → MMR-diversify — so the fuller retrieval surface (the wrappers, not just the index) executes in a real binary. Same collision-safe footprint: `crates/sovereign-chat/` only.

## What this SDD builds

- **`--rerank [QUERY…]`** in `sovereign-chat` (implies `--rag`): wraps `knowledge_store()` (the built-in `Bm25Store`) in the hub's decorator chain — `Reranked::with_defaults(...)` (lexical coverage rerank, falls back to the inner top-k if a semantic pool has no term overlap) → `Deduped::with_defaults(...)` (fingerprint near-dup drop) → `Diversified::new(..., lambda=0.7, pool_factor=4, min_pool=8)` (MMR relevance-vs-diversity) — each a `Retriever` over the previous, then handed to the same `RagResponder`.
- **`drive_rag<Ret: Retriever>(...)`** — the run loop is now generic over the retriever, so the plain (`Bm25Store`) and reranked (nested-decorator) pipelines — which are different concrete types — share one code path with **no boxing / no `dyn`**; the two arms monomorphize.
- **`main()`** strips `--rerank` alongside `--rag`; `--help` documents it.

## Verification (real, observed)

- `cargo build -p sovereign-chat` compiles.
- `cargo test -p sovereign-chat` — **25 passed** (10 bin-unit incl. `reranked_pipeline_still_grounds_a_known_query`; 9 lib; 6 binary-integration incl. `rerank_pipeline_grounds_a_known_query`).
- Live: `sovereign-chat --rerank "what is sovereignty" "how much does it cost"` prints `retrieval-augmented mode (top-2 BM25 → rerank → dedup → diversify)` and both queries report **grounded: true** — the decorator chain executes and still grounds.
- `cargo fmt --all --check` (CI-exact) clean; `cargo clippy -p sovereign-chat --all-targets` clean.

## Non-goals

- **Exposing every decorator individually** (hybrid/ANN/IVF-PQ/Matryoshka/VP-tree stores, injection-filter, keyphrase-query) — the chain here is the common relevance/quality trio; per-decorator flags are a follow-up if wanted.
- **Tuning the pipeline for answer quality** — weights are random (as every demo binary); the point is the fuller retrieval surface runs, not output quality.
- **gatewayd/cortex wiring** — still the cross-session-contended high-leverage move (F-2026-083/088/089), deliberately untouched.

## Safety invariants

Crate-layer only: `crates/sovereign-chat/{src/main.rs,tests/run.rs}` (no new deps — the decorators are already in the `sovereign-retrieval` edge added by SDD-976). No gatewayd, no cockpit, no `unsafe`. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `crates/sovereign-chat/src/main.rs` — `--rerank` path + `drive_rag` generic helper
- `crates/sovereign-retrieval/src/lib.rs` — `Reranked` / `Deduped` / `Diversified` (the decorators wired)
- SDD-976 — the `--rag` base path this deepens
- `docs/review/phase-1/island-register.md` — F-2026-093, the "wire the island" theme
- SDD-100 — the per-session number-band convention
