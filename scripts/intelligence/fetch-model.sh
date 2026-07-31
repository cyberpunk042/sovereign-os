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

# OPTIONAL files — fetched best-effort, absence is not an error.
#
# tokenizer_config.json carries `chat_template` and `eos_token`, and
# sovereign-gatewayd reads it straight out of the model dir
# (crates/sovereign-gatewayd/src/lib.rs:1312):
#
#     let chat_template = std::fs::read(format!("{dir}/tokenizer_config.json"))
#
# Without it chat_template is None, the gateway falls back to a plain
# role-concatenated prompt, and an INSTRUCTION-TUNED model never sees the
# markers it was trained on — so it never emits its end-of-turn token and runs
# on past the answer. Observed with SmolLM2-1.7B-Instruct (ChatML,
# eos <|im_end|>): asked for the capital of France it answered correctly and
# then kept going, "…Paris.\nassistant\nParis is the capital of France".
# Base models are unaffected, which is why three files were enough until an
# instruct model was served.
OPTIONAL_FILES=(tokenizer_config.json generation_config.json special_tokens_map.json)

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

for f in "${OPTIONAL_FILES[@]}"; do
  out="${DEST}/${f}"
  if [ -s "${out}" ]; then
    echo "  ✓ ${f} already present — skipping"
    continue
  fi
  # No -f exit on 404 here: these are genuinely optional and many repos omit
  # some of them. `|| true` keeps `set -e` from aborting the whole fetch.
  if curl -fsSL --retry 3 --retry-delay 2 --max-time 120 "${BASE}/${f}" -o "${out}.part" 2>/dev/null; then
    mv "${out}.part" "${out}"
    echo "  ↓ ${f} — got $(wc -c < "${out}") bytes"
  else
    rm -f "${out}.part"
    echo "  · ${f} not published by this repo — skipping (optional)"
  fi
done

echo
echo "[✓] ${MODEL_REPO} ready in ${DEST}"
if [ -s "${DEST}/tokenizer_config.json" ]; then
  if grep -q '"chat_template"' "${DEST}/tokenizer_config.json" 2>/dev/null; then
    echo "    chat_template present — instruct models will stop at their end-of-turn token"
  else
    echo "    note: tokenizer_config.json has no chat_template (base model, or template ships elsewhere)"
  fi
else
  echo "    note: no tokenizer_config.json — the gateway will use its fallback prompt format"
fi
echo "    run:  sovereign-serve --model ${DEST} \"The capital of France is\""
