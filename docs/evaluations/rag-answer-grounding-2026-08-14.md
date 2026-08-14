# RAG answer grounding — does retrieval reach the answer?

Companion to `rag-retrieval-dense-fusion-2026-08-14.md`, which measures whether
the right passage is RETRIEVED. This measures the other half: whether the
system's own knowledge reaches the reply.

The two are not the same question, and the gap between them is not theoretical.
For a full day retrieval was measured, improved and reported while the proxy
relay forwarded requests verbatim — so grounding reached nothing, and every
retrieval number was true and irrelevant. A retrieval score cannot detect that.
This can.

Reproduce: `python3 docs/evaluations/rag-answer-grounding-bench.py 8793 8794`

## Method

Two gateways differing in exactly one thing: whether a corpus is loaded. Same
binary, same backend model (`gpu-logic`, Nemotron-30B on the RTX 5090), same
routing, same prompt path. Verified before running — `rag_corpus_docs` 2828
against 0.

Each question names facts that appear only in this system's own documents. The
score is how many appear in the answer, averaged over 3 samples per cell.

## Result

| question | RAG on | RAG off |
|---|---|---|
| Which ZFS pool holds this system's datasets, name two | 0.7/1 | 0.0/1 |
| How is the RTX 4090 attached to SAIN-01? | 1.0/1 | 0.0/1 |
| Which CPU cores does the Pulse tier run on, which engine? | 1.0/2 | 0.0/2 |
| What recordsize is the models dataset tuned to? | 1.0/1 | 0.7/1 |
| Which GPU runs Logic, which runs Oracle? | 1.0/1 | 0.0/1 |
| Name the three tiers of the Genesis Trinity | 3.0/3 | 0.0/3 |
| **grounded facts recalled** | **7.7/9** | **0.7/9** |

Representative answers:

```
Q: What recordsize is the ZFS dataset holding models tuned to?
  RAG ON : 1M
  RAG OFF: The dataset is configured with a **128 K** recordsize.

Q: How is the RTX 4090 attached to SAIN-01?
  RAG ON : connected externally through an OcuLink eGPU interface
  RAG OFF: Could you clarify what SAIN-01 refers to ...
```

The RAG-off failure mode worth noting is the second kind, not the first: not "I
don't know" but a confident, plausible, wrong number. That is what an ungrounded
operator console does with a question about its own machine.

## Three flaws in the first version of this benchmark

Recorded because each one would have produced a better-looking and less true
number, and because the first version reported one of them.

1. **Single-sample scoring.** The model is non-deterministic; run to run the same
   question answers correctly, vaguely, or not at all. The first run reported
   9/12 vs 0/12 from one sample per cell. Now 3 samples, averaged.
2. **A guessable fact.** `tank` was a required fact — and it is the conventional
   ZFS pool name in every tutorial, which the RAG-off model produced unprompted.
   A fact a guess satisfies measures nothing about grounding. Removed.
3. **Presence is not correctness.** "Which GPU runs Logic, which runs Oracle" was
   two independent regexes, so an answer naming both cards while SWAPPING them
   scored full marks — and one sampled answer did exactly that ("Logic Engine →
   RTX 4090"). Now one ordered fact.

Empty answers were also being scored as ignorance when they were token
starvation: a reasoning model with `max_tokens: 700` spent the budget on
chain-of-thought and emitted no content. Raised to 2000, which moved one
question from 0/2 to 2/2 — a measurement artifact worth 2 points.

## Honest limits

- **6 questions.** Enough to establish that grounding works and that its absence
  is total; not enough to rank configurations against each other.
- **Grounding, not quality.** A well-grounded answer can still be badly written,
  incomplete, or wrong about something not measured. `Pulse tier` scores 1.0/2
  WITH RAG: it gets `CCD 0` and then says the engine is AVX-512 rather than
  bitnet.cpp — grounded on one fact, hallucinating the adjacent one.
- **Not a regression gate.** The absolute numbers move with the model, the
  corpus, and sampling. The comparison within a single run is the result.
