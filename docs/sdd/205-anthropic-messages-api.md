# SDD-205 — The Anthropic Messages API on the gateway (use the box from VS Code / Claude Code)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-12
> Closes findings: operator directive 2026-07-12 — *"now we need to make it compatible with Anthropic Messages API structure, so that I can use it in vscode and whatever else compatible too with that structure."* Plan approved.
> Derived from / extends: the M033/M034 "Anthropic-first gateway" spec (`config/inference/m033-compatibility-gateway.yaml`, `m034-anthropic-first-gateway.yaml` — `/v1/messages` primary, OpenAI-compat secondary), the OpenAI shim (`/v1/chat/completions`), `sovereign-gatewayd`.

## Mission

Make `sovereign-gatewayd` (:8787) speak the **Anthropic Messages API** so any tool that speaks it — VS Code
extensions (Cline / Claude Dev), Claude Code (`ANTHROPIC_BASE_URL`), the Anthropic SDKs — can drive the
box's **own local model**, entirely on loopback, nothing crossing the network. This fulfils the M034
"Anthropic-first" spec, which had `/v1/messages` as a decision stub; it is now a real generating endpoint.

## Endpoints

| Method + path | Shape |
|---|---|
| `POST /v1/messages` | Anthropic Messages API. Request `{model, max_tokens, system?, messages[], stream?, …}` (content may be a string OR a `[{type:"text",text}]` block array). Non-stream → `{type:"message", role:"assistant", content:[{type:"text",text}], stop_reason:"end_turn", usage:{input_tokens,output_tokens}}`. `stream:true` → SSE: `message_start` → `content_block_start` → `content_block_delta`(`text_delta`)* → `content_block_stop` → `message_delta` → `message_stop`. |
| `GET /v1/models` | Anthropic models list (the one local model). |
| `POST /v1/messages/count_tokens` | `{input_tokens:N}` (best-effort, ~4 chars/token). |

The sovereign routing **DECISION** engine that `/v1/messages` used to return moved fully to **`/v1/infer`**
(`{kind:"decision"}`); `/mcp`, `/v1/simple`, `/v1/explain`, `/v1/deliberate`, `/v1/coat` are unchanged. The
OpenAI shim (`/v1/chat/completions`) stays as the secondary compat surface.

## Wire it up

Start the gateway with a model loaded (a model dir with `config.json` + `*.safetensors` + `tokenizer.json`):

```
SOVEREIGN_GATEWAY_MODEL=/var/lib/sovereign-os/models/smollm-135m sovereign-gatewayd --http
# fetch one: scripts/intelligence/fetch-model.sh /var/lib/sovereign-os/models/smollm-135m
```

- **Claude Code:** `ANTHROPIC_BASE_URL=http://127.0.0.1:8787 ANTHROPIC_API_KEY=sk-local claude` (it POSTs to `<base>/v1/messages`).
- **VS Code — Cline / Claude Dev:** API Provider = **Anthropic**, Base URL = `http://127.0.0.1:8787`, API Key = any (`sk-local`), Model = any (the box serves its local model regardless of the id).
- **Anthropic SDK:** `Anthropic(base_url="http://127.0.0.1:8787", api_key="sk-local")`.

## Sovereign posture

- **Loopback-trust:** the `x-api-key` + `anthropic-version` headers are accepted but not validated — there is
  no cloud auth on a sovereign, loopback-bound box (bind beyond loopback is the operator's §1g decision).
- **Never fabricated (SB-077):** no model loaded → an honest Anthropic **error** envelope (503), not a faked
  message. Generation runs only on the locally-loaded model; the same model-gating the OpenAI shim discloses.
- The requested `model` id is echoed back but the box serves its one local model; `usage` token counts are
  best-effort on a base completion model.

## Honest gating

Wire structure + both transports (non-stream JSON + SSE) are **live and verified** end-to-end with a real
model (SmolLM-135M). Output *quality* is model-gated — a small base model rambles and does not stop cleanly;
a stronger instruct model + stop-sequence handling (a documented follow-up) yields clean turns. Compatibility
(the shape VS Code / Claude Code consume) is complete today.
