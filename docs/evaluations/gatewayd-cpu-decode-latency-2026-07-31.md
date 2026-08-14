# Evaluation — where sovereign-gatewayd's CPU latency actually goes

> Measured on `ai-workstation` 2026-07-31 against the resident
> `/mnt/vault/models/smollm2-1.7b-instruct` (SmolLM2-1.7B-Instruct, bf16,
> 24 layers × 2048, vocab 49152), served by `sovereign-gatewayd` on
> `127.0.0.1:8787`. Every number is wall-clock over the real HTTP surface.
>
> Status: **SUPERSEDED 2026-08-14 — the numbers below are a historical record
> of a broken tokenizer.** They were taken while `HfBpeTokenizer::encode`
> segmented added tokens into ordinary BPE pieces (fixed in ddc758e0), so each
> ChatML marker cost **7 tokens instead of 1**, and before the per-generation KV
> reset (f2fb8b4e), so prefill ran against a cache carried over between requests.
>
> Both fixes are in and the re-measurement is at the bottom of this file. The
> headline: the **18.2s intercept was almost entirely the broken tokenizer** and
> is now **0.61s**. Cite the re-measurement, not the tables above.
>
> The structural finding is unaffected and still holds: prefill runs the decode
> path one token at a time, so prompt tokens cost the same as generated ones.

## The question

After the end-of-turn fix (`9d579ef8`) cut a short answer from 60 tokens to 7,
wall clock fell 61.4s → 28.7s. But 7 tokens in 28.7s is not the ~1.3 tok/s the
60-token run implied, so something else dominated. Two candidate shapes: a fixed
per-request cost (model setup, safety spine, RAG augmentation), or prompt
processing scaling with input.

## Measurement 1 — vary output length, hold the prompt at "Hi"

| `max_tokens` | wall clock | tokens returned |
|---|---|---|
| 1 | 18.9s | 1 |
| 2 | 19.7s | 2 |
| 4 | 21.0s | 4 |
| 8 | 23.7s | 8 |
| 16 | 24.5s | 9 (stopped at eos) |

Marginal cost per generated token: **~0.7s**. Intercept: **~18.2s**.

An 18s floor on a two-word prompt looks like fixed overhead. It is not.

## Measurement 2 — vary prompt length, hold output at 1 token

| prompt | words | wall clock for 1 token |
|---|---|---|
| "Hi" | 1 | 19.6s |
| one sentence | 14 | 29.4s |
| repeated filler | 36 | 58.1s |

Slope: **~1.1s per word ≈ 0.85s per token**. That is the same order as the
decode cost above, not the ~10–100× cheaper prefill a batched implementation
would give.

## Conclusion

There is **no fixed overhead worth chasing**. Total latency is approximately

```
(prompt_tokens + generated_tokens) × ~0.75s
```

The apparent 18s "constant" in measurement 1 is the ChatML template rendered
before any user content, each token costing a full forward pass.

**Correction (2026-08-01).** This originally read "~20 tokens of `<|im_start|>` /
role / `<|im_end|>` markers", which understated it by about 7×. At the time
`encode` spelled every marker out as ordinary BPE pieces — `<|im_start|>` became
`<`,`|`,`im`,`_`,`start`,`|`,`>` — so a four-marker ChatML frame cost ~28 marker
tokens rather than 4, and that was the bulk of the "constant". ddc758e0 makes
markers atomic, which should cut most of this floor. The number above has NOT
been re-measured since; treat it as an upper bound from a broken tokenizer.

## Cause

`sovereign-quant-model::generate_masked_until_with`:

```rust
let mut logits = Vec::new();
for &t in prompt {
    logits = self.forward(t)?;      // one token at a time
}
```

Prefill runs the decode path per prompt token. Conventional serving processes
the whole prompt in one batched matmul, which is compute-bound and reaches far
higher throughput than token-at-a-time decode — decode is memory-bandwidth-bound
because each step re-reads the weights to produce a single token.

## What this implies

