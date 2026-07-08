# SDD-049 — Model runtime actuation (functional load / unload / warm for D-03)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-08
> Closes findings: none (actuation half atop the D-03 read model + SDD-047 control surface)
> Derived from: operator directive 2026-07-08 (chose the d-03 model-runtime engine after SDD-048's approval-authority merged in PR #26); SDD-047 (cockpit functional execution / R10274 control-exec-api); SDD-045 (control surface); M075 SRP topology (`config/inference/m075-srp-topology.yaml`); M011 KV-cache hierarchy (`config/inference/m011-kv-cache-hierarchy.yaml`, spec-only).

## Mission

Make the D-03 model-health panel's three actions — **load model**, **unload
idle**, **warm KV** — functional as sanctioned cockpit controls on the SDD-047
R10274 rail. Today they are neutralized ("planned"); the D-03 read path
(`model-health.py`) is complete, but the actuation half is greenfield.

## Problem

There is **no per-model hot-swap** in this architecture. A Trinity tier is one
server process serving ONE model, bound at systemd-unit start via a `*_MODEL`
env (`start-{pulse,logic-engine,oracle-core}.sh`). So the three buttons have no
real backend:

1. **model load** — no `models load` verb; "load model X into role R" must mean
   "resolve X → (tier, on-disk path), point the tier's env at X, and restart the
   tier unit." The `sovereign-osctl inference {start|stop|restart} <tier>`
   primitive exists (control `inference-tier`), but the id→path resolver, the
   env-drop-in orchestration, the `/run/sovereign-os/model-state.json` **producer**
   (nothing writes it — `model-health.py` only reads it), and a VRAM-fit gate do
   not.
2. **model unload** — no per-model unload / idle tracking. Manual unload = stop the
   role's tier + update state.
3. **kv-cache warm** — no prefill/warm runtime. `m011` is a spec contract;
   `flex-profile.kv_cache_dtype` is KV *quantization*, not warming.

## Required coverage

### Load semantics + actuation

- **load = tier-(re)start bound to the model** (the only real primitive; no
  hot-swap). `models load <id>` resolves the catalog id → its `tier` (→ SRP role
  via `TIER_TO_ROLE`) and its on-disk path, writes the tier's env drop-in, and
  restarts the tier unit.
- **Actuation channel = the highest-precedence env drop-in.** The start scripts do
  `runtime_profile_override <VAR>` (sets only if unset) BEFORE `: "${VAR:=default}"`,
  and each unit has an `EnvironmentFile`. Writing `<TIER>_MODEL=<path>` into
  `/etc/sovereign-os/inference-<tier>.env` wins over both the active runtime
  profile and the hardcoded default — no start-script edits.
- **id→path resolution (Q-049-A)** — NOT a string-munge of the id. Resolve id →
  catalog entry → `hf_repo_id` (`org/name`) → try `<MODELS_DIR>/<org>__<name>`
  then `<MODELS_DIR>/<basename>` then `<MODELS_DIR>/<id>`, and **verify the
  directory exists**, else a structured error. (Two on-disk conventions coexist:
  `models pull` writes `basename`; `start-oracle-core.sh` expects `org__name`.)
- **role→GPU is fixed** (`crates/sovereign-hardware-registry canonical_role()` /
  m075): conductor=CPU, logic=GPU0 (RTX 4090), oracle=GPU1 (Blackwell). No
  ambiguity — `--role` is derivable from the catalog `tier`, so `models load <id>`
  is self-contained.
- **precision is encoded in the id** (Nemotron BF16/FP8/NVFP4 are distinct catalog
  ids) — no `--precision` flag needed; loading a precision variant = loading its id.

### VRAM-fit gate (operator decision: REFUSE by default)

Before load, compare the catalog `vram_gib_min` against the role's **live free
VRAM** (`model-health.collect_gpus()` `mem_total − mem_used`). **Refuse** (error)
if it won't fit; `--force` is the only bypass and is logged. (Stricter than
`start-oracle-core.sh`'s warn-but-proceed — appropriate for a web-triggered
control that could OOM a live GPU.) If GPU telemetry is unavailable, the check is
skipped with a note (cannot verify) rather than refusing.

### model-state.json producer

