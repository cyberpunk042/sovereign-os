# SDD-978 — expose the retrieval hub's decorator surface as chat flags

> Status: draft
> Owner: operator-directed 2026-07-13 ("1 and 2 both, sequentially, lets do a big PR. take the time, do not minimize."); agent-authored
> Advances: **F-2026-093** ("wire the island") — runs the retrieval hub's full decorator + store surface in a real binary.
> Builds on: SDD-976 (`--rag`) + SDD-977 (`--rerank`). Part A of a two-part arc (Part B = SDD-979).
> Mandate module: **E11.M978**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

SDD-976/977 gave `sovereign-chat` a `--rag` path over a BM25 store, optionally reranked. This exposes the rest of the `sovereign-retrieval` hub's surface — the **hybrid store**, the **injection filter**, and the **keyphrase query distiller** — as composable flags, so any combination of the hub's real capabilities runs in a shipping binary. Crate-layer only; collision-safe.

## Enabling change (sovereign-retrieval, additive)

To compose an arbitrary subset of decorators — whose concrete type varies per combination — the retriever is held as a single `Box<dyn Retriever>`. Two additive, tested changes to the hub:

1. **`impl<R: Retriever + ?Sized> Retriever for Box<R>`** — a boxed retriever is a retriever, so a flag-assembled pipeline drops into `RagResponder` as one type.
2. **`pub fn augment_prompt(retriever, prompt, top_k) -> String`** — the context-augmentation logic, factored out of `RagResponder::augment` (which now calls it). Lets a caller ground a prompt *without* generation — the seam Part B (SDD-979) needs. `RagResponder::augment` behaviour is unchanged; all 63 retrieval tests pass.

## What this SDD builds (sovereign-chat)

- **`RagFlags`** (`--hybrid` / `--rerank` / `--injection-filter` / `--keyphrase`), each implying `--rag`, combinable.
- **`build_retriever(flags) -> (Box<dyn Retriever>, String)`** — assembles the pipeline in a fixed sensible order (base store → rerank/dedup/diversify → injection-filter → keyphrase distiller, outermost so the distilled query flows down) and returns a human label of the composed pipeline.
- **`hybrid_store()`** + a shared **`DOCS`** const so the BM25 and hybrid stores back the same corpus.
- `drive_rag` is now non-generic over `Box<dyn Retriever>`; `main()` strips all five flags; `--help` documents them.

## Verification (real, observed)

- `cargo test -p sovereign-retrieval` — **63 passed** (Box impl + augment_prompt refactor clean).
- `cargo test -p sovereign-chat` — **28 passed** (incl. `build_retriever_grounds_and_labels_across_flag_combos` + binary-integration `full_retrieval_pipeline_grounds_and_labels`, `hybrid_flag_implies_rag_and_grounds`).
- Live: `sovereign-chat --hybrid --rerank --injection-filter --keyphrase "what is sovereignty"` →
  `retrieval-augmented mode (top-2 keyphrase → hybrid(BM25+embed) → rerank → dedup → diversify → injection-filter)`, **grounded: true** — the whole decorator chain composes and grounds.
- `cargo fmt --all --check` (CI-exact, exit read directly) + `cargo clippy --all-targets` clean.

## Non-goals

- Exposing every store variant individually (ANN/IVF-PQ/Matryoshka/VP-tree/BinaryHamming/FuzzyTerm) — `--hybrid` covers the common dense+sparse case; the rest are a follow-up.
- Quality tuning (weights random); gatewayd/cortex wiring (F-2026-083/088/089).

## Safety invariants

Crate-layer only: additive `sovereign-retrieval` lib change (a `Box` impl + a free fn; no behaviour change to existing APIs) + `sovereign-chat`. No gatewayd, no cockpit, no `unsafe`. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `crates/sovereign-retrieval/src/lib.rs` — `Box` impl + `augment_prompt`
- `crates/sovereign-chat/src/main.rs` — `RagFlags` / `build_retriever` / the flags
- SDD-976 / SDD-977 — the `--rag` / `--rerank` foundations this extends
- SDD-979 — Part B (cached-RAG in serve), which consumes `augment_prompt`
- SDD-100 — the per-session number-band convention
