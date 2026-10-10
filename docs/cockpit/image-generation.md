# Image Generation (Cockpit Panel)

*Purpose*: Test the **live stable-diffusion.cpp runtime through its OpenAI Images API** without OpenClaw in the path. Discovery comes from the active profile marker, profile YAMLs, and live `/v1/models` probes — never a hardcoded list.

## Overview

This cockpit panel provides a direct interface to the stable-diffusion.cpp `sd-server` that an image profile activates. It bypasses OpenClaw entirely, allowing you to test image generation directly against the local runtime.

## How It Works

1. **Active marker** — `/etc/sovereign-os/active-runtime-profile`
2. **Profile YAMLs** — every `profiles/{runtime,orchestration}/*.yaml` whose `runtime_handler` starts with `image`
3. **Live probes** — each declared image allocation port is probed at `/v1/models`; only a port that answers `sd-cpp-local` is offered for generation

The active sd-server exposes the **OpenAI Images API** (verified `POST /v1/images/generations` with `b64_json` responses).

## UI

```
┌──────────────────────────────────────────────────────────────┐
│ Image Generation  [direct sd-server · no OpenClaw]           │
│ ────────────────────────────────────────────────────────────  │
│ Banner: active profile · ready ports · runtime status        │
│ ────────────────────────────────────────────────────────────  │
│ Generate: endpoint · size · steps · seed                     │
│           prompt ▸ ▶ Generate                                │
│           <inline PNG + artifact link>                       │
│ ────────────────────────────────────────────────────────────  │
│ Image profiles: each shows its exact                         │
│   sudo sovereign-osctl trinity profile switch <id>           │
│   (+ "Activate via rail" when served through the hub)        │
│ ────────────────────────────────────────────────────────────  │
│ Gallery: last artifacts from                                 │
│   /var/lib/sovereign-os/image-generation                     │
└──────────────────────────────────────────────────────────────┘
```

## Key Elements

### Status Banner
Shows the current state: active profile, ready ports, and runtime status. Updates dynamically based on the daemon's discovery.

### Generation Form
- **Image endpoint**: Automatically populated with live sd-server ports
- **Size**: 1024x1024, 768x768, 512x512, 1024x768, 768x1024
- **Steps**: 1-60 inference steps (sd-server default if omitted)
- **Seed**: Optional seed for reproducibility
- **Prompt**: Text prompt for image generation (max 1000 chars)
- **Negative prompt**: Optional negative prompt (max 500 chars)

### Image Profiles
Lists all available image-family profiles with their exact activation commands.

### Gallery
Shows the last 8 generated artifacts with links to download individual images.

## API Surface (`sovereign-image-generation-api`, :8150)

| Route | Notes |
| --- | --- |
| `GET /api/image-gen/status` | Active profile, per-port probes, every image-family profile + its exact `change_cli` |
| `POST /api/image-gen/generate` | Single-flight; strict validation (prompt ≤1000, size allow-list, steps 1–60, seed 0…2³¹−1); proxies to sd-server; persists a PNG artifact |
| `GET /api/image-gen/gallery` | Persisted outputs (strict `…\.png` name pattern) |
| `GET /api/image-gen/artifact?name=…` | One artifact (strict pattern) |

## Activating an Image Profile

Generation requires an image profile active, e.g.:

```bash
sudo sovereign-osctl trinity profile switch codernext-image-companion
```

From the cockpit this is the **orchestration-profile** control (D-21 rail, R10274): the Apply button — and the "Activate via rail" button on this panel when served through the :8100 hub — POST the sanctioned mutation endpoint `control-exec-api` (:8130), which runs the verb through the `SOVEREIGN_OS_COCKPIT` sudoers bucket.

## Relationship to OpenClaw

When an image profile is active, `scripts/inference/sync-openclaw-models.py` points OpenClaw's `image_generate` tool at the SAME sd-server port. The two paths are independent: this panel bypasses OpenClaw entirely, which is exactly how you qualify or debug the image runtime without an agent in the loop.

## Notes

- Output persistence is best-effort: if the gallery write fails the image is still returned inline
- One generation at a time (single-flight) — the image GPU has one runtime
- Works with any future image profile: drop the YAML in `profiles/orchestration/` with a `runtime_handler: image*` and it appears
- **The daemon must be running** for this panel to work: `python3 scripts/operator/image-generation-api.py`
