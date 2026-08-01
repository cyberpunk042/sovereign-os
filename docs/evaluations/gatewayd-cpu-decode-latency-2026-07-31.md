# Evaluation — where sovereign-gatewayd's CPU latency actually goes

> Measured on `ai-workstation` 2026-07-31 against the resident
> `/mnt/vault/models/smollm2-1.7b-instruct` (SmolLM2-1.7B-Instruct, bf16,
> 24 layers × 2048, vocab 49152), served by `sovereign-gatewayd` on
> `127.0.0.1:8787`. Every number is wall-clock over the real HTTP surface.
>
> Status: **MEASURED, and PARTLY INVALIDATED 2026-08-01 — do not cite the
> template figure.** Every number here was taken while `HfBpeTokenizer::encode`
> segmented added tokens into ordinary BPE pieces (fixed in ddc758e0): each
> ChatML marker cost **7 tokens instead of 1**. So the per-token costs below
> stand, but the prompt-length attribution does not — the template overhead was
> several times what a correct tokenizer produces, and the marker-cost sentence
> under "Conclusion" is wrong as written. The measurements also predate the
> per-generation KV reset (f2fb8b4e); they ran against a cache that carried over
> between requests, so prefill was operating on a dirtier and longer context than
> a correct run would. Re-measure before using any absolute figure here.
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