The load/unload engine becomes the writer of `/run/sovereign-os/model-state.json`
in the shape `model-health.py` reads (`{loaded:{role:[{id,precision,path,
size_bytes}]}}`), written **atomically** (`os.replace`, the approval-decide.py
precedent), so the D-03 "loaded models" overlay becomes live.

### Warm (operator decision: minimal prefill NOW)

`models warm {logic|oracle}` → the role's tier port (LOGIC_PORT 8082 / ORACLE_PORT
8083) → POST a tiny `/v1/completions` (`max_tokens:1`) to the running vLLM OpenAI
server to load weights + prime the KV cache; graceful error if the server is down.
Non-privileged (loopback HTTP, no root/mutation), DRY-RUN by default. logic|oracle
only — the GPU tiers with a KV cache.

## Goals

- Functional load + unload + warm via the sanctioned control-exec-api rail; each a
  new control auto-rendered on d-03 (`applies_to: [d-03-model-health]`).
- Reuse `model-health.py` (import its `load_catalog` / `collect_gpus` /
  `TIER_TO_ROLE` / `MODEL_STATE_PATH`) — keep it a pure reader; writers live in new
  `scripts/models/{load,unload,warm}.py`.
- R10212 preserved: selfdef/perimeter untouched; `state_path` free of
  selfdef/tetragon; `model-health-api.py` stays read-only (405).

## Non-goals (Stage 4 / follow-up Epic)

- `--idle-for` **auto-unload** as a recurrent hook.
- Real per-model VRAM **eviction / LRU** accounting.
- Richer warm (profile/dtype-aware prefill, multi-request warmup curves).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-049-A | How to derive the on-disk model path from the catalog id? | **proposed: id → catalog → hf_repo_id → try `<org>__<name>` then `<basename>` then `<id>` under MODELS_DIR → verify is_dir(). Confirm the canonical convention.** |
| Q-049-B | Should `unload` cover conductor/pulse (CPU) too, or logic/oracle only? | **proposed: logic/oracle only (the GPU tiers). Operator may extend.** |
| Q-049-C | When the resolved path is absent on disk — refuse, or offer `models pull`? | **proposed: refuse with a structured error naming the tried paths. Operator may prefer an auto-pull.** |
| Q-049-D | Should load auto-`inference stop` a conflicting model already on that GPU before restart? | **proposed: no (restart replaces the tier's model anyway); revisit if multi-model-per-GPU lands.** |
| Q-049-E | VRAM-fit posture. | **answered (operator, 2026-07-08): REFUSE by default, `--force` (logged) override.** |
| Q-049-F | kv-warm scope. | **answered (operator, 2026-07-08): build a minimal prefill-warm now (a 3rd control this PR).** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** `scripts/models/load.py` — resolve id→(tier,path), VRAM-fit gate,
  write the tier env drop-in, restart the unit, publish `model-state.json`
  atomically, DRY-RUN default.
- **Stage 2:** `scripts/models/unload.py` — stop the role's tier + rewrite state.
- **Stage 3:** `scripts/models/warm.py` + three controls (`model-load`,
  `model-unload`, `model-warm`) + `cmd_models()` case arms + sudoers + lint bumps
  (18→21) + re-enable the three d-03 buttons + a unit test suite.
- **Stage 4 (follow-up):** idle-auto-unload + LRU eviction + richer warm.

## Cross-references

- `scripts/inference/model-health.py` — the D-03 reader (import its helpers).
- `scripts/inference/start-{pulse,logic-engine,oracle-core}.sh` — `*_MODEL` env /
  `runtime_profile_override` precedence + tier ports.
- `models/catalog.yaml` — id → hf_repo_id → path source.
- `config/inference/m075-srp-topology.yaml` + `crates/sovereign-hardware-registry`
  — fixed role→GPU.
- `scripts/operator/_action_exec.py` — the exec rail (`state_path` must avoid
  selfdef/tetragon); `control-exec-api.py` — the R10274 write daemon.
- `config/control-systems.yaml` — the 18 controls (model the 3 new on rollback-apply
  / approvals-decide).
- SDD-047 (cockpit functional execution), SDD-045 (control surface), SDD-048
  (approval authority — the prior greenfield engine).
