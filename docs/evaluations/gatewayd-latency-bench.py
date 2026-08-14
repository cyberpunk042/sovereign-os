"""Re-measure sovereign-gatewayd decode latency — CPU path and GPU tiers.

Reproduces the two measurements from
docs/evaluations/gatewayd-cpu-decode-latency-2026-07-31.md, which was marked
PARTLY INVALIDATED because every figure was taken while:

  - HfBpeTokenizer::encode split ChatML markers into ordinary BPE pieces, so
    each marker cost 7 tokens instead of 1 (fixed in ddc758e0), and
  - the KV cache carried over between requests (per-generation reset in
    f2fb8b4e), so prefill ran on a dirtier, longer context than it should have.

Both fixes are in. Run against a gateway with NO corpus: RAG grounding prepends
passages, which would inflate every prompt and make these numbers incomparable
to the 2026-07-31 run.

Usage: python3 gatewayd-latency-bench.py <port> [local-model-id] [gpu-model-id]
"""

import json
import sys
import time
import urllib.request

PORT = sys.argv[1] if len(sys.argv) > 1 else "8795"
LOCAL_ID = sys.argv[2] if len(sys.argv) > 2 else "local-oracle"
GPU_ID = sys.argv[3] if len(sys.argv) > 3 else None


def call(model, prompt, max_tokens):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/v1/chat/completions",
        data=body, headers={"content-type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as r:
        raw = r.read().decode("utf-8", "replace")
    elapsed = time.monotonic() - t0
    # The local path answers JSON; a proxied model streams SSE even when
    # stream:false is asked, so count content deltas instead.
    try:
        d = json.loads(raw)
        usage = d.get("usage") or {}
        return elapsed, usage.get("completion_tokens"), usage.get("prompt_tokens")
    except json.JSONDecodeError:
        # Count BOTH content and reasoning deltas. A reasoning model spends most
        # of a small budget on chain-of-thought and emits no content at all, so
        # counting only content reported "1 token" for a 16-token budget and made
        # the fitted throughput meaningless. Reasoning tokens are generated
        # tokens: they cost the same forward pass.
        n = 0
        for line in raw.splitlines():
            if not line.startswith("data: ") or "[DONE]" in line:
                continue
            try:
                delta = json.loads(line[6:])["choices"][0].get("delta", {})
            except Exception:
                continue
            if delta.get("content") or delta.get("reasoning"):
                n += 1
        return elapsed, n, None


def warmup(model):
    """One discarded call. The FIRST request pays costs no later one does —
    lazy init, page-cache misses, allocator warm-up. Measured here: 7.06s for a
    single token, against 1.85s for two on the very next call. Including it made
    the fitted slope NEGATIVE."""
    call(model, "Hi", 1)


def fit(pts):
    """Least squares over ALL points, not endpoints. An endpoint slope lets one
    outlier set the whole answer, which is exactly what the warm-up call did."""
    n = len(pts)
    sx = sum(x for x, _ in pts)
    sy = sum(y for _, y in pts)
    sxx = sum(x * x for x, _ in pts)
    sxy = sum(x * y for x, y in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0, sy / n
    slope = (n * sxy - sx * sy) / denom
    return slope, (sy - slope * sx) / n


def vary_output(model, label):
    warmup(model)
    print(f"\n## {label} — vary max_tokens, prompt held at \"Hi\"\n")
    print("| max_tokens | wall clock | completion tokens |")
    print("|---|---|---|")
    pts = []
    for n in (1, 2, 4, 8, 16):
        el, got, _ = call(model, "Hi", n)
        print(f"| {n} | {el:.2f}s | {got} |")
        if got:
            pts.append((got, el))
    if len(pts) >= 2:
        slope, intercept = fit(pts)
        print(f"\nMarginal cost per generated token: **{slope:.3f}s**"
              f"  ·  intercept **{intercept:.2f}s**")


def vary_prompt(model, label):
    warmup(model)
    print(f"\n## {label} — vary prompt length, output held at 1 token\n")
    prompts = [
        ("Hi", 1),
        ("Explain in one word what a filesystem does for an operating system.", 12),
        (" ".join(["filler word here"] * 12), 36),
    ]
    print("| prompt words | wall clock | prompt tokens |")
    print("|---|---|---|")
    pts = []
    for text, words in prompts:
        el, _, ptok = call(model, text, 1)
        print(f"| {words} | {el:.2f}s | {ptok if ptok is not None else '—'} |")
        pts.append((words, el))
    slope, intercept = fit(pts)
    print(f"\nSlope: **{slope:.3f}s per word**  ·  intercept **{intercept:.2f}s**")


if __name__ == "__main__":
    print(f"# gatewayd latency — port {PORT}")
    vary_output(LOCAL_ID, f"CPU local ({LOCAL_ID})")
    vary_prompt(LOCAL_ID, f"CPU local ({LOCAL_ID})")
    if GPU_ID:
        vary_output(GPU_ID, f"GPU proxy ({GPU_ID})")
