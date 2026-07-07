# D-21 — Language Model Orchestration (cockpit panel)

> Operator-facing cockpit panel. Read-only mirror. Operator §1g standing rule
> (sacrosanct): **We do not minimize anything.**

## What it is

D-21 is the model-orchestration console: pick an orchestration **Profile**, see
the **model→hardware assignment grid** (which model runs on GPU0 / GPU1 / CPU0
per **M075** SRP topology), and inspect the **CPU AVX-512 / GPU capability**
panel. It composes three already-shipped sources — no new data model:

| Row | Source |
|-----|--------|
| Profiles | `runtime-modes-api._list_profiles()` (M076 `profiles/runtime/*.yaml`) |
| Assignment grid | `scripts/inference/model-health.py` snapshot (shared with D-03) reshaped to GPU0/GPU1/Ext-GPU/CPU0 cells with Model 0/1/2 + Mode |
| Features CPU / GPUs | `/proc/cpuinfo` AVX-512 flags (VNNI/VPDPBUSD, VPOPCNTDQ…) + GPU compute-cap (NVFP4 on Blackwell) |

Device → SRP role: **GPU0 = Logic**, **GPU1 = Oracle (Blackwell)**, **CPU0 =
Conductor** (Ryzen 9 9900X, cores split 1-7 / 8-15 / 16-24 across Model 0/1/2).
An **Ext-GPU** cell shows N/A until an external card is registered.

## Read-only boundary (R10212)

The cockpit **never mutates SRP topology**. The API daemon fail-closes on
POST/PUT/DELETE (`405`). The central **Apply** composes and **clipboard-copies**
the MS003-signed profile verb (`sovereign-osctl runtime-modes apply <profile>`);
model→hardware assignment is `sovereign srp override` / `sovereign model load
--role …` per M075 R12509/R12564.

## Surfaces (§1g ladder)

| Surface | Path |
|---------|------|
| core | reused: `scripts/inference/model-health.py` + `scripts/operator/runtime-modes-api.py` |
| api | `scripts/operator/lm-orchestration-api.py` — `GET /api/lm-orchestration/{grid,profiles,features,stream}` |
| webapp | `webapp/d-21-lm-orchestration/index.html` (`/webapp/`) |
| service | `systemd/system/sovereign-lm-orchestration-api.service` (loopback `127.0.0.1:8121`) |

Registered in `surface-map.py` (`lm-orchestration`, 4/8 at structural ceiling) +
`nav-snippet.html` (D-21) + `config/dashboard-catalog.yaml`. Inlines the shared
SDD-045 control-surface component.

## Run it

```sh
python3 scripts/operator/lm-orchestration-api.py     # http://127.0.0.1:8121/webapp/
systemctl enable --now sovereign-lm-orchestration-api.service
```

`--self-check` prints one grid/profiles/features view and exits 0 (CI smoke).

## Profiles note (operator-decision pending)

The Profiles row renders whatever `profiles/runtime/*.yaml` ship — today the 3
verbatim-locked M076 load-balancing profiles (ultra-sovereign-efficiency /
high-concurrency-burst / deep-context-synthesis). The 5 sketched
orchestration-**intent** profiles (Full orchestration / Coding Focus / Thinking
Focus / Hybrid / Full Hybrid) are a different axis; because `profiles/runtime/`
is pinned to exactly 3 by `test_runtime_profiles_verbatim`, they need a separate
profile family — **operator decision pending** before they are authored.

## Related

- **D-22 LM Status & Operability** — the companion per-device status panel.
- **D-03 model-health**, **runtime-modes** — the shared cores this reuses.
- **M075** SRP topology · **M076** runtime profiles.
