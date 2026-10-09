# Native dual-image runtime qualification — 2026-10-09

Operator backend: stable-diffusion.cpp, revision
`7867f6da4af741d4d9d5fbd6c7f1197dfb8c6e39`.

CUDA build: isolated 13.3 compiler/runtime headers, SM120a; existing LLM
environment untouched. CLI and headless server build successfully.

## Artifact compatibility

- Qwen Image 2.1 UC BF16 GGUF, original BF16 encoder and model-specific VAE:
  direct native startup succeeds on the RTX 5090. Declared parameter allocation:
  14,215 MiB GPU and 15,536 MiB CPU. Not a measured generation peak.
- FLUX.2-dev original downloaded Diffusers transformer layout is not directly
  understood by the native loader (initially misdetected as FLUX.1). Repacked
  locally with `convert-flux2-native.py`; all 331 source tensors pass bit-exact
  round-trip validation against the forward Diffusers converter. No dtype
  change. Source files are untouched.
- FLUX text encoder requires removing `language_model.` from the language
  tensor names. `convert-flux2-encoder.py` retains 363 language tensors unchanged;
  vision-tower tensors are not needed for text-to-image conditioning.
- After both conversions, native FLUX.2 startup succeeds on the PRO 6000.
  Declared parameter allocation: 61,625 MiB GPU and 43,682 MiB CPU. Not a
  measured generation peak.

Converted local artifacts are under `.runtime/image-artifacts/`; their combined
size is approximately 111.6 GB. They are derived artifacts, not new downloads.

## Remaining qualification

Live profile activation, image generation, repeat activation, restoration and
boot persistence must be verified before promoting this candidate as ready.
Startup success is not generation quality or reliability certification.

## 5090-only qualification run (operator scope: RTX 5090 only, oracle retained)

Operator directive 2026-10-09 13:29: test the 5090 side only; the Oracle must
stay resident because the OpenClaw assistant runs on it. Executed as a
manual transaction instead of the profile switch, because
`trinity profile switch qwen-image-flux-dual` stops both chat residents.

Procedure (evidence: `/tmp/image-qual-5090.log`, copied to the operator
workspace): `sudo -n sovereign-osctl inference stop logic` freed the 5090
(23,190 MiB llama.cpp resident); `sd-server` started directly with the
activation rail's exact arguments on `--listen-port 8188`;
`qualify-image-dual.py --model qwen` runs; `inference start logic` restored
the 5090 chat resident on exit trap.

Measured results:

- 512px 2-step smoke: passed in 13.5 s (first request includes weight load).
- 1024px 28-step run 1: 30.5 s. Run 2 (repeat): 29.1 s. Byte-identical PNGs
  (seed 42 determinism; both 1,229,002 bytes).
- Peak 5090 occupancy during the generation window: 15,273 MiB of 32,607 MiB.
  Engine-declared split: diffusion model 13,571 MiB VRAM + VAE 644 MiB VRAM,
  text encoder 15,536 MiB CPU RAM — CPU offload behaved as specified.
- Content sanity via pixel statistics (view_image unavailable, no vision key):
  75% near-white, 23% red pixels, 1536 unique colours in the 1024px frames —
  consistent with the red-teapot-on-white-table prompt. The 2-step 512px
  frame is content-garbage, as expected for transport-only proof.
- Oracle untouched throughout: PRO 6000 steady at 61,494 MiB; the assistant
  served its own qualification turn.
- Restoration verified: logic endpoint live, marker unchanged
  (`qwen38-flash-next-256k`), both units `active`, GPU state identical to pre-test.

Still open before `qwen-image-flux-dual` is promotable:

- FLUX.2-dev generation has never run: it needs ~61.6 GB of the PRO 6000,
  which is the Oracle's exact footprint. It can only be qualified in a window
  where the operator accepts assistant downtime.
- Live activation of the dual profile through `trinity profile switch` (stops
  Oracle — assistant down during the switch).
- Boot persistence, repeated activation, and unload/return cycling.

Sized consequence on the 5090: logic (23.2 GB) and Qwen Image (15.3 GB peak)
cannot coexist in 32.6 GB. A 5090-only image profile can preserve the Oracle
and assistant while replacing logic.

## Operator tooling (code-complete, not live-activated by this session)

Per operator directive ("do the code so that I can use them MYSELF"), the
activation transaction now wires the operator's own tooling end to end:

- `scripts/inference/activate-image-profile.py` calls
  `scripts/inference/sync-openclaw-models.py --profile qwen-image-flux-dual`
  once both image services are ready.
- The sync sets `models.providers.openai.baseUrl` to the live
  stable-diffusion.cpp endpoint (port from the profile's first active image
  allocation), `agents.defaults.mediaModels.image.primary`
  (`openai/gpt-image-2` — OpenClaw validates capability hints by model ref;
  sd-server ignores the request model field), and the required
  `browser.ssrfPolicy.dangerouslyAllowPrivateNetwork` opt-in, then restarts
  the OpenClaw gateway. OpenClaw's first-class `image_generate` tool then
  appears in chat; no image model is registered as a chat model.
- Restoring any chat profile through `trinity profile switch` runs the same
  sync, which removes exactly these managed keys (an operator-owned openai
  provider with any other baseUrl is never touched; the SSRF opt-in stays,
  matching the sync script's set-only precedent).
- Re-running activation while services are live re-syncs idempotently, so a
  hand-reverted config is rewired without a service restart.
- Transient image units remain session-scoped: boot restoration is still an
  open qualification item. After a reboot with the image marker set, rerun
  the profile switch to bring the services back.
