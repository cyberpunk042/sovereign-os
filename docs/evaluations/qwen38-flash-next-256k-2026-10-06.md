# Flash-Next Oracle 256K qualification — 2026-10-06

Operator verbatim:

> can we not have more context room ? its not usable like this

Prepared separate `qwen38-flash-next-256k` profile. Only Oracle's served context
changes from 65536 to 262144. Logic remains 131072; RTX4090 and all model,
precision, output-limit, GPU and lazy-loading settings are unchanged. The
tested `qwen38-flash-next-dual` 64K profile remains the rollback target.

Preflight observed Oracle 55060/97887MiB VRAM. This suggests headroom, not proof
of a successful 256K allocation. OpenClaw has no global `contextTokens` override;
its managed model metadata must be synchronized with the real backend limit.

New profile control resolution and preservation tests: 6 passed in 0.18s.
`qualify-flash-context.py --extended` now supports bounded ~128K/~230K probes,
refusing a backend below 262144 and leaving at least 4096 tokens of headroom.

Operator explicitly authorized interruption: “you may interupt yes”. Applied
via the standard profile switch, which restarted the inference services and
OpenClaw gateway. Backend `/slots` confirms Oracle 262144 and Logic 131072;
both idle before probing. Oracle used 61462MiB after allocation (previously
55060MiB). OpenClaw sync reported `gpu-oracle.contextWindow: 65536 -> 262144`
and refreshed its materialized agent catalog.

Extended retrieval running: `/tmp/flash-next-context-e0pwuuc9`.
Restore `qwen38-flash-next-dual` if allocation or qualification fails.
Targeted regression suite: 11 passed in 0.24s.

First extended probe passed: **128033 actual prompt tokens**, all three exact
codes recovered, stop reason normal. Uncached wall time 100.72s, prefill
1282.02 tokens/s, short-response decode 49.24 tokens/s. Peak Oracle 61488MiB.
Second extended probe passed: **230024 actual prompt tokens**, all three exact
codes recovered, normal stop. Uncached wall time 222.25s, prefill 1044.71
tokens/s, short-response decode 37.24 tokens/s, peak Oracle 61488MiB.
Neither synthetic retrieval probe is a long coding-task soak or proof of
arbitrary reasoning quality at the full window. Initial ingestion latency is
material; larger context does not make cold histories instantaneous.

Post-expansion OpenClaw checks (two rounds per card): **4/4 passed**, 12
successful reads, zero unexpected tools/errors, no fallback or compactions.
Oracle 49.08s / 14.39s; Logic 18.23s / 18.20s. Evidence:
`/tmp/sovereign-openclaw-qualification-34we0q_f`.

Final state: `qwen38-flash-next-256k` remains active and selectable in the
profile library. Model services active, `NRestarts=0` after planned activation.
No rollback needed. Oracle backend and OpenClaw metadata both 262144; Logic
131072. Output caps remain Oracle 8192 / Logic 4096, so the whole context is
not available solely for user text. Instructions, tools and output share it.
Profile marked ready for this tested configuration, not a universal reliability
certification. Original 64K profile and RTX4090 allocations preserved.
