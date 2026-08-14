# RAG retrieval — dense fusion on SAIN-01, 2026-08-14

Measured on the live box against the real corpus (`docs/src` + `docs/sdd`,
297 files, 3500 passages) with `POST /v1/corpus/search`, which runs the same
path that grounds a prompt.

Reproduce: `python3 docs/evaluations/rag-retrieval-bench.py 8787`

## Result

| stage | literal hit@5 / MRR | paraphrase hit@5 / MRR | overall hit@5 / MRR |
|---|---|---|---|
| `hybrid` (BM25 + char-n-gram) | 6/8 · 0.688 | **0/6 · 0.000** | 6/14 · 0.393 |
| `dense` (bge-m3, no rerank) | 6/8 · 0.750 | 2/6 · 0.222 | 8/14 · 0.524 |
| `fused` (shipped) | **7/8 · 0.812** | 2/6 · 0.200 | **9/14 · 0.550** |

The headline is the `hybrid` paraphrase row: **zero for six**. BM25 and
char-n-grams match characters, so a question asked in different words than the
document that answers it finds nothing. That is what the Router tier was
provisioned to fix.

## What the stage breakdown was for

Fusing the dense ranking in produced **no change at all** on the first attempt —
identical hit@5 and MRR. The `stage` parameter exists because that number could
not say whether the embeddings were bad, the fusion was wrong, or a later stage
was discarding what the dense pass found. It answered immediately:

```
query: which filesystem holds the operating system datasets
  hybrid  MISS
  dense   rank 1      <- the embedder found it perfectly
  fused   MISS        <- and the pipeline threw it away
```

`sovereign_rerank::rerank` scores by term coverage and drops any passage sharing
zero query terms — the definition of a paraphrase. Running it last discarded
exactly what the dense pass exists to find.

The second finding came the same way. With the fix in place but interleaving
**lexical-first**, `dense` alone (MRR 0.524) still beat `fused` (0.464): dense
only reached output slots 2 and 4, and one target sat at dense rank 3. Starting
the interleave with the dense side — measured, not assumed — put `fused` above
both components, which is what a fusion should do.

## Follow-up: the remaining misses were not what I said they were

The first version of this document listed the four remaining paraphrase misses
as "chunk-level dilution and embedding quality". Both wrong. The documents that
answer those queries **were** retrieved by the dense pass — at ranks 12, 39, 9
and 11 — and pushed under the top-5 cutoff by the table of contents.
`sdd__INDEX` appeared in the dense top-5 of all four.

An index is topically adjacent to everything and substantively answers nothing,
which is exactly the shape that wins a semantic ranking and loses a question.
It was also 19% of the corpus by bytes: `sdd__INDEX.md` plus
`src__sdd-catalog.md` came to 497 KB of dense tables naming every SDD.

Removing them (scripts/iac module 88) lifted both component rankings — the
fused number did not move, being already at what 14 queries can resolve:

| stage | before | after |
|---|---|---|
| `hybrid` | 6/14 · 0.393 | **7/14 · 0.443** |
| `dense` | 8/14 · 0.524 | **9/14 · 0.538** |
| `fused` | 9/14 · 0.550 | 9/14 · 0.550 |

## Follow-up: the grounding top-k default was the worst setting

`DEFAULT_RAG_TOP_K` was 3, chosen before this box had ever run RAG:

```text
top-k    overall hit@k
  3        8/14        <- the previous default
  5        9/14
  8        9/14
 10       10/14
```

Now 5 — the knee, taking the whole 3→5 gain where 5→8 buys nothing. Not 10
despite the extra hit: this measures RETRIEVAL, and more context also means more
irrelevant context. Taking the measured knee rather than the measured maximum is
the conservative read of a number that does not cover the risk.

## Honest limits

- **14 queries.** Small enough that the dense-first ordering is a provisional
  choice supported by a consistent direction (dense MRR > lexical MRR on every
  cut), not a tuned constant. It should be re-checked if the corpus changes.
- **The fused number has not moved since the dense-first fix**, through two
  changes that both improved its inputs. 14 queries is not enough resolution to
  tune fusion on, and further ratio tuning would be fitting the benchmark rather
  than the corpus. Expanding the query set is the prerequisite for any more
  fusion work.
- **`dense` alone now beats `fused` on paraphrase** (3/6 · 0.256 vs 2/6 · 0.200)
  while losing on literal. Interleaving halves each side's effective depth, so a
  dense hit at rank 4-5 cannot reach a top-5 output. Known, not yet addressed.
- **The first version of this benchmark had wrong ground truth.** It labelled one
  document per query from its filename, so "how are language models split across
  the graphics cards" counted `sdd__993-sain-gpu-topology` and
  `sdd__111-d21-d22-full-layout` as failures — documents that genuinely answer
  it. Labels here were checked against document content, and a query may have
  several correct answers.

## Not measured

Answer quality. This measures whether the right passages are *retrieved*, which
is necessary and not sufficient — grounding the model in the right document does
not prove the generated answer improved. That needs a separate evaluation.
