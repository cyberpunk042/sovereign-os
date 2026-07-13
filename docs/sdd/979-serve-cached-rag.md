# SDD-979 — cached-RAG in sovereign-serve (retrieval × the cost-aware cache)

> Status: draft
> Owner: operator-directed 2026-07-13 ("1 and 2 both, sequentially, lets do a big PR. take the time, do not minimize."); agent-authored
> Advances: **F-2026-093** ("wire the island") — a third real consumer of the retrieval hub, combining it with a *different* cluster.
> Builds on: SDD-978 (the `augment_prompt` seam). Part B of a two-part arc (Part A = SDD-978).
> Mandate module: **E11.M979**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

`sovereign-serve` is the $0-aware serving assembly — cache → complexity → budget → generate → account — but it served plain prompts with no retrieval. This wires the `sovereign-retrieval` hub into it so serving is **retrieval-augmented and cached at once**: ground each query, then serve the grounded prompt through the cost-aware cache. Because augmentation is deterministic (same query → same retrieved docs → same grounded prompt), a **repeated grounded query is a genuine $0 cache hit** — the model never runs. It combines two previously-disjoint clusters (retrieval + the completion cache) into one capability, entirely in the crate layer.

## What this SDD builds (sovereign-serve)

- **`--rag [PROMPT…]`**: builds a BM25 `rag_knowledge_store()`, then for each query calls `sovereign_retrieval::augment_prompt(&retriever, query, top_k)` (the seam SDD-978 factored out) to get the grounded prompt, and serves it through the existing `Server` (cache + budget + the real `generate` closure — so `--rag` composes with the egress/decode flags unchanged). Each grounded prompt is served twice so the demo shows the repeat as a `$0` exact hit; per-query grounding is reported.
- Adds the `sovereign-retrieval` dependency edge to serve; `--help` documents the flag.

**Why the cache hits:** the cache keys on the request text. `augment_prompt` is a pure function of `(corpus, query, top_k)`, so the grounded prompt is stable across calls — the second serve of the same query is byte-identical and resolves as an exact `$0` hit. Retrieval cost is paid once; the cache absorbs the repeat.

## Verification (real, observed)

- `cargo test -p sovereign-serve` — **18 passed** (incl. binary-integration `rag_grounds_the_prompt_and_a_repeat_is_free`).
- Live: `sovereign-serve --rag "what is sovereignty" "how much does it cost"` →
  `grounded=true` for both; first serve of each `hit=miss` (tokens charged, model runs); **second serve `hit=exact in=0 out=0`** (the $0 cache hit); summary `4 request(s), 2 cache hit(s) ($0) [2 exact, 0 semantic]`, hit-rate 0.50. The served prompt carries the `Context:` block, confirming real augmentation.
- `cargo fmt --all --check` (CI-exact) + `cargo clippy -p sovereign-serve --all-targets` clean; `cargo metadata --locked` in sync (`Cargo.lock` committed).

## Non-goals

- **Semantic-cache RAG** — a paraphrased query grounds to a *different* prompt, so it misses the exact cache; `--rag --semantic` composes but the semantic tier keys on the grounded text, not the raw query. Making paraphrase-grounding cache-friendly is a follow-up.
- **The decorator pipeline** (rerank/hybrid/…) in serve — serve uses the base BM25 store; the full pipeline lives in chat (SDD-978). Sharing one retriever builder across both binaries is a possible future consolidation.
- gatewayd/cortex wiring (F-2026-083/088/089); trained output (weights random).

## Safety invariants

Crate-layer only: `crates/sovereign-serve/{Cargo.toml,src/main.rs,tests/run.rs}` + the `augment_prompt` seam from SDD-978. No gatewayd, no cockpit, no `unsafe`. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `crates/sovereign-serve/src/main.rs` — the `--rag` cached-serving path
- `crates/sovereign-retrieval/src/lib.rs` — `augment_prompt` (the grounding seam)
- `crates/sovereign-serve/src/lib.rs` — `Server` (the cache/budget/meter it grounds into)
- SDD-978 — Part A (the decorator flags + the `augment_prompt` seam)
- SDD-955 — the island register; the "real consumer" this adds
- SDD-100 — the per-session number-band convention
