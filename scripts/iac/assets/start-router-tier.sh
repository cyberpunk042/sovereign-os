#!/usr/bin/env bash
# Start one Router-tier pooling model under host-resident vLLM.
#
# WHAT THE ROUTER TIER IS
#   The Genesis Trinity (Pulse · Logic · Oracle) is about generation. The
#   catalog also carries a fourth, quieter tier — `router` — holding the models
#   that do not generate text at all: embedders and cross-encoder rerankers.
#   None of them had ever been served on this box, which is why retrieval here is
#   still BM25 + char-n-gram: lexical only, no semantic recall.
#
# WHY ONE SCRIPT FOR BOTH
#   An embedder and a reranker differ by exactly two vLLM flags (--runner and
#   --convert) and their port. Everything else — the venv, the GPU pin, the cache
#   relocation, the nvcc-avoidance settings the Logic tier discovered the hard
#   way — is identical. Two near-identical launchers would drift; the difference
#   belongs in the env file, not in a copy of the script.
#
#   vLLM serves ONE model per process, so the tier is two units, not one:
#     sovereign-router-embed.service   /v1/embeddings
#     sovereign-router-rerank.service  /rerank, /v1/score
#
# WHY NOT scripts/inference/ WITH THE OTHER LAUNCHERS
#   Because of where it has to be INSTALLED. /opt/sovereign-os is a dpkg-owned
#   payload; only module 90 writes there, and 90 runs after 78. A unit whose
#   ExecStart pointed into the payload would reference a file that does not exist
#   until a second converge. Module 78 installs this to /usr/local/lib instead,
#   which nothing else owns — the same reasoning that placed gpu-route-apply.sh.
#
# Env (all set by /etc/sovereign-os/router-<role>.env, written by module 78):
#   ROUTER_MODEL        path to the weights directory
#   ROUTER_SERVED_NAME  the id this serves under; must equal the proxy id
#   ROUTER_HOST/PORT    listen address
#   ROUTER_RUNNER       vLLM --runner (pooling for both roles here)
#   ROUTER_CONVERT      vLLM --convert (classify for the cross-encoder; unset for
#                       the embedder, whose config already declares its head)
#   ROUTER_MAX_MODEL_LEN, ROUTER_GPU_MEMORY_UTILIZATION
#   ROUTER_EXTRA_ARGS   passthrough for anything not modelled above
#
# shellcheck shell=bash
set -euo pipefail

: "${ROUTER_MODEL:?ROUTER_MODEL is required}"
: "${ROUTER_HOST:=127.0.0.1}"
: "${ROUTER_PORT:?ROUTER_PORT is required}"
: "${ROUTER_RUNNER:=pooling}"
: "${ROUTER_MAX_MODEL_LEN:=8192}"
# These models are ~2 GiB against a 24 GiB card. vLLM's default 0.90 would
# reserve almost the whole GPU for a KV cache that a pooling runner barely uses,
# and the two router units share this card — the second would then fail to
# allocate. Small and explicit.
: "${ROUTER_GPU_MEMORY_UTILIZATION:=0.15}"

# Idempotency, matching start-logic-engine.sh: a unit restarted while the old
# process still holds the port should no-op rather than crash-loop on EADDRINUSE.
if command -v ss >/dev/null 2>&1 && ss -lnt "sport = :${ROUTER_PORT}" 2>/dev/null | grep -q LISTEN; then
  echo "port ${ROUTER_PORT} already listening — router tier appears up; no-op exit"
  exit 0
fi

argv=(python -m vllm.entrypoints.openai.api_server
      --model "${ROUTER_MODEL}"
      --host "${ROUTER_HOST}" --port "${ROUTER_PORT}"
      --runner "${ROUTER_RUNNER}"
      --max-model-len "${ROUTER_MAX_MODEL_LEN}"
      --gpu-memory-utilization "${ROUTER_GPU_MEMORY_UTILIZATION}")

[ -n "${ROUTER_SERVED_NAME:-}" ] && argv+=(--served-model-name "${ROUTER_SERVED_NAME}")
[ -n "${ROUTER_CONVERT:-}" ]     && argv+=(--convert "${ROUTER_CONVERT}")
[ -n "${ROUTER_TRUST_REMOTE_CODE:-}" ] && argv+=(--trust-remote-code)
# Deliberately unquoted: ROUTER_EXTRA_ARGS carries several flags, not one.
# shellcheck disable=SC2206
[ -n "${ROUTER_EXTRA_ARGS:-}" ] && argv+=(${ROUTER_EXTRA_ARGS})

echo "router tier: model=${ROUTER_MODEL} served=${ROUTER_SERVED_NAME:-<path>} port=${ROUTER_PORT}"
echo "argv: ${argv[*]}"

[ -n "${SOVEREIGN_OS_DRY_RUN:-}" ] && { echo "SOVEREIGN_OS_DRY_RUN — not starting"; exit 0; }

exec "${argv[@]}"
