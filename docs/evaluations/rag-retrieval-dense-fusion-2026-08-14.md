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

## Honest limits

- **14 queries.** Small enough that the dense-first ordering is a provisional
  choice supported by a consistent direction (dense MRR > lexical MRR on every
  cut), not a tuned constant. It should be re-checked if the corpus changes.
- **4 of 6 paraphrase queries still miss at every stage** — including `dense`.
  Those are not fusion problems: the embedder does not surface the right passage
  at all. Chunk-level dilution (3500 passages from 297 files) and embedding
  quality are the next thing to look at, and neither is addressed here.
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