- **Conversation history is quadratic in practice.** Every turn re-prefills the
  whole transcript at full decode cost. A 500-token history costs ~6 minutes
  before the first new token.
- **The chat template is not free.** It is correct and necessary (without it the
  model never stops — see `9d579ef8`), but it adds ~15s to every request here.
- **Batched prefill is the single highest-leverage optimisation** available on
  the CPU path, and it is independent of M01283 (the Blackwell CUDA bridge). It
  would not speed decode at all, but on any realistic prompt prefill is the
  majority of the wall clock.
- The GPUs are idle throughout: an RTX PRO 6000 (96 GiB) and an RTX 5090
  (32 GiB) contribute nothing, because no crate in the tree links a GPU backend
  (`cudarc`/`candle`/`wgpu`/`vulkano` appear in no `Cargo.toml`;
  `sovereign-nvfp4-runtime`'s `blackwell-cuda` feature is an empty placeholder
  for M01283).

## Follow-up — head-skipping prefill, measured

`2b7ff23e` stopped computing the LM head for non-final prefill tokens (their
logits were discarded). Predicted ~5.9% from MAC counts: the head is
2048×49152 ≈ 101M against ~1611M for the 24 layers.

Same three prompts, one output token, before and after:

| prompt | before | after | change |
|---|---|---|---|
| "Hi" | 19.6s | 18.0s | −8.2% |
| 14 words | 29.4s | 27.0s | −8.2% |
| 36 words | 58.1s | 53.8s | −7.4% |

**~8%**, slightly above the MAC-count prediction — plausibly because the head is
~100M weights re-read per token, so it is more memory-bandwidth-bound than its
share of arithmetic suggests.

A caution about how this was nearly mis-reported. The first post-change run used
`"word " × N` prompts instead of the originals and showed −10%/−14%/−34%. That
was not a speedup; `"word " × 36` simply tokenises to fewer tokens than
`"Please answer concisely. " × 12`. Changing the workload and the code in the
same step produced a number 4× too good. The table above re-runs the exact
baseline prompts.

The conclusion is unchanged: ~8% is real and exact, and prefill remains one full
forward pass per prompt token. Batched prefill is still where the leverage is.

## Scoping batched prefill — what it would actually take

Recorded so the next person does not have to re-derive it.

The whole stack is vector-shaped from top to bottom:

```rust
DecoderStack::run(&mut self, hidden: &[f32]) -> Vec<f32>
MhaBlock::step(&mut self,    hidden: &[f32]) -> Vec<f32>
Ffn::forward(&self,          x: &[f32])      -> Vec<f32>
Linear::forward(&self,       x: &[f32])      -> Vec<f32>   // matvec, not matmul
```

Batching is therefore not a refactor of one function — it is a **second forward
path** alongside the existing one, through at least `sovereign-quant-model`,
`sovereign-safetensors-loader` (the stack), `sovereign-mha-block`,
`sovereign-attention`, `sovereign-ffn` and `sovereign-linear`.

The attention layer is the hard part and the risky one. Single-query attention
against a KV cache is a **different computation** from full-sequence
self-attention with causal masking — not the same code with an extra dimension.
Getting the mask subtly wrong produces output that looks plausible and is wrong,
which is the worst failure mode available.

**Expected payoff is real but bounded on CPU.** The dramatic prefill speedups
quoted for batching are largely a GPU phenomenon: batching raises arithmetic
intensity, which matters when you have thousands of idle FLOPs waiting on
memory. On CPU the gain comes from better cache reuse and SIMD utilisation —
plausibly 2–5× on prefill, so perhaps 2–3× on a whole request, not 10–100×.

Weighed against that: a multi-day change across six crates, touching the
correctness-critical attention path, on a daemon that currently works.

**Recommendation: do not start this as an incidental task.** Either commit to it
properly with its own test plan, or put the effort into M01283 (the Blackwell
CUDA bridge), where the same batching work buys an order of magnitude more and
the two idle GPUs in this chassis — an RTX PRO 6000 (96 GiB) and an RTX 5090
(32 GiB) — stop being decoration.

