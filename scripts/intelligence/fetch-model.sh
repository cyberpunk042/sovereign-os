#!/usr/bin/env bash
# scripts/intelligence/fetch-model.sh — fetch a small REAL trained model for the
# sovereign Rust runtime to serve (sovereign-serve --model / the gateway).
#
# OPT-IN, MANUAL ONLY. This downloads ~0.5 GB from HuggingFace; it is NEVER wired
# into provisioning or first-boot. Run it by hand when you want the local brain
# to do genuine inference on real weights.
#
# Default model: HuggingFaceTB/SmolLM-135M — Llama-architecture (loader-
# compatible: RoPE base 10000, GQA, tied embeddings, SwiGLU/RMSNorm, F32/BF16),
# GPT-2 byte-level BPE tokenizer.json (vocab 49152), small enough to run on CPU.
#
# Usage:
#   scripts/intelligence/fetch-model.sh [DEST_DIR]
#   MODEL_REPO=HuggingFaceTB/SmolLM2-360M scripts/intelligence/fetch-model.sh /var/lib/sovereign-os/models/smollm2-360m
#
# Then:
#   sovereign-serve --model DEST_DIR "The capital of France is"
set -euo pipefail

MODEL_REPO="${MODEL_REPO:-HuggingFaceTB/SmolLM-135M}"
DEST="${1:-./models/$(basename "${MODEL_REPO}")}"
BASE="https://huggingface.co/${MODEL_REPO}/resolve/main"
FILES=(config.json tokenizer.json model.safetensors)

echo "[*] fetching ${MODEL_REPO} -> ${DEST}"
mkdir -p "${DEST}"

for f in "${FILES[@]}"; do
  out="${DEST}/${f}"
  if [ -s "${out}" ]; then
    echo "  ✓ ${f} already present ($(wc -c < "${out}") bytes) — skipping"
    continue
  fi
  echo "  ↓ ${f}"
  # --retry survives transient DNS/network hiccups; -f fails on HTTP errors.
  curl -fsSL --retry 5 --retry-delay 2 --max-time 900 "${BASE}/${f}" -o "${out}.part"
  mv "${out}.part" "${out}"
  echo "    got $(wc -c < "${out}") bytes"
done

echo
echo "[✓] ${MODEL_REPO} ready in ${DEST}"
echo "    run:  sovereign-serve --model ${DEST} \"The capital of France is\""
