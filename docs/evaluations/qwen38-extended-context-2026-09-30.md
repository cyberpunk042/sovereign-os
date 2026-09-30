# Qwen 3.8 extended context — 2026-09-30

Saved separate profile: `qwen38-dual-agent-long`, display name
Qwen 3.8 Dual Agent — 128K / 192K. Original `qwen38-dual-agent` is unchanged.
Logic uses Q4_K_M / 131072 context; Oracle Q8_0 / 196608. Same single slots,
Q8 KV cache, output reservations and 4090 embedding/reranking allocations.

Activation through the authorized profile CLI exited zero. Backends and OpenClaw
reported the new limits. Regression tests for control-rail resolution, rollback
preservation and unchanged other allocations: 2 passed.

Concurrent synthetic beginning-of-prompt code retrieval:

| Route | Actual prompt tokens | End-to-end seconds | Answer |
|---|---:|---:|---|
| Logic | 115030 | 75.45 | exact, passed |
| Oracle | 175035 | 135.42 | exact, passed |

These requests overlapped the initial OpenClaw tool probes, so timings can include
queueing. OpenClaw Logic completed in 78968 ms. OpenClaw Oracle timed out at its
90000 ms test deadline while the long request occupied the single backend slot.
This is a failed concurrent responsiveness check, not a reliability pass.
Oracle retry after the large request completed passed in 13439 ms with no fallback;
OpenClaw reported 196608 context. Both successful OpenClaw probes were verified
against transcript toolCall and toolResult events, one pair per session.
No model service restart was observed. Oracle reached an observed 85 C.
Observed VRAM: Logic 23223 MiB / 32607; Oracle 34348 MiB / 97887.

The large-input tests are synthetic, not near-full OpenClaw sessions or sustained
soak certification. Do not interpret model load success or ample VRAM as proving
interactive latency at the full window. Original profile remains the fallback.