The cheap win in this area has already been taken: `2b7ff23e` skips the LM head
on non-final prefill tokens for a measured ~8%.

## Reproduce

```sh
for n in 1 2 4 8 16; do
  /usr/bin/time -f "%e s  max_tokens=$n" curl -s -o /dev/null \
    -X POST http://127.0.0.1:8787/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"local-oracle\",\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}],\"max_tokens\":$n}"
done
```

Vary the `content` string instead of `max_tokens` for measurement 2.


---

# Re-measurement — 2026-08-14

Same two measurements, same box, after `ddc758e0` (atomic ChatML markers) and
`f2fb8b4e` (per-generation KV reset). Run against a gateway with **no corpus**:
RAG grounding now prepends passages, which would inflate every prompt and make
these incomparable to the original.

Reproduce: `python3 docs/evaluations/gatewayd-latency-bench.py <port>`

## Measurement 1 — vary output length, prompt held at "Hi"

| `max_tokens` | wall clock | completion tokens |
|---|---|---|
| 1 | 1.23s | 1 |
| 2 | 1.85s | 2 |
| 4 | 3.08s | 4 |
| 8 | 5.57s | 8 |
| 16 | 6.20s | 9 (eos) |

Marginal cost per generated token **0.621s** · intercept **0.61s**.

## Measurement 2 — vary prompt length, output held at 1 token

| prompt words | wall clock |
|---|---|
| 1 | 1.24s |
| 12 | 11.71s |
| 36 | 25.75s |

Slope **0.682s per word**.

## What changed, and what did not

| | 2026-07-31 | 2026-08-14 |
|---|---|---|
| per generated token | ~0.7s | **0.621s** |
| intercept | **18.2s** | **0.61s** |
| per prompt word | ~1.1s | **0.682s** |

**The 18.2s "constant" was the broken tokenizer, as the 2026-08-01 correction
predicted.** A 30× collapse in the intercept, from a fix to token segmentation —
the ChatML frame was costing ~28 marker tokens where it should cost 4, and every
one of those was a full forward pass.

**The structural finding is unchanged and still the important one.** Prompt
words cost 0.682s and generated tokens cost 0.621s: the same order. Prefill runs
the decode path one token at a time, so a prompt token costs what a generated
token costs, where a batched implementation would make it 10–100× cheaper. Total
latency is still approximately `(prompt_tokens + generated_tokens) × ~0.65s`.

## The GPU tiers, for scale

Measured through the same harness on the same box:

| path | per token | throughput |
|---|---|---|
| CPU local (SmolLM2-1.7B, this gateway) | 0.621s | **1.6 tok/s** |
| GPU proxy (`gpu-logic`, Nemotron-30B NVFP4 on the RTX 5090) | 0.0057s | **177 tok/s** |
| the same tier queried DIRECTLY on :8082 | — | **~250 tok/s** |

That is the ~110× the Router/Logic tier work bought, and it is why "auto"
resolving to the CPU primary was a serious defect rather than a preference.

**The 177 vs 250 gap is NOT attributed.** The gateway figure counts SSE deltas;
the direct figure is vLLM's own `completion_tokens` against wall clock. The
difference is relay overhead, a counting difference between those two methods,
or both. Measuring that properly needs the relay to report usage, which it does
not — stated rather than guessed at.

## Two flaws in the re-measurement harness, fixed before these numbers

- **The first call is not like the others.** A cold request measured 7.06s for a
  single token against 1.85s for two on the very next call — lazy init, page
  cache, allocator. Including it made the fitted slope NEGATIVE. There is now a
  discarded warm-up call.
- **Endpoint slopes let one outlier decide the answer**, which is precisely how
  that warm-up call produced −0.108s per token. Now least squares over all
  points.
- Counting only `content` deltas reported "1 token" for a 16-token GPU budget,
  because a reasoning model spends a small budget entirely on chain-of-thought.
  Reasoning tokens are generated tokens — same forward pass — and are now
  counted.
