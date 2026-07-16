# SDD-716 — adapter transport + ZFS lineage (Slice 2b) (IMPLEMENTATION)

> Status: draft (implementation — Slice 2b: the transport half of the LoRA loop)
> Owner: operator-directed 2026-07-16 (verbatim): *"2b and 3 now, one PR. take your time"*.
> Addresses: the missing "ship a promoted adapter SAIN-01 → box, versioned for rollback" link in the M046
> foundry (E0444 Adapter Memory pipeline step "monitored deployment"; E0446 ZFS role "adapter versions +
> rollback"). No finding re-opens.
> Mandate module: **E11.M716**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## The gap this closes

With SDD-715, a promoted adapter can be *served* (`llama-server --lora`). But nothing moved the weights from the
training box to the serving box, and E0446's "ZFS owns adapter versions + rollback" had no implementation. The
M046 loop had a hole between *promote* (SDD-051 `adapter-decide.py`, MS041 triple-gate, `registry.json`) and
*serve* (SDD-715). This lands the transport + versioning link.

## What this delivers

- **NEW `scripts/inference/adapter-transport.py`** — a **planner** (stdlib-only; reuses `adapter-foundry.py`'s
  registry reader so it never invents an adapter):
  - `plan <id> [--from SRC] [--version V]` → the exact `rsync` pull (`SRC/<id>/` →
    `/var/lib/sovereign-os/adapters/<id>/<version>/`) **plus** a `zfs snapshot <dataset>@adapter-<id>-<version>`
    for lineage/rollback (E0446). Version defaults to the registry's promotion-history depth (`v1`, `v2`, …).
  - `list` → local adapter versions present on the box.
  - `rollback <id> <version>` → the `zfs rollback <dataset>@adapter-<id>-<version>` plan.
  - **DRY-RUN by default** (prints the plan); `--apply` executes via subprocess. Source / dataset / adapters-dir
    are env-overridable (`SOVEREIGN_OS_ADAPTER_SOURCE` default `sain-01:/var/lib/sovereign-os/adapters`,
    `SOVEREIGN_OS_ADAPTER_DATASET`, `SOVEREIGN_OS_ADAPTERS_DIR`).
- **NEW contract lint** `tests/lint/test_adapter_transport_contract.py`: present + executable + stdlib-only;
  reuses the foundry registry reader; `plan` emits `[rsync, zfs-snapshot]` into the versioned dest with the
  `@adapter-<id>-<version>` snapshot; `rollback` emits `zfs rollback`; DRY-RUN default (no host mutation
  without `--apply`).

## Why a planner, not an executor

Cross-box transport (rsync/ssh from SAIN-01) and ZFS operations cannot run in CI — there is one box, no pool,
no second host. So the deliverable is the **plan** (the exact commands, argv-tested) plus the versioning
**layout**; the operator (or a runtime job) runs `--apply` on the real box. This mirrors the project's dry-run
discipline and SDD-714/715's "argv proven, hardware bring-up is a runtime step" posture.

The ZFS dataset itself is **profile-declared** (`hardware.storage.datasets` → `zfs-datasets-create.sh`), not
hardcoded here — the planner snapshots whatever dataset backs `/var/lib/sovereign-os/adapters`, so an operator
who wants adapter rollback declares that path as its own dataset in their profile.

## The M046 loop, now complete (serving side)

Train on SAIN-01 (E0446 4090/Blackwell) → promote (SDD-051 `adapter-decide`, MS041 triple-gate) →
**`adapter-transport.py plan … --apply`** pulls the weights into `/var/lib/sovereign-os/adapters/<id>/<version>/`
and snapshots it → catalog `lora-adapter` bound to `dual-turing-serving` → `llama-server --lora` (SDD-715). A
bad adapter version rolls back via the snapshot.

## Verification

- `python3 -m pytest tests/lint/test_adapter_transport_contract.py` — green (present/executable/stdlib,
  registry reuse, plan/rollback shape, DRY-RUN default).
- Functional: `plan sovereign-os-admin-lora` emits the rsync + `zfs snapshot …@adapter-sovereign-os-admin-lora-v1`
  plan; `rollback` emits `zfs rollback`; `list` reports "(no adapters)" absent a populated dir (honest).
- Full `tests/` + 5 profiles + ruff green; `context.md` sdd count bumped.
- **Not runtime-verified** (no second host / no ZFS pool in CI): a real transfer + snapshot + rollback. The
  plan construction + registry integration are proven.

## Non-goals

- **`sovereign-osctl adapters transport` verb + api + dashboard surface** (the full §1g 8-surface ladder) — the
  core planner lands first; the osctl/api/webapp surfaces are a follow-up.
- **Automatic transport on promotion** (a foundry hook that fires transport when `adapter-decide promote`
  succeeds) — deliberate operator-run step for now.
- **Multi-host fan-out** (one SAIN-01 → many serving boxes).
