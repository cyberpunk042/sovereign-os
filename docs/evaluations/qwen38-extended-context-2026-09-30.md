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

## Oracle 256K extension

Saved and activated `qwen38-dual-agent-256k`, display name
**Qwen 3.8 Dual Agent — 128K / 256K**. Logic remains at 131072;
Oracle is 262144. Worker embedding/reranking allocations are unchanged.
The earlier profiles remain available for rollback. The authorized profile
switch exited zero; Oracle reported both n_ctx and n_ctx_train as 262144.

Direct Oracle test, with three distinct markers at the start, middle and end:

| Check | Actual prompt tokens | Seconds | Result |
|---|---:|---:|---|
| Retrieve all markers through structured record_codes call | 230337 | 193.77 | Exact arguments, passed |
| Consume tool result and return exact receipt | 230442 | 0.66 | VERIFIED-256K, passed |

The continuation reused 230404 cached tokens. Peak sampled Oracle VRAM was
36844 MiB, peak temperature 84 C (96 samples). This measures synthetic retrieval
and a tool round-trip, not broad reasoning accuracy at 230K.

OpenClaw session `context256-20260930-oracle` completed in 13092 ms:
status=ok, contextTokens=262144, fallbackUsed=false. Read-only SQLite transcript
inspection confirmed one session_status toolCall and one matching non-error
toolResult. This OpenClaw probe was short, not a full-window OpenClaw workload.

Verification outputs:

```text
pytest -q tests/lint/test_qwen_trial_profiles.py tests/test_openclaw_context_compat.py tests/test_openclaw_compaction_defaults.py
9 passed in 0.96s

systemctl show sovereign-logic-engine sovereign-oracle-core -p ActiveState -p NRestarts
ActiveState=active
NRestarts=0
ActiveState=active
NRestarts=0
```

The capacity and bounded tool checks passed, but this is not sustained stability
certification. A fresh 230K input took over three minutes; single-slot queueing
can still exceed client deadlines. Cached continuation speed does not guarantee
every subsequent request will retain its cache. No beyond-native-window scaling
was enabled, and no workstation restart was required.
