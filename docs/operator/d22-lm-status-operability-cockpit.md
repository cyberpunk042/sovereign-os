# D-22 — Language Model Status & Operability (cockpit panel)

> Operator-facing cockpit panel. Read-only mirror of the model-health core.
> Operator §1g standing rule (sacrosanct): **We do not minimize anything.**

## What it is

D-22 is a cockpit dashboard that shows, **per device** (CPU0 / GPU0 / GPU1),
the language models currently bound to each SRP role and their operability
state — with per-model **Actions / Tests** and a **render-only Chat** composer.
It is a different *rendering* of the same joined data the D-03 model-health panel
uses, not a new data source.

Device → SRP role mapping (M075 topology):

| Slot | SRP role | Hardware |
|------|----------|----------|
| CPU0 | Conductor (Pulse) | Ryzen 9 9900X AM5 AVX-512 (bitnet.cpp ternary) |
| GPU0 | Logic Engine | Logic GPU |
| GPU1 | Oracle Core | Blackwell (NVFP4) |

Each device exposes **Model 0 / Model 1 / Model 2** tabs (the per-role candidate
or runtime-loaded models), a History | Selected table with latency (p50/p95/p99)
when the inference fabric publishes it, and an operability action bar.

## Surfaces (§1g ladder)

| Surface | Path |
|---------|------|
| core | `scripts/inference/model-health.py` (shared with D-03; reused, not duplicated) |
| api | `scripts/operator/lm-status-operability-api.py` — `GET /api/lm-status/{health,devices,stream}` |
| webapp | `webapp/d-22-lm-status-operability/index.html` (served at `/webapp/`) |
| service | `systemd/system/sovereign-lm-status-operability-api.service` (loopback `127.0.0.1:8122`) |

`cli` / `tui` / `dashboard` / `mcp` are **not applicable** — the CLI is
`sovereign-osctl model-health` on the shared core, and the webapp *is* this
panel's operator dashboard. Tracked in `scripts/operator/surface-map.py`.

## Read-only boundary (R10212)

The panel **never mutates**. The API daemon fail-closes on POST/PUT/DELETE
(`405`). Every **Action** and **Test** button, and the **Chat** Send, composes
the equivalent **MS003-signed CLI verb** and **copies it to the clipboard** for
the operator to run out-of-band:

| Button | Copied signed verb |
|--------|--------------------|
| Action · load | `sovereign model load <model> --role <conductor\|logic\|oracle> --precision …` |
| Action · toggle | `sovereign srp toggle <role>` |
| Action · override | `sovereign srp override <task> <role>` |
| Test · eval | `sovereign models eval <model> --dry-run` |
| Test · bench | `sovereign srp benchmark <role> --dry-run` |
| Chat · Send | `sovereign infer --targets <CPU0,GPU0,GPU1> --prompt "…"` |

## Run it

```sh
python3 scripts/operator/lm-status-operability-api.py    # http://127.0.0.1:8122/webapp/
# or, packaged:
systemctl enable --now sovereign-lm-status-operability-api.service
```

`--self-check` prints one devices view and exits 0 (CI smoke).

## Chat scope (deferred)

sovereign-os has no inference-invocation surface yet; live inference belongs to
the M058 fabric / a sibling runtime. The Chat is **render-only** in this build
(composes + clipboard-copies a signed invocation); live streaming wires in when
an inference producer publishes `/run/sovereign-os/model-state.json`-style state.

## Related

- **D-03 model-health** — the SRP-role health panel this reuses.
- **M075** — SRP hardware topology (Conductor/Logic/Oracle).
- Companion panel **D-21 LM Orchestration** (profiles + hardware-assignment grid)
  — the profiles-family decision (5 orchestration-intent profiles vs the
  verbatim-locked 3 M076 load-balancing profiles) is operator-pending.
