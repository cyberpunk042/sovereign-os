# Flash-Next dual-agent qualification — 2026-10-05

## Authorization and current status

Operator verbatim:

> okay lets add the profile and test it then

> Yes, continue automatically and roll back on failure

Profile added: `qwen38-flash-next-dual`, displayed as **Qwen Flash-Next + 27B —
Qualification**. It is a candidate, not a reliability certification.
Download started using the existing allowlisted `models download` service.
**Download complete; both SHA-256 checks passed. Profile active. Initial 64K
qualification passed: direct tool roundtrip, 10/10 OpenClaw read tasks, real
parent/child handoff, and 31.6K/58.2K retrieval. Not a long coding-task soak.**
Do not treat a present directory or a running download as readiness.

Rollback profile at start: `qwen38-dual-agent-256k`. Candidate activated at 18:17 EDT.
Do not replace a different profile if the operator changes it while downloading.

## Configuration

- Oracle / RTX PRO 6000: `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S`, 65536 context,
  8192 output, one slot, full GPU transformer layers, mmap + lazy embeddings,
  FP16 K/V cache for initial architecture qualification. No speculative decoding.
- Logic / RTX 5090: unchanged Qwen3.8-27B-Q4_K_M at 131072 context / 4096 output.
- RTX 4090 embedding/reranking allocations: exactly unchanged.
- OpenClaw sync recognizes the new profile and applies missing Qwen3.8 sampler
  defaults, bounded reasoning and parent handoff settings; preserves overrides.
- Existing `qwen38-dual-agent-256k` and other profiles are unchanged.

