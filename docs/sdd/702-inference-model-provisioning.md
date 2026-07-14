# SDD-702 — inference model provisioning: the vLLM Oracle tier gets a real model at first boot (F-2026-112)

> Status: draft
> Owner: operator-directed 2026-07-14 (build-and-flash readiness — inference; operator upgraded the Oracle model to Llama 4 Scout via AskUserQuestion); agent-authored.
> Closes: **F-2026-112** (HIGH).
> Mandate module: **E11.M702**.
> Number band: **700–799 (phase-1 audit continuation — build-and-flash readiness)** per SDD-100.

## The directive

Batch 4 of the build-and-flash readiness pass: the piece that makes SAIN-01 an
actual AI node. The operator directed me to research the model rather than ask
blindly, then chose the Oracle-tier upgrade.

## F-2026-112 (HIGH) — the vLLM serve tier references models that nothing downloads

Investigating *from* the project (not over it) surfaced that the repo already has a
deliberate **3-tier inference architecture** with real serve units reading from
`/mnt/vault/models/<name>`:

| Tier | Unit | Model it reads |
|---|---|---|
| Pulse | `sovereign-pulse` (bitnet.cpp, CPU/CCD0) | `microsoft/bitnet-b1.58-2B-4T` (ternary) |
| Logic | `sovereign-logic-engine` (vLLM) | `qwen3-coder` |
| Oracle | `sovereign-oracle-core` (vLLM, Blackwell) | `nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning` |

vLLM itself is already declared in `config/operator-deps.toml` `[pip]`. But **nothing
downloads any of these models** — `scripts/intelligence/fetch-model.sh` only pulls a
0.5 GB SmolLM smoke model and is explicitly "never wired". So a flashed box has the
full serving machinery (`model_serve_cli`, `VllmBackend`, oracle-core) pointed at
`/mnt/vault/models/<model>` paths that **do not exist** — the inference tier is
weightless, and the AI node can't actually infer.

Two things were wrong to fix at once:

1. **No provisioning** — nothing brings a real model onto the box.
2. **The Oracle model underused the card** — the default Nemotron **30B/3B-active**
   MoE uses `<30 GB` of the 96 GB Blackwell, leaving ~66 GB idle. Asked to research
   the best current fit, the operator chose the upgrade.

## The fix — a first-boot model-provision hook + the Oracle upgrade

**Operator decision (AskUserQuestion):** upgrade the Oracle model to
**`meta-llama/Llama-4-Scout-17B-16E-Instruct`** — 109B total / 17B-active MoE,
~55–60 GB at Q4, fitting the 96 GB card with wide KV-cache headroom, MoE-fast decode,
10M context. (The researched best single-96 GB fit; a 70B-dense FP8 or a Qwen3 large
model are the ungated alternatives.)

- **`provisioning.model`** profile block (+ schema): `repo` / `local_dir` (under
  `/mnt/vault/models`, where the Oracle Core reads) / `quantization` (fp8) /
  `min_free_gb`. Swappable — point `repo` at any vLLM-servable model.
- **`inference-model-provision.sh`** first-boot hook: idempotent (a present
  `config.json` → no-op), VM-skipped. Downloads `repo` → `local_dir` via
  `huggingface-cli download` (sharded + resumable), **gated-token aware**
  (`SOVEREIGN_OS_HF_TOKEN` — Scout is gated), then sets `ORACLE_MODEL=<local_dir>`
  in `/etc/sovereign-os/inference-oracle-core.env` so the serve unit uses the
  provisioned model (the profile is the source of truth, superseding the shipped
  Nemotron default). **NON-FATAL throughout**: a missing huggingface CLI, no token,
  insufficient free space, or a download error each log a clear message + skip
  cleanly (a multi-GB pull must never brick first boot — it's fully resumable
  post-flash with `systemctl start sovereign-inference-model-provision`).
- **`sovereign-inference-model-provision.service`**: first-boot target member,
  `ConditionVirtualization=no`, `RequiresMountsFor=/mnt/vault/models` (the ZFS
  vault must be mounted first), `TimeoutStartSec=0` (a big download isn't timed
  out), `ProtectSystem=strict` + a narrow RWP (`/mnt/vault/models` + `/etc/sovereign-os`
  + the metric dir).

The Pulse (BitNet ternary) + Logic (Qwen3-Coder) tiers keep their own model defaults
— this SDD provisions the Oracle model, the one the operator upgraded.

## Why not a new auto-serve unit

Serving stays **operator-launched** (the deliberate `installed-off` posture — like
selfdef + ghostproxy). This SDD provisions the model + wires `ORACLE_MODEL`; the
operator starts the tier (`systemctl start sovereign-oracle-core` /
`sovereign-osctl inference start`). Adding an auto-serve boot unit would break the
posture, so it's out of scope.

## The lint

`tests/lint/test_inference_model_provision_contract.py` (6 cases): vLLM +
huggingface_hub declared in operator-deps `[pip]`; the hook uses `huggingface-cli`,
is gated-token aware, wires `ORACLE_MODEL`, and carries the non-fatal skip paths; the
unit is a first-boot member requiring the vault mount with no download timeout; the
profile's `local_dir` lands under `/mnt/vault/models` where the serve units read (not
an orphan path). The per-unit systemd coverage/hardening + firstboot-membership +
install-coverage + metric-inventory lints cover the new unit + metrics generically.

## Verification (real, observed)

- `bash -n` on the hook clean; the profile validates against the schema
  (`jsonschema`); `operator-deps.toml.example` parses (`tomllib`).
- `pytest tests/lint/test_inference_model_provision_contract.py` → **6 passed**;
  the firstboot-membership + metric-inventory lints green with the new unit/metrics.
- Full `tests/` suite + all 5 profiles validated before push (the verification the
  #170 schema slip taught me to run).
- **Not** verified: the actual vLLM install / multi-GB gated download / model serve —
  needs the physical SAIN-01 + an HF token + network (no GPU/token/weights in CI).
  Same static-contract bar as every first-boot hardware hook.

## Scope / safety

New: `inference-model-provision.sh` hook + `sovereign-inference-model-provision.service`
unit + the contract lint + the `provisioning.model` profile block + schema. Wired:
firstboot target `Wants=` + membership floor, `provision-bake.sh` FB_UNITS, systemd
README fleet count, metric inventory. operator-deps `[pip]` **unchanged** (vLLM +
huggingface_hub were already declared — a first grep saw only the `[pip]` header).
No Rust crate, no gatewayd/cockpit/webapp change; no new dependency. The hook is
idempotent + VM-skipped + fully non-fatal. MS003 `unsigned-pending-MS003`.

## Non-goals

- Auto-serving on boot (deliberate operator-launched posture).
- Re-picking the Pulse (BitNet ternary) / Logic (Qwen3-Coder) tier models (kept).
- Installing bitnet.cpp for the Pulse tier (a separate llama.cpp-derived build).
- gatewayd auth/TLS + wiring the security crates into the daemon path (Batch 6).
- Pinning an exact Scout revision (the profile names the repo; `main` is fine).

## Cross-references

- `scripts/hooks/post-install/inference-model-provision.sh` — the gated-token, resumable, non-fatal pull
- `systemd/system/sovereign-inference-model-provision.service` — first-boot member requiring the vault mount
- `systemd/system/sovereign-oracle-core.service` — the vLLM serve unit `ORACLE_MODEL` points into
- `config/operator-deps.toml.example` — vLLM + huggingface_hub (already declared)
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-112 (closed here)
