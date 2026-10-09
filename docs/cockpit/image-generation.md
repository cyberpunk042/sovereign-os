# Image Generation (Cockpit Panel)

*Purpose*: test the **live image model directly from the dashboard — without
OpenClaw in the path**.

## How it works

The panel talks straight to the stable-diffusion.cpp `sd-server` that an image
profile activates. Discovery is file-driven (operator directive 2026-10-09:
"Remove this hardcoded list"):

1. **Active marker** — `/etc/sovereign-os/active-runtime-profile`.
2. **Profile YAMLs** — every `profiles/{runtime,orchestration}/*.yaml` whose
   `runtime_handler` starts with `image` (image-dual / image-companion).
3. **Live probes** — each declared image allocation port is probed at
   `/v1/models`; only a port that answers `sd-cpp-local` is offered for
   generation. The panel never guesses a port.

The active sd-server exposes the **OpenAI Images API** (verified
`POST /v1/images/generations` with `b64_json` responses; the request's `model`
field is ignored — one runtime per port).

## UI

```
┌──────────────────────────────────────────────────────────────┐
│ Image Generation  [direct sd-server · no OpenClaw]           │
│ status tiles: active profile · port probes · profile count   │
│ ────────────────────────────────────────────────────────────  │
│ Generate: endpoint :8188 ✓ · size · steps · seed             │
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

## Activating an image profile

Generation requires an image profile active, e.g.:

```bash
sudo sovereign-osctl trinity profile switch codernext-image-companion
```

From the cockpit this is the **orchestration-profile** control
(`config/control-systems.yaml`): the D-21 profile rail Apply button — and the
"Activate via rail" button on this panel when served through the :8100 hub —
POST the sanctioned mutation endpoint `control-exec-api` (:8130), which runs
the verb through the `SOVEREIGN_OS_COCKPIT` sudoers bucket
(`scripts/operator/operator-sudoers.sh`, validated with `visudo -cf`). The
image-companion activator keeps the chat Oracle resident, so the assistant
survives the switch. Two gates make it real: the sudoers bucket installed +
`SOVEREIGN_OS_ACTION_EXEC_LIVE=1` on the control-exec-api unit; until then
every Apply is an honest dry-run.

## API surface (`sovereign-image-generation-api`, :8150)

| Route | Notes |
| --- | --- |
| `GET /api/image-gen/status` | active profile, per-port probes, every image-family profile + its exact `change_cli` |
| `POST /api/image-gen/generate` | single-flight; strict validation (prompt ≤1000, size allow-list, steps 1–60, seed 0…2³¹−1); proxies to sd-server; persists a PNG artifact |
| `GET /api/image-gen/gallery` · `GET /api/image-gen/artifact?name=…` | persisted outputs (strict `…\.png` name pattern) |

The generate POST is **inference only**: it starts nothing, stops nothing, and
mutates no host state. Host changes (profile switches) stay the exclusive job
of the control-exec rail (R10274/R10212).

## Relationship to OpenClaw

When an image profile is active,
`scripts/inference/sync-openclaw-models.py` points OpenClaw's `image_generate`
tool at the SAME sd-server port. The two paths are independent: this panel
bypasses OpenClaw entirely, which is exactly how you qualify or debug the
image runtime without an agent in the loop.

## Notes
- Output persistence is best-effort: if the gallery write fails the image is
  still returned inline (never fabricate a success it can't prove).
- One generation at a time (single-flight) — the image GPU has one runtime.
- Works with any future image profile: drop the YAML in
  `profiles/orchestration/` with a `runtime_handler: image*` and it appears.
