# Operator request — 2026-10-09

> one fit on the rtx5090 and the other on the 6000

> create the profile I asked...

> i have a new profile to create / test:
> abenzerps/Qwen-Image-2.1-Uncensored-GGUF
> black-forest-labs/FLUX.2-dev

## Qualification scope

These are image generators, not chat backends. Do not register them as
gpu-oracle/gpu-logic OpenClaw chat models. Current LLM activation remains
qwen38-flash-next-256k until the operator authorizes GPU reassignment.

Initial repository inspection found no ComfyUI/Diffusers activation integration
in scripts, systemd or configuration. Adding ordinary llama.cpp allocations
would not create a working image-generation profile.

Proposed candidates, not yet deployable or qualified:

- Qwen Image 2.1: original requested repository, UC Q4_K_M transformer,
  companion text encoder and VAE; ComfyUI plus compatible GGUF loader.
  Validate repository revisions and component compatibility before download.
- FLUX.2 dev: original requested repository, BF16 transformer on the PRO 6000
  with sequential CPU text-encoder offload. Hardware fit is a hypothesis,
  not a measured result. Requires gated repository access and accepted terms.

Keep inference fully local; do not adopt the model-card remote text encoder.
Preserve 4090 desktop, embedding and reranking allocations.

## Qualification gates

1. Confirm GPU reassignment and repository access; never accept terms for user.
2. Pin runtime/model revisions and exact download manifests with checksums.
3. Implement separate image workflow activation, VRAM preflight, output
   persistence, status, and explicit rollback to the current LLM profile.
4. Generate a fixed-seed benign 512px smoke image, then repeated 1024px images;
   record wall time, peak VRAM, failures and output artifacts.
5. Test unload/reload and return to the existing LLM profile, checking actual
   resident models and both OpenClaw catalogs. Do not promote on load alone.

Sources:
- https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-GGUF
- https://huggingface.co/black-forest-labs/FLUX.2-dev