Source: [quantization repository](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF)
and [official Qwen model card](https://huggingface.co/Qwen/Qwen3.8-Flash-Next).
The official model is an experimental architecture. The catalog records license
`other` because the quant metadata lists Apache-2.0 while the base model lists
Qwen Community; this is not resolved by assuming the quant metadata overrides
the base license.

Pinned Hugging Face revision: `ed59f92082b1e93c0e96d60a8b11aab089b52f09`.
Download selections (no other quantizations or vision projector):

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf | 54817524224 | 4c1eb2ceb4915e1192f4f386021897bde56a97f40a0bb78bb86465e0f7d2aca3 |
| IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf | 28800138432 | 316b46f3a2dbd68c900f43136ab9449f9dcc3725dfd8c794847c204bc161e113 |

README is also selected; total download 83,617,678,349 bytes.
Job state: `/var/lib/sovereign-os/model-downloads/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S.json`.
Service: `sovereign-model-download-Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S.service`.
Downloader verifies both checksums before publishing `complete`.

## Verified before loading

### Live qualification, 18:17–18:19 EDT

Download state `complete`, 83,617,678,349 bytes, pinned revision matched; the
HTTP fallback finished and the worker verified both complete artifact hashes.
Both 8082/8083 slots were idle before activation. Supported profile switch
completed; OpenClaw metadata now advertises Flash-Next and 65536 context.
Oracle journal confirms the exact IQ3_S shard path, `model loaded`, one 65536
slot, and `/health` returned `{"status":"ok"}`. Cold load took ~65 seconds.
Idle allocated VRAM: Oracle 55028MiB, Logic 23201MiB, RTX4090 4921MiB.
Direct backend tool roundtrip passed in 4.37s: exact `lookup_code` arguments,
tool-result continuation and exact `CEDAR-974213` answer. Final decode 75.31t/s
on this short response; not a sustained throughput claim.
OpenClaw five-round-per-card qualification running with evidence under
`/tmp/sovereign-openclaw-qualification-mke4tmuy`.

Completed: **10/10 passed**, 30 successful reads, zero tool errors/unexpected
tools, no fallback, zero compactions. Oracle run durations 53.45, 12.37, 12.52,
30.86, 50.98s; Logic 18.27, 9.97, 9.73, 18.50, 18.24s. These are controlled
read-tool fixtures, not a general coding benchmark. Actual resident path from
`/props` independently confirmed Flash-Next IQ3_S on port 8083.
Parent/sub-agent test started with evidence
`/tmp/sovereign-subagent-qualification-7bah3ydm`, parent session
`subagent-qualification-2d30a107856fe1e2`.

Parent/sub-agent result: **passed in 81.01s**, one `sessions_spawn`, one
`sessions_yield`, one child `read`; exact code returned by child and parent,
zero errors and zero length stops. Child key
`agent:main:subagent:da4e82d8-4b34-4112-a00e-14783f59f8b1`.

`python3 scripts/inference/qualify-flash-context.py`: **2/2 passed** with uncached
prompts and exact random-code retrieval at beginning, middle and end:

| Actual prompt tokens | Total seconds | Prefill tok/s | Short-response decode tok/s | Peak Oracle MiB |
|---:|---:|---:|---:|---:|
| 31576 | 20.16 | 1629.49 | 79.39 | 55058 |
| 58174 | 38.84 | 1532.47 | 66.72 | 55058 |

Evidence: `/tmp/flash-next-context-9vqc2atv/results.json`. These synthetic
retrieval figures do not establish coding quality or throughput on arbitrary
inputs. 65536 remains the served Oracle limit; no 128K/256K Flash-Next claim.
Both model services reported `ActiveState=active`, `NRestarts=0` after testing.
Final targeted regression suite: **30 passed in 0.33s**. Profile remains active;
rollback was not needed. Completion heartbeat paused after successful initial
qualification. Retained candidate label distinguishes this from sustained soak
certification; the operator can re-activate it from the profile library.

- Vault had 1.3T available; sufficient space without deleting other models.
- Installed runtime `56381e4` advertises mmap/lazy-mode and contains
  `llama_model_qwen4exp` symbols. This is preliminary compatibility evidence,
  **not a successful model load**.
- Live `GET http://127.0.0.1:8100/api/lm-orchestration/profiles` includes the new
  profile and shows `ready:false`, `active:false` with its running download.
- Targeted suite, including isolated model/profile schema validation:
  `28 passed in 0.44s`.
- Broader suite: 128 passed, 3 failed. Existing HEAD reproduces catalog
  `autocomplete` enum / orchestration-as-runtime binding errors and the old
  `frontier-multifile-specialist` `kv-cache` role error. None belongs to the new
  model/profile. Those unrelated entries were not modified.

## Automatic continuation plan

### Download recovery, 2026-10-05 12:45 EDT

First attempt failed during download (`ConnectionError`) at 59,158,266,972 /
83,617,678,349 bytes. The download unit was inactive, vault still had 1.2T free,
and the Hugging Face repository API responded HTTP 200. Issued **one** resume
through the same allowlisted `models download` command; accepted. Existing
partial files retained; no duplicate worker and no profile switch.
If this resume also fails, investigate/report rather than retry indefinitely.

The resumed attempt also failed during download (`ConnectionError`), at
75,113,776,483 / 83,617,678,349 bytes. At inspection the worker was inactive,
the vault still had 1.2T available, and shard 2 existed at its expected
28,800,138,432-byte size. Shard 1 remains incomplete. Final SHA-256 verification
has not run, so neither the profile nor download is certified ready.
No profile switch occurred; `qwen38-dual-agent-256k` remains active. No files
were deleted. The exact transport failure beneath ConnectionError is not yet
established. Further retries should investigate download transport/resumption
rather than repeat the same large-file transfer indefinitely.

### Transport repair after operator continuation

Operator: “lets investigate and make sure it ifinish and load”. The currently
installed huggingface_hub 1.32.0 creates a unique temporary file and removes it
on failed transfers (`_download_to_tmp_and_move` source inspected). Repeated
snapshot retries are therefore not a reliable byte-resume strategy. This
explains a present resume limitation, not the exact cause of the earlier
ConnectionError; the old job logs do not expose that underlying exception.

Added `scripts/models/http-range-download.py`, selected for previously failed
ConnectionError jobs and subsequent HTTP-range resumes. It uses the pinned
repository revision, exact Content-Range validation, stable revision-keyed
partials, 64MiB requests, up to five consecutive transport retries with backoff,
and SHA-256 verification before promotion. The worker verifies all artifacts
again before publishing complete. No signed URLs or token values enter state;
HTTP status codes may be recorded for diagnosis.

Old 46,783,921,375-byte partial preserved separately: its completeness/layout
is not assumed safe for HTTP byte append. Completed shard 2 is reused. Progress
counts only the current HTTP partial and completed artifacts, not stale cache
bytes. Initial live observation: 335,544,320 new HTTP bytes downloaded, worker
status `downloading`, transport `http-range`.

`python3 -m pytest -q tests/test_http_range_download.py tests/test_model_download_job.py`:
**22 passed in 0.16s**, including resume offsets, wrong ranges, wrong checksums,
five-attempt retry bound, and no bearer token forwarded to another storage host.

The existing completion heartbeat is being resumed for download verification,
actual loading, OpenClaw qualification and rollback on failure. No profile
switch or inference qualification has yet occurred.

1. Wait for download state `complete`; inspect recorded sizes/checksums/revision.
   If failed/interrupted, report the problem; do not activate incomplete weights.
2. Re-read active profile and current GPU/service activity. If the operator has
   selected a different profile, stop for direction. Do not interrupt active
   user generations silently.
3. Activate using the established command:
   `sudo -n /usr/local/bin/sovereign-osctl trinity profile switch qwen38-flash-next-dual`.
   Inspect backend journals, `/health`, `/props`, real loaded model path and
   `nvidia-smi`; do not infer success from the profile marker or CLI exit alone.
4. Verify direct backend and gateway generation, JSON tool-call arguments and
   a tool-result continuation. Check bounded thinking produces visible answers.
5. Run `python3 scripts/inference/qualify-openclaw.py --rounds 5` (both cards),
   and `python3 scripts/inference/qualify-openclaw-subagent.py`. Require transcript
   evidence, expected model identities, no fallback, no unexpected tools/errors.
6. Test retrieval around 32K and near the 64K Oracle limit with output headroom;
   record actual token counts, prefill/decode latency and peak VRAM. Do not
   advertise 128K/256K for Flash-Next without separate measured tests.
7. On any load, context, tool or OpenClaw failure after the switch, restore
   `qwen38-dual-agent-256k` with the same supported switch command, then verify
   both original backends and OpenClaw catalog. Preserve logs and downloaded
   files. No workstation reboot, unrelated service changes or GPU remapping.
8. Record results here, notify the operator, and pause the completion heartbeat.
   Passing these bounded checks is not a long coding-task soak certification.
