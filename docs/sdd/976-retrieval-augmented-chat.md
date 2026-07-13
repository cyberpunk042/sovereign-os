# SDD-976 — retrieval-augmented chat (wire the retrieval hub into `sovereign-chat`)

> Status: draft
> Owner: operator-directed 2026-07-13 ("what can we do now? crates integrations? from the bottom to avoid collision?"); agent-authored
> Advances: **F-2026-093** ("wire the island") — gives the retrieval cluster a real second consumer beyond the mega-demo.
> Mandate module: **E11.M976** (operator-mandate cross-link).
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

The operator asked to make progress through **crate integrations from the bottom** — real Rust wiring in the crate layer — specifically to sidestep the shared-doc-registry surface where two parallel sessions kept colliding. This is the first such integration: it lives entirely in `crates/sovereign-chat/`, touches no gatewayd/cockpit/registry file, and lights up a genuinely under-consumed island cluster.

## The gap (grounded in the island register)

`sovereign-retrieval` is a full RAG/retrieval hub — ~20 store types (BM25, hybrid, ANN, IVF-PQ, Matryoshka, VP-tree, …), a `RagResponder`, and reranker/dedup/injection-filter decorators, 63 tests — but it is consumed by **nothing except `sovereign-inference-demo`** (the 152-crate mega-demo) and `sovereign-retrieval-metrics`. The other demo binaries do plain generation: `sovereign-chat` and `sovereign-serve` never retrieve, despite a complete RAG stack sitting in the workspace. Per SDD-955's own analysis, the highest-leverage island move is *"a real consumer of `sovereign-llm`/`sovereign-retrieval`"* — the production wiring (into gatewayd) is the cross-session-contended part, so this takes the collision-safe half: a second **demo-binary** consumer.

## What this SDD builds

A `--rag` mode in `sovereign-chat`, mirroring the exact `Responder`→`RagResponder` composition the mega-demo already proves:

- **`knowledge_store()`** — a small built-in `Bm25Store` (5 short docs about the box: sovereignty / cost / privacy / rust / offline) so retrieval has real content to rank.
- **`run_rag(messages, sampler)`** — wraps the runtime as a `Responder` (`sovereign_agent_runtime::LlmResponder`), then `RagResponder::new(responder, store, top_k=2)`, and for each query prints whether retrieval **grounded** the prompt (`augment(q) != q`) plus the (untrained) reply.
- **`main()`** — a stripped `--rag` flag selects the path; documented in `--help`.

The dependency edges added (`sovereign-retrieval`, `sovereign-agent-runtime`, `sovereign-agent-loop`) pull the retrieval cluster into a second running binary — the crates now execute outside the mega-demo.

## Verification (real, observed)

- `cargo build -p sovereign-chat` compiles — pulls the retrieval cluster (bm25, ivf, hnsw, vptree, matryoshka, rerank, rank-fusion, …).
- `cargo test -p sovereign-chat` — **13 passed** (8 unit incl. `rag_grounds_a_known_query` + `knowledge_store_retrieves_a_corpus_match`; 5 binary-integration incl. `rag_mode_grounds_a_known_query` + `rag_mode_leaves_an_unmatched_query_ungrounded`).
- Live: `sovereign-chat --rag "how much does it cost"` → **grounded: true** (BM25 hit the cost doc); `"what about privacy"` → grounded: false (correct — the doc text says *private*, not *privacy*, and BM25 does not stem). The grounding signal reflects **genuine retrieval**, not a constant.
- `cargo fmt -p sovereign-chat --check` clean; `cargo clippy -p sovereign-chat --all-targets` clean (crate carries `[lints] workspace = true`, so `unsafe_code = forbid` holds).

## Non-goals

- **Wiring retrieval into the production daemon** (`gatewayd`/`cortex`) — the highest-leverage but cross-session-contended move (F-2026-083/088/089); deliberately not touched to stay collision-safe.
- **Retrieval-augmenting the multi-turn `ChatSession`** — this adds a distinct single-shot `--rag` path; folding RAG into the bounded-history loop is a follow-up.
- **Trained output** — weights are random (as with every demo binary); the point is that retrieval fires and grounds, not answer quality.

## Safety invariants

Crate-layer only: `crates/sovereign-chat/{Cargo.toml,src/main.rs,tests/run.rs}`. No gatewayd, no cockpit, no shared doc registry beyond this SDD's own rows. No `unsafe`. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `crates/sovereign-chat/src/main.rs` — the `--rag` path + `knowledge_store` + `run_rag`
- `crates/sovereign-retrieval/src/lib.rs` — `RagResponder` / `Bm25Store` / `Retriever` (the hub wired in)
- `crates/sovereign-agent-runtime/src/lib.rs` — `LlmResponder` (runtime → `Responder` adapter)
- `crates/sovereign-inference-demo/src/main.rs` (≈1180-1220) — the reference RAG composition this mirrors
- `docs/review/phase-1/island-register.md` — F-2026-093, the "wire the island" theme this advances
- SDD-955 — the island register + the "real consumer is the highest-leverage move" analysis
- SDD-100 — the per-session number-band convention
