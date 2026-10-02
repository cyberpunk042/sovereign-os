# Long-context tuning and request-boundary diagnostics

## Decision

Keep microbatch512 and profile qwen38-dual-agent-256k. The long-context comparison
does not demonstrate a consistent improvement from1024. No context sizes,
weights, GPU allocations or model service settings were changed.

## Long-context comparison

Reproducer: `python3 scripts/inference/bench-qwen-tuning.py --long-context`.
Artifacts: /tmp/sovereign-qwen-tuning-5e7kbb0s/results.json and server logs.
Isolated second Oracle resident, same262144 context/Q8 weights/Q8 KV, logical
batch2048, uncached prompts, greedy retrieval. Each exact answer passed.

| Microbatch | Prompt tokens | Seconds | Prefill tokens/sec |
|---|---:|---:|---:|
|512|127995|74.455|1728.25|
|512|229985|194.407|1192.81|
|1024|127996|75.534|1704.48|
|1024|229986|189.963|1221.00|

One sample per size/configuration; ordered rather than randomized. The approximately
2% advantage at230K and slight regression at128K do not support promotion.
This is bounded synthetic retrieval, not proof of full-context reasoning quality.

## Repeated OpenClaw tests

`python3 scripts/inference/qualify-openclaw.py --rounds 5` exited0.
Artifacts: /tmp/sovereign-openclaw-qualification-ffwloqr2/summary.json.
Five fresh-session tasks on each route, each requiring three real read-tool
calls, exact random codes and the correct sum. Transcript-verified:

- Logic:5/5 passed;9.57–18.43 seconds.
- Oracle:5/5 passed;15.27–25.34 seconds.
-30 successful file reads; no unexpected tools, tool errors, compactions or fallback.

The test runs one request per card concurrently. This is not a same-card
concurrency test or a sustained stability soak.

## Diagnostics enabled

Source: scripts/inference/openclaw-request-diagnostics.mjs.
Installer: scripts/inference/install-request-diagnostics.py.
Reader: scripts/inference/summarize-request-diagnostics.py.

Installed a narrow, version-checked wrapper on the managed OpenClaw extra-body
request path. Only sovereign gpu-logic/gpu-oracle requests are eligible.
It observes final-result promises without consuming or modifying stream events.
No prompt text, tool arguments/results, replies, headers or credentials are logged.
Fingerprints use a random process-local HMAC key, not plain content hashes;
comparisons cannot cross gateway restarts. Result records contain only timings,
numeric usage and an error flag. Null usage means unavailable, not zero.

The private0700 directory ~/.openclaw/diagnostics contains0600 requests.jsonl.
Rotation occurs after5MiB, retaining one previous file. The marker
request-hashes.enabled enables recording; no polling daemon or scheduled task
was created. Gateway-only restart loaded the diagnostic wrapper.

Disable without restarting:
`python3 scripts/inference/install-request-diagnostics.py --disable`

Installation is explicit; an OpenClaw package update can replace the patched
bundle. Reinstall with --dist after compatibility checking; the installer refuses
an unrecognized wrapper. No automatic upstream-update compatibility is claimed.

## Captured behavior and limits

During the five-session tests, tool and settings fingerprints remained unchanged.
Changed system-message fingerprints first diverged in chunk32 (1024-character
chunks of JSON-serialized content). Some reused23669/23693 tokens; later new
sessions replayed approximately24K tokens with cacheRead0.

These changes were BETWEEN fresh test sessions. They do not prove the cause of
the earlier same-session cache miss. The summary compares previous requests on
the same route, not necessarily the same conversation. Do not call every cold
request a bug or demote dynamic system instructions to user messages for speed.
The instrumentation now permits comparing the actual request boundary when a
same-session slowdown recurs.
