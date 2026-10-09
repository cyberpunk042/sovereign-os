# Image Generation (Cockpit Panel)

*Purpose*: Test the live image model directly from the dashboard.

## How it works
The panel automatically discovers any model whose `id` contains `image` in OpenClaw’s catalog.
It then presents:

1. **Model selector** – a dropdown of all discovered image models (currently `openai/gpt-image-2`).
2. **Prompt box** – single‑line text input.
3. **Generate button** – invokes the `image_generate` tool.

## UI
```
┌───────────────────────────────────────────────────────┐
│ Image Generation                                         │
│ ------------------------------------------------------- │
│ Model:   [openai/gpt-image-2 ▼]                         │
│ Prompt:  _____________________________________________ │
│          [ Generate ]                                    │
│                                                       │
│   <generated image appears here after click>           │
└───────────────────────────────────────────────────────┘
```

## Implementation (behind the scenes)
When you click **Generate**, the cockpit sends this JSON to OpenClaw:
```json
{
  "tool": "image_generate",
  "args": {
    "prompt": "<your‑prompt>",
    "size": "1024x1024",
    "model": "<selected‑model‑id>"
  }
}
```
OpenClaw returns a PNG attachment, which the cockpit automatically displays in the panel.

## Notes
- This panel is **read‑only** – it never starts or stops services.
- It works with any future image model you add; just register it in the model catalog.
- No sudo or manual commands are required.

---
*Safe UI addition – only reads the model catalog and calls the already‑exposed `image_generate` endpoint.*
